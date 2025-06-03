import tweepy
import logging
import os
import requests
import time
from typing import Optional, Dict, Any, List, Tuple # Tuple を追加
from datetime import datetime, timezone # timezone を追加
import io # io を追加
import tempfile # tempfile を追加
import mimetypes # mimetypes を追加
import subprocess # subprocess を追加
import uuid # uuid を追加

# このモジュールがengine_coreパッケージ内にあることを想定してConfigをインポート
# ただし、TwitterClient自体はConfigに直接依存せず、キーは外部から渡される想定
# from .config import Config # 通常はWorkflow層などでConfigからキーを取得して渡す

logger = logging.getLogger(__name__)

# Twitter API v1.1 (メディアアップロード用)
MEDIA_ENDPOINT_URL_V1 = 'https://upload.twitter.com/1.1/media/upload.json'
# Twitter API v2 (ツイート投稿用)
# (tweepy.Clientが内部的にv2エンドポイントを使用する)

class RateLimitError(Exception):
    """レート制限エラーを示すカスタム例外"""
    def __init__(self, message: str, reset_at_utc: Optional[datetime] = None, remaining_seconds: Optional[int] = None):
        super().__init__(message)
        self.reset_at_utc = reset_at_utc
        self.remaining_seconds = remaining_seconds

