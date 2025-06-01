import tweepy
import logging
import os
import requests
import time
from typing import Optional, Dict, Any, List # List を追加
from datetime import datetime # datetime を追加

# このモジュールがengine_coreパッケージ内にあることを想定してConfigをインポート
# ただし、TwitterClient自体はConfigに直接依存せず、キーは外部から渡される想定
# from .config import Config # 通常はWorkflow層などでConfigからキーを取得して渡す

logger = logging.getLogger(__name__)

# Twitter API v1.1 (メディアアップロード用)
MEDIA_ENDPOINT_URL_V1 = 'https://upload.twitter.com/1.1/media/upload.json'
# Twitter API v2 (ツイート投稿用)
# (tweepy.Clientが内部的にv2エンドポイントを使用する)

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
                wait_on_rate_limit=True
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
            self.api_v1 = tweepy.API(auth_v1, wait_on_rate_limit=True)
            logger.info("Twitter API v1.1 ハンドラの初期化に成功しました。")
        except Exception as e:
            logger.error(f"Twitter API v1.1 ハンドラの初期化に失敗: {e}", exc_info=True)
            # v1.1の認証が失敗するとメディアアップロードができないので、これは致命的
            raise ValueError(f"Twitter API v1.1 auth failed: {e}")

    def _upload_media_v1(self, media_url: str) -> Optional[str]:
        """指定されたURLのメディアをTwitterにアップロードし、メディアIDを返す (v1.1 API)。"""
        if not self.api_v1:
            logger.error("Twitter API v1.1が初期化されていません。メディアをアップロードできません。")
            return None
        
        try:
            logger.info(f"メディアURLからデータをダウンロード開始: {media_url}")
            response = requests.get(media_url, stream=True)
            response.raise_for_status() # HTTPエラーチェック
            
            # ファイル名と拡張子を仮に決定 (Content-Typeからより正確に判定も可能)
            file_name = os.path.basename(media_url.split('?')[0]) # クエリパラメータを除外
            if '.' not in file_name: # 拡張子がない場合はデフォルトで.jpgを試す
                file_name += ".jpg"

            # Tweepyのメディアアップロード機能を利用
            # videoの場合はmedia_category='tweet_video'が必要になることがある
            # ここではシンプルに画像とGIFを想定
            # チャンクアップロードが必要な大きなファイルには upload_chunked を使用

            # Content-Typeに基づいてメディアカテゴリを推測
            content_type = response.headers.get('content-type', '').lower()
            media_category = None
            is_video = False

            if 'image/gif' in content_type:
                media_category = 'tweet_gif'
            elif 'image/' in content_type: # jpg, pngなど
                media_category = 'tweet_image'
            elif 'video/mp4' in content_type: # 簡単な例としてMP4のみ対応
                media_category = 'tweet_video'
                is_video = True
            else:
                logger.warning(f"不明なContent-Type: {content_type}。メディアカテゴリを推測できません。アップロードを試みますが失敗する可能性があります。")

            logger.info(f"メディアをTwitterにアップロード中 (ファイル名: {file_name}, カテゴリ: {media_category or '未指定'})...")
            
            # requestsのレスポンスから直接ファイルオブジェクトとして渡す
            # Tweepyはファイルライクオブジェクトを受け付ける
            if is_video:
                 # 動画はチャンクアップロードが必要な場合が多い
                 # Tweepy v4.x では media_upload はファイルパスを期待する。ファイルライクオブジェクトは非推奨。
                 # 一時ファイルに保存してからパスを渡す方法が確実。
                with open(file_name, 'wb') as f_temp:
                    for chunk in response.raw.stream(decode_content=True):
                        f_temp.write(chunk)
                logger.debug(f"メディアを一時ファイル {file_name} に保存しました。")
                
                # チャンクアップロード (ファイルサイズによってはこちらが適切)
                # Tweepyの upload_chunked はファイルパスを引数にとる
                uploaded_media = self.api_v1.media_upload(filename=file_name, media_category=media_category, chunked=True)
                os.remove(file_name) # 一時ファイルを削除
                logger.debug(f"一時ファイル {file_name} を削除しました。")
            else:
                # 画像やGIFの場合
                uploaded_media = self.api_v1.media_upload(filename=file_name, file=response.raw, media_category=media_category)

            logger.info(f"メディアのアップロード成功。Media ID: {uploaded_media.media_id_string}")
            return uploaded_media.media_id_string

        except requests.exceptions.RequestException as e:
            logger.error(f"メディアURLからのダウンロード失敗: {media_url}, Error: {e}", exc_info=True)
            return None
        except tweepy.TweepyException as e:
            logger.error(f"Twitterへのメディアアップロード失敗: {e}", exc_info=True)
            # tweepy.errors.Forbidden の場合は403エラーで、キーの権限問題やAPIルールの可能性
            if isinstance(e, tweepy.errors.Forbidden):
                logger.error("Forbidden (403)エラー。APIキーの権限、アプリの承認状態、またはTwitterのルール違反を確認してください。")
            return None
        except Exception as e:
            logger.error(f"メディアアップロード中の予期せぬエラー: {e}", exc_info=True)
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
            # tweepy.errors.Forbidden の場合は401/403エラーで、認証や権限問題の可能性
            if isinstance(e, tweepy.errors.Forbidden):
                logger.error("Forbidden (401/403)エラー。APIキー、アクセストークンの有効性、権限、またはTwitterのルール違反を確認してください。")
            elif isinstance(e, tweepy.errors.TooManyRequests): # 429 Rate Limit
                 logger.error("レート制限超過 (429)。しばらく待ってから再試行してください。")
            # 他のTweepyExceptionもここでキャッチされる
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