class TwitterClient:
    def __init__(self, consumer_key: str, consumer_secret: str,
                 access_token: str, access_token_secret: str,
                 bearer_token: Optional[str] = None): # v2用
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.bearer_token = bearer_token

        if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
            msg = "Twitter APIキー/トークンが不足しています。"
            logger.error(msg)
            raise ValueError(msg)
        
        # Tweepy Client (v2) の初期化
        # bearer_tokenは必須ではないが、あると一部のv2エンドポイントで利用可能
        try:
            self.client_v2 = tweepy.Client(
                bearer_token=self.bearer_token, # v2の読み取り専用エンドポイントなどで使用
                consumer_key=self.consumer_key, # v2の投稿エンドポイントで使用
                consumer_secret=self.consumer_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
                wait_on_rate_limit=False # Falseに変更
            )
            logger.info("Twitter API v2 クライアントの初期化に成功しました。")
        except Exception as e:
            logger.error(f"Twitter API v2 クライアントの初期化に失敗: {e}", exc_info=True)
            # v2クライアントが失敗しても、v1.1のメディアアップロードは試行可能にするため、ここではraiseしない
            self.client_v2 = None 

        # Tweepy API (v1.1) の認証ハンドラ (メディアアップロード用)
        try:
            auth_v1 = tweepy.OAuth1UserHandler(
                consumer_key=self.consumer_key,
                consumer_secret=self.consumer_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )
            self.api_v1 = tweepy.API(auth_v1, wait_on_rate_limit=False) # Falseに変更
            logger.info("Twitter API v1.1 ハンドラの初期化に成功しました。")
        except Exception as e:
            logger.error(f"Twitter API v1.1 ハンドラの初期化に失敗: {e}", exc_info=True)
            # v1.1の認証が失敗するとメディアアップロードができないので、これは致命的
            raise ValueError(f"Twitter API v1.1 auth failed: {e}")

    def _get_rate_limit_info_from_exception(self, e: tweepy.errors.TweepyException) -> Dict[str, Any]:
        """Tweepyの例外からレート制限関連情報を抽出するヘルパー"""
        rate_limit_info = {"error_type": type(e).__name__, "message": str(e)}
        reset_dt_utc_val = None
        remaining_sec_val = None

        if hasattr(e, 'response') and e.response is not None and hasattr(e.response, 'headers'):
            headers = e.response.headers
            # rate_limit_info['headers'] = dict(headers) # デバッグ用に全ヘッダはログレベルDEBUGで出すなど検討
            
            limit = headers.get('x-rate-limit-limit')
            remaining_api_calls = headers.get('x-rate-limit-remaining') # 名前変更 remaining -> remaining_api_calls
            reset_unix = headers.get('x-rate-limit-reset')
            
            if limit: rate_limit_info['limit_max'] = limit
            if remaining_api_calls: rate_limit_info['limit_remaining_calls'] = remaining_api_calls
            if reset_unix:
                try:
                    reset_dt_utc_val = datetime.fromtimestamp(int(reset_unix), tz=timezone.utc)
                    rate_limit_info['limit_reset_at_utc'] = reset_dt_utc_val.isoformat()
                    
                    now_utc = datetime.now(timezone.utc)
                    remaining_sec_val = max(0, int((reset_dt_utc_val - now_utc).total_seconds()))
                    rate_limit_info['limit_reset_in_seconds'] = remaining_sec_val
                except ValueError:
                    logger.warning(f"x-rate-limit-resetヘッダーの値 ({reset_unix}) のパースに失敗しました。")
                    rate_limit_info['limit_reset_at_unix'] = reset_unix
        else:
            logger.warning(f"例外 {type(e).__name__} に response または headers 属性がありません。詳細なレート制限情報は取得できません。")
        
        # RateLimitErrorに渡す直前の情報をログ出力
        logger.info(f"RateLimitError生成情報: reset_at_utc={reset_dt_utc_val}, remaining_seconds={remaining_sec_val}, raw_info={rate_limit_info}")

        return {"raw_info": rate_limit_info, "reset_at_utc": reset_dt_utc_val, "remaining_seconds": remaining_sec_val}

    def _modify_video_metadata_ffmpeg(self, input_path: str) -> Optional[str]:
        """ffmpegを使用して動画のコメントメタデータを変更し、新しい一時ファイルのパスを返す。"""
        output_temp_file = None
        try:
            # 出力用の一時ファイル名を生成 (入力と同じ拡張子を維持)
            input_dir = os.path.dirname(input_path)
            input_filename = os.path.basename(input_path)
            input_name_part, input_ext_part = os.path.splitext(input_filename)
            
            # 新しい一時ファイルを作成 (NamedTemporaryFileだとffmpegが書き込めないことがあるので、単純なパスを生成)
            # ffmpegは出力ファイルを自分で作成するので、存在しないパスを指定する
            output_filename = f"{input_name_part}_meta_modified_{uuid.uuid4().hex[:8]}{input_ext_part}"
            output_path = os.path.join(tempfile.gettempdir(), output_filename) # システムの一時ディレクトリに作成

            # ffmpegコマンドの準備
            # コメントにランダムな値を設定
            random_comment = f"mod_{uuid.uuid4().hex[:12]}_{int(time.time())}"
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c', 'copy',         # ビデオとオーディオストリームを再エンコードせずにコピー
                '-metadata', f'comment={random_comment}',
                '-y',                 # 出力ファイルを無条件に上書き
                output_path
            ]
            
            logger.info(f"ffmpegでメタデータ変更開始: {input_path} -> {output_path} (comment: {random_comment})")
            # ffmpegの実行 (標準出力・エラーは抑制し、エラー時のみログに出す)
            process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=False)
            
            if process.returncode == 0:
                logger.info(f"ffmpegによるメタデータ変更成功: {output_path}")
                return output_path
            else:
                logger.error(f"ffmpegの実行に失敗 (code: {process.returncode}): {input_path}")
                logger.error(f"ffmpeg stdout: {process.stdout}")
                logger.error(f"ffmpeg stderr: {process.stderr}")
                # 失敗した場合は生成された可能性のある出力ファイルを削除
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except OSError as e_rem_out:
                        logger.warning(f"ffmpeg失敗後の出力一時ファイル削除エラー: {output_path}, {e_rem_out}")
                return None

        except Exception as e:
            logger.error(f"ffmpeg処理中に予期せぬエラー: {e}", exc_info=True)
            if output_path and os.path.exists(output_path):
                 try: os.remove(output_path) 
                 except: pass # エラー時は握りつぶす
            return None

    def _upload_media_v1(self, media_url: str) -> Optional[str]:
        """指定されたURLのメディアをTwitterにアップロードし、メディアIDを返す (v1.1 API)。"""
        if not self.api_v1:
            logger.error("Twitter API v1.1が初期化されていません。メディアをアップロードできません。")
            return None
        
        try:
            logger.info(f"メディアURLからデータをダウンロード開始: {media_url}")
            response = requests.get(media_url, stream=True)
            response.raise_for_status() # HTTPエラーチェック
            original_media_url = media_url # 元のURLを保持

            # Google Driveの共有リンクを直接ダウンロード用URLに変換
            if "drive.google.com" in media_url and "/view" in media_url:
                try:
                    parts = media_url.split('/')
                    file_id = None
                    for i, part in enumerate(parts):
                        if part == 'd' and i + 1 < len(parts):
                            file_id = parts[i+1]
                            break
                    
                    if file_id:
                        direct_download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                        logger.info(f"Google Driveリンクを検出。直接ダウンロードURLに変換: {direct_download_url}")
                        # stream=True を維持しつつ、新しいURLで再度リクエスト
                        response = requests.get(direct_download_url, stream=True, timeout=30, allow_redirects=True)
                        response.raise_for_status()
                        current_content_type = response.headers.get('content-type', '').lower()
                        if 'text/html' in current_content_type:
                            logger.warning(f"Google DriveからHTMLが返されました (Content-Type: {current_content_type})。URL: {direct_download_url}. 元のURLでの処理を試みます。")
                            # HTMLが返された場合は元のURLで取得し直す
                            response = requests.get(original_media_url, stream=True, timeout=30)
                            response.raise_for_status()
                    else:
                        logger.warning(f"Google DriveのファイルID抽出に失敗しました: {media_url}")
                        # ファイルIDが取れなければ元のresponseで続行 (既に取得済み)

                except requests.exceptions.RequestException as e_gdrive:
                    logger.error(f"Google Drive直接ダウンロードURLからの取得/処理に失敗: {e_gdrive}。元のURLで試行します。")
                    response = requests.get(original_media_url, stream=True, timeout=30)
                    response.raise_for_status()
                except Exception as e_general:
                    logger.error(f"Google Driveリンク処理中に予期せぬエラー: {e_general}。元のURLで試行します。")
                    response = requests.get(original_media_url, stream=True, timeout=30)
                    response.raise_for_status()
            
            try:
                media_content = response.content # 全コンテンツをメモリに読み込む
                content_type = response.headers.get('content-type', '').lower()
                logger.debug(f"取得したContent-Type: '{content_type}' (URL: {response.url})")

            except Exception as e_content:
                logger.error(f"レスポンスコンテンツの読み込みに失敗: {e_content}")
                return None

            # ファイル拡張子を決定
            # mimetypesを使ってContent-Typeから拡張子を推測
            guessed_extension = mimetypes.guess_extension(content_type.split(';')[0])
            base_file_name = os.path.basename(original_media_url.split('?')[0])
            original_extension = os.path.splitext(base_file_name)[1].lower()

            # 適切な拡張子を選択 (mimetypesの結果を優先、なければ元のURLから)
            file_extension = guessed_extension if guessed_extension else original_extension
            if not file_extension: # それでもなければデフォルト
                if 'video' in content_type:
                    file_extension = '.mp4'
                elif 'gif' in content_type:
                    file_extension = '.gif'
                else:
                    file_extension = '.jpg' # デフォルト
            
            # 一時ファイル名のプレフィックス (拡張子なし)
            file_name_prefix = os.path.splitext(base_file_name)[0] if '.' in base_file_name else base_file_name
            
            media_category = None
            is_video = False

            if 'image/gif' in content_type:
                media_category = 'tweet_gif'
            elif 'image/' in content_type:
                media_category = 'tweet_image'
            elif 'video/mp4' in content_type or (file_extension == '.mp4' and 'video' in content_type):
                media_category = 'tweet_video'
                is_video = True
            elif 'video/' in content_type: # mp4以外のvideoタイプも考慮
                 media_category = 'tweet_video'
                 is_video = True
                 if not file_extension.startswith('.'):
                     file_extension = '.' + content_type.split('/')[-1] # video/quicktime -> .quicktime
                 if file_extension == '.mov': # .movはTwitterでサポートされない場合があるので注意喚起
                     logger.warning("Content-Typeまたはファイル名が .mov (video/quicktime) です。Twitterでの互換性に注意してください。")

            elif 'application/octet-stream' in content_type or not content_type:
                logger.warning(f"Content-Typeが '{content_type}' のため、ファイル拡張子 '{file_extension}' から推測します。")
                if file_extension in ['.mp4', '.mov']:
                    media_category = 'tweet_video'
                    is_video = True
                    if file_extension == '.mov': logger.warning("拡張子が .mov です。Twitterでの互換性に注意してください。")
                elif file_extension in ['.jpg', '.jpeg', '.png']:
                    media_category = 'tweet_image'
                elif file_extension == '.gif':
                    media_category = 'tweet_gif'
                else:
                    logger.warning(f"拡張子 '{file_extension}' からもメディアタイプを特定できませんでした。デフォルトで画像として扱います。")
                    media_category = 'tweet_image'
            else:
                logger.warning(f"不明なContent-Type: {content_type}。ファイル拡張子 '{file_extension}' から推測し、デフォルトで画像として扱います。")
                media_category = 'tweet_image' # デフォルト

            logger.debug(f"判定後の media_category: '{media_category}', is_video: {is_video}, file_extension: {file_extension}")

            temp_file_path = None # 元のダウンロードされた一時ファイル
            modified_temp_file_path = None # ffmpegで処理された後の一時ファイル

            try: # Inner try for file processing and upload
                # 一時ファイルを作成 (正しい拡張子を付ける)
                with tempfile.NamedTemporaryFile(delete=False, prefix=file_name_prefix + '_', suffix=file_extension) as temp_f:
                    temp_f.write(media_content)
                    temp_file_path = temp_f.name
                
                upload_target_path = temp_file_path # アップロード対象のパス（デフォルトは元のファイル）

                # 動画の場合、ffmpegでメタデータを変更する
                if is_video and temp_file_path:
                    logger.info(f"動画ファイル ({temp_file_path}) のメタデータ変更を試みます...")
                    modified_temp_file_path = self._modify_video_metadata_ffmpeg(temp_file_path)
                    if modified_temp_file_path:
                        logger.info(f"メタデータ変更成功。アップロードには変更後ファイルを使用: {modified_temp_file_path}")
                        upload_target_path = modified_temp_file_path
                    else: # このelseは if modified_temp_file_path: に対応
                        logger.warning(f"動画メタデータの変更に失敗。元のファイルでアップロードを続行します: {temp_file_path}")
                
                # 上記のifブロックが終わった後 (動画処理が終わった後、または動画でなかった場合)
                logger.info(f"メディアを一時ファイル {upload_target_path} に保存し、Twitterにアップロード中 (カテゴリ: {media_category or '未指定'}, メディアタイプ: {content_type})...")

                uploaded_media = self.api_v1.media_upload(
                    filename=upload_target_path, 
                    media_category=media_category,
                    chunked=is_video # 動画の場合はチャンクアップロードを有効にする
                )
                logger.info(f"メディアのアップロード成功。Media ID: {uploaded_media.media_id_string}")
                return uploaded_media.media_id_string

            except Exception as e_upload: # This except corresponds to the inner try
                logger.error(f"メディアアップロード処理中の予期せぬエラー: {e_upload}", exc_info=True)
                pass 

            finally: # This finally corresponds to the inner try
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                        logger.debug(f"一時ファイル {temp_file_path} を削除しました。")
                    except OSError as e_remove:
                        logger.error(f"一時ファイル {temp_file_path} の削除に失敗: {e_remove}")
                if modified_temp_file_path and os.path.exists(modified_temp_file_path):
                    try:
                        os.remove(modified_temp_file_path)
                        logger.debug(f"ffmpeg処理後の一時ファイル {modified_temp_file_path} を削除しました。")
                    except OSError as e_remove_mod:
                        logger.error(f"ffmpeg処理後の一時ファイル {modified_temp_file_path} の削除に失敗: {e_remove_mod}")
                # If an error occurred in the try block above, and we didn't return a media_id,
                # _upload_media_v1 needs to return None.
                # This will be caught by the outer try-except structure if an error was raised from inner 'except'
                # or if we simply fall through.

        except tweepy.TweepyException as e: # This is for Tweepy specific errors outside the inner file processing try-catch
            logger.error(f"Twitterへのメディアアップロード失敗 (TweepyException): {e}", exc_info=True) # Clarified log
            if isinstance(e, tweepy.errors.Forbidden):
                logger.error("Forbidden (403)エラー。APIキーの権限、アプリの承認状態、またはTwitterのルール違反を確認してください。")
            # No separate 'except Exception as e_upload:' here, as that was for the inner try.
            # Any other TweepyException will just be logged and lead to returning None.
            return None # Return None for any TweepyException here

        except requests.exceptions.RequestException as e_req:
            logger.error(f"メディアURLからのダウンロードまたはGoogle Drive処理で失敗: {original_media_url}, Error: {e_req}", exc_info=True)
            return None
        except Exception as e_outer:
            logger.error(f"メディア処理の全体的な予期せぬエラー: {e_outer}", exc_info=True)
            return None

    def post_tweet(self, text: str, media_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """テキストとオプションでメディアIDリストを指定してツイートを投稿する (v2 API)。"""
        if not self.client_v2:
            logger.error("Twitter API v2クライアントが初期化されていません。ツイートを投稿できません。")
            return None
        
        try:
            logger.info(f"ツイート投稿開始: Text='{text[:30]}...', Media IDs={media_ids}")
            kwargs = {"text": text}
            if media_ids:
                kwargs["media_ids"] = media_ids
            
            response = self.client_v2.create_tweet(**kwargs)
            # response は tweepy.Response オブジェクトで、data, includes, errors, meta などの属性を持つ
            # response.data は投稿されたツイートの情報 (id, textなど) を含むdict
            if response.data and response.data.get("id"):
                logger.info(f"ツイート投稿成功。Tweet ID: {response.data['id']}, Text: {response.data['text']}")
                return response.data # dictを返す
            else:
                logger.error(f"ツイート投稿は成功しましたが、レスポンスデータが不正です: {response}")
                if response.errors:
                    logger.error(f"APIエラー詳細: {response.errors}")
                return None

        except tweepy.TweepyException as e:
            logger.error(f"ツイート投稿失敗: {e}", exc_info=True)
            if isinstance(e, tweepy.errors.TooManyRequests):
                rate_limit_details = self._get_rate_limit_info_from_exception(e)
                reset_at = rate_limit_details.get("reset_at_utc")
                remaining_sec = rate_limit_details.get("remaining_seconds")
                # ログメッセージは _get_rate_limit_info_from_exception 内で出力されるのでここでは不要
                raise RateLimitError(message=str(e), reset_at_utc=reset_at, remaining_seconds=remaining_sec)
            elif isinstance(e, tweepy.errors.Forbidden):
                logger.error("Forbidden (401/403)エラー。APIキー、アクセストークンの有効性、権限、またはTwitterのルール違反を確認してください。")
            
            # 上記以外のTweepyExceptionや、Forbiddenの場合も（当面は）Noneを返す
            return None
        except Exception as e:
            logger.error(f"ツイート投稿中の予期せぬエラー: {e}", exc_info=True)
            return None

    def post_with_media_url(self, text: str, media_url: Optional[str]) -> Optional[Dict[str, Any]]:
        """メディアURLを指定して、ダウンロード・アップロード後にツイートする統合メソッド。"""
        media_id_list = None
        if media_url:
            logger.info(f"メディアURL付き投稿: {media_url}")
            uploaded_media_id = self._upload_media_v1(media_url)
            if uploaded_media_id:
                media_id_list = [uploaded_media_id]
            else:
                logger.warning("メディアのアップロードに失敗したため、メディアなしで投稿を試みます。")
                # メディアアップロード失敗時はテキストのみで投稿を試みる
        
        return self.post_tweet(text, media_ids=media_id_list)

    def post_reply(self, text: str, in_reply_to_tweet_id: str, media_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """指定されたツイートにリプライを投稿する (v2 API)。"""
        if not self.client_v2:
            logger.error("Twitter API v2 クライアントが初期化されていません。リプライを投稿できません。")
            return None

        logger.info(f"リプライ投稿開始: Text='{text[:30]}...', InReplyTo='{in_reply_to_tweet_id}', MediaIDs={media_ids}")
        
        actual_media_ids_for_api = media_ids if media_ids else None

        # create_tweet に渡す引数を準備
        kwargs = {
            "text": text,
        }
        if actual_media_ids_for_api:
            kwargs["media_ids"] = actual_media_ids_for_api
        
        # 'reply' という不正な引数ではなく、'in_reply_to_tweet_id' を直接渡す
        kwargs["in_reply_to_tweet_id"] = in_reply_to_tweet_id
        
        # User Context認証が必要な場合は user_auth=True を指定。
        # デフォルトではApp Contextで動作しようとする可能性があるため、明示的にUser Contextを指定する。
        # ただし、tweepy.Clientがconsumer_key等で初期化されていれば、
        # create_tweetはUser Contextで動作するはず。念のため。
        # kwargs["user_auth"] = True # tweepyのClientの初期化方法によっては不要かもしれない

        try:
            # response = self.client_v2.create_tweet(**kwargs) # 修正前
            response = self.client_v2.create_tweet( # 修正後: 引数を展開せず、必須のものとin_reply_to_tweet_idを明示的に渡す
                text=text,
                in_reply_to_tweet_id=in_reply_to_tweet_id,
                media_ids=actual_media_ids_for_api
                # user_auth=True # こちらにも適用
            )

            if response and response.data:
                logger.info(f"リプライ投稿成功。Tweet ID: {response.data['id']}, Text: {response.data['text'][:30]}...")
                return {"id": response.data["id"], "text": response.data["text"]}
            else:
                logger.error("リプライ投稿後、APIからのレスポンスが不正です。")
                return None

        except tweepy.errors.Forbidden as e: # 403 Forbidden
            rate_limit_details = self._get_rate_limit_info_from_exception(e)
            error_message = f"リプライ投稿失敗 (403 Forbidden): {str(e)}. Details: {rate_limit_details['raw_info']}"
            logger.error(error_message, exc_info=True)
            # RateLimitErrorをraiseしない (Forbiddenは必ずしもレート制限ではないため)
            # ただし、ヘッダーにレート制限情報があればRateLimitErrorを発生させてもよい
            if "x-rate-limit-remaining" in e.response.headers and e.response.headers["x-rate-limit-remaining"] == "0":
                 raise RateLimitError(
                    message=f"リプライ投稿中にAPIレート制限 (403 Forbidden): {str(e)}",
                    reset_at_utc=rate_limit_details.get('reset_at_utc'),
                    remaining_seconds=rate_limit_details.get('remaining_seconds')
                )
            # それ以外の403エラーはそのまま失敗として処理
            return None
        except tweepy.errors.TooManyRequests as e: # 429 Too Many Requests
            rate_limit_details = self._get_rate_limit_info_from_exception(e)
            raise RateLimitError(
                message=f"リプライ投稿中にAPIレート制限 (429 Too Many Requests): {str(e)}",
                reset_at_utc=rate_limit_details.get('reset_at_utc'),
                remaining_seconds=rate_limit_details.get('remaining_seconds')
            )
        except tweepy.errors.TweepyException as e:
            # ここでTweepyExceptionをキャッチする前に、より具体的な例外 (例: BadRequest) を上に書くことも検討
            logger.error(f"リプライ投稿中に予期せぬTweepyエラー: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"リプライ投稿中に予期せぬ一般エラー: {e}", exc_info=True)
            return None

    def delete_tweet(self, tweet_id: str) -> bool:
        """指定されたIDのツイートを削除する (v2 API)。成功すればTrueを返す。"""
        if not self.client_v2:
            logger.error("Twitter API v2 クライアントが初期化されていません。ツイートを削除できません。")
            return False
        
        try:
            logger.info(f"ツイート削除開始: ID={tweet_id}")
            response = self.client_v2.delete_tweet(id=tweet_id)
            if response and response.data and response.data.get('deleted') is True:
                logger.info(f"ツイート削除成功: ID={tweet_id}")
                return True
            else:
                # 削除失敗時、response.data が存在しない場合や、response.data['deleted'] が False の場合がある
                # response.errors も確認すると良い
                error_detail = "不明な理由"
                if response and response.errors:
                    error_detail = str(response.errors)
                elif response and response.data: # dataはあるがdeletedではない場合
                    error_detail = f"API応答 data={response.data}"

                logger.error(f"ツイート削除失敗: ID={tweet_id}. Detail: {error_detail}. RawResponse: {response}")
                return False
        except tweepy.errors.TooManyRequests as e_429:
            logger.warning(f"ツイート削除中にレート制限 (429 Too Many Requests): {e_429}")
            # 削除処理でのレート制限は致命的ではないかもしれないので、エラーをraiseせずFalseを返すことも検討
            # ここでは一旦RateLimitErrorをraiseする (呼び出し側でハンドリングを期待)
            rate_limit_details = self._get_rate_limit_info_from_exception(e_429)
            raise RateLimitError(
                message=f"Twitter APIレート制限 (ツイート削除): {e_429}",
                reset_at_utc=rate_limit_details.get("reset_at_utc"),
                remaining_seconds=rate_limit_details.get("remaining_seconds")
            )
        except tweepy.errors.Forbidden as e_403: # 自分のツイートでない、または権限不足
            logger.error(f"ツイート削除中に権限エラー (403 Forbidden): {e_403}. 対象ツイートの所有権やアプリ権限を確認してください。 ID={tweet_id}, Response: {e_403.response.text if e_403.response else 'N/A'}", exc_info=True)
            return False
        except tweepy.errors.NotFound as e_404: # ツイートが存在しない
            logger.warning(f"削除対象のツイートが見つかりませんでした (404 Not Found): ID={tweet_id}")
            return False # 見つからない場合は、ある意味「削除済み」とも言えるのでTrueを返すか議論の余地あり。ここではFalse。
        except tweepy.errors.TweepyException as e:
            logger.error(f"ツイート削除中に予期せぬTweepyエラー: {e}. ID={tweet_id}", exc_info=True)
            return False
        except Exception as e_general:
            logger.error(f"ツイート削除中に予期せぬ一般エラー: {e_general}. ID={tweet_id}", exc_info=True)
            return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger.info("TwitterClientのテストを開始します。")

    # テストには実際のAPIキーとアクセストークンが必要です。
    # 環境変数やconfigファイルから読み込むことを推奨します。
    # ここではデモ用にプレースホルダを使用します。
    # 重要：実際のキーをコードにハードコーディングしないでください。
    try:
        # Configからキーを取得する例 (ただし、Configのパス解決がこのファイルの場所に依存しないように注意)
        # このテストは engine_core のルートで python -m engine_core.twitter のように実行することを想定
        from config import Config # プロジェクトルートのconfigを想定
        project_root_for_config = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_instance = Config(config_path=os.path.join(project_root_for_config, "config/config.yml"))
        
        active_account_id = config_instance.get("testing.default_twitter_account_id", "ZaikerLong") # config.ymlに追記想定
        account_details = config_instance.get_active_twitter_account_details(active_account_id)

        if not account_details:
            logger.error(f"テスト用アカウント '{active_account_id}' の設定がconfig.ymlに見つかりません。テストをスキップします。")
        else:
            client = TwitterClient(
                consumer_key=account_details['consumer_key'],
                consumer_secret=account_details['consumer_secret'],
                access_token=account_details['access_token'],
                access_token_secret=account_details['access_token_secret'],
                bearer_token=account_details.get('bearer_token') # Optional
            )
            
            logger.info("テキストのみのツイートテスト...")
            # タイムスタンプを付与して毎回異なる内容にする
            text_tweet_content = f"これは #TwitterClient から ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) のテスト投稿です。"
            tweet_response_text_only = client.post_tweet(text_tweet_content)
            if tweet_response_text_only:
                logger.info(f"テキストツイート成功: ID {tweet_response_text_only.get('id')}")
            else:
                logger.error("テキストツイート失敗。")

            logger.info("画像URL付きツイートテスト...")
            # テスト用の画像URL (著作権フリーのものを推奨)
            # 例: Placeholder.com の画像
            test_image_url = config_instance.get("testing.test_image_url", "https://via.placeholder.com/640x480.png?text=Test+Image")
            image_tweet_content = f"これはテスト画像付き投稿です！ ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) #Python #Tweepy"
            
            tweet_response_with_image = client.post_with_media_url(image_tweet_content, test_image_url)
            if tweet_response_with_image:
                logger.info(f"画像付きツイート成功: ID {tweet_response_with_image.get('id')}")
            else:
                logger.error("画像付きツイート失敗。")
            
            # TODO: 動画のテストは適切なURLとファイル処理が必要なため、ここでは省略
            # logger.info("動画URL付きツイートテスト...")
            # test_video_url = config_instance.get("testing.test_video_url", "ここにテスト用MP4動画URL")
            # video_tweet_content = f"これはテスト動画付き投稿！ ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) #VideoTest"
            # tweet_response_with_video = client.post_with_media_url(video_tweet_content, test_video_url)
            # if tweet_response_with_video:
            #     logger.info(f"動画付きツイート成功: ID {tweet_response_with_video.get('id')}")
            # else:
            #     logger.error("動画付きツイート失敗。")

    except ImportError as e:
        logger.error(f"Configモジュールが見つかりません。engine_coreのルートからテストを実行してください。 ex: python -m engine_core.twitter. エラー詳細: {e}")
    except ValueError as ve:
        logger.error(f"設定エラーまたはキーエラー: {ve}")
    except Exception as e:
        logger.error(f"TwitterClientのテスト中に予期せぬエラー: {e}", exc_info=True) 