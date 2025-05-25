import os
import sys
import requests
import json
import tweepy
import time # timeモジュールをインポート
from typing import List

# プロジェクトルートをsys.pathに追加 (configモジュール等をインポートするため)
# このファイルの場所 (bots/extract_tweets_bot/) からプロジェクトルートへの相対パスを解決
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from config import config_loader # プロジェクトルートのconfigモジュールから
import logging

# ロガー設定 (このモジュール用のロガー)
logger = logging.getLogger(__name__) # __name__ は bots.extract_tweets_bot.twitter_api_client になるはず
if not logger.handlers: # ハンドラが重複しないように
    handler = logging.StreamHandler()
    # TODO: ログフォーマットはプロジェクト全体で統一するか、設定可能に
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO) # デフォルトのログレベル

# X API v2 エンドポイント (App Context用)
API_BASE_URL_V2 = "https://api.twitter.com/2"

# レート制限に関するデフォルト値
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 60  # 429エラー時の基本待機時間
MIN_REQUEST_INTERVAL_SECONDS = 1 # 通常のリクエスト間の最小間隔

class TwitterApiClient: # クラス名を変更
    def __init__(self, bot_name="extract_tweets_bot"): # デフォルトのボット名を変更
        self.bot_name = bot_name # どのボットから呼ばれたかの識別に使う
        self.config = config_loader.get_full_config()
        if not self.config:
            logger.error(f"❌ ({self.bot_name}) 設定ファイルの読み込みに失敗しました。TwitterApiClientは機能しません。")
            # 呼び出し元でNoneチェックなどをしてもらうために、ここでは例外を送出しないでおくか、
            # あるいは特定の例外を送出するかは設計次第。
            # ここでは、以降の処理で client が None のままになるので、それを利用側がハンドルすることを期待。
            self.twitter_api_config = {}
        else:
            self.twitter_api_config = self.config.get("twitter_api", {})

        # User Context (OAuth 1.0a) クライアントの初期化
        self.consumer_key = self.twitter_api_config.get("consumer_key")
        self.consumer_secret = self.twitter_api_config.get("consumer_secret")
        self.access_token = self.twitter_api_config.get("access_token")
        self.access_token_secret = self.twitter_api_config.get("access_token_secret")
        
        self.client_v2_user_context = None # User Context v2 API クライアント

        if self.consumer_key and self.consumer_secret and self.access_token and self.access_token_secret:
            try:
                self.client_v2_user_context = tweepy.Client(
                    consumer_key=self.consumer_key,
                    consumer_secret=self.consumer_secret,
                    access_token=self.access_token,
                    access_token_secret=self.access_token_secret
                )
                logger.info(f"✅ ({self.bot_name}) Tweepy Client (User Context) の初期化に成功しました。")
            except Exception as e:
                logger.error(f"❌ ({self.bot_name}) Tweepy Client (User Context) の初期化中にエラー: {e}", exc_info=True)
        else:
            # 投稿機能だけでなく、User Contextでの情報取得もできなくなる
            logger.warning(f"⚠️ ({self.bot_name}) User Contextに必要なTwitter APIキー (Consumer/Access Token) がconfigに設定されていません。User Context API機能は利用できません。")

        # App Context (Bearer Token) の準備
        self.bearer_token = self.twitter_api_config.get("bearer_token")
        self.headers_app_context = None
        if self.bearer_token and self.bearer_token != "YOUR_BEARER_TOKEN_HERE":
            self.headers_app_context = {
                "Authorization": f"Bearer {self.bearer_token}"
            }
        else:
            logger.warning(f"⚠️ ({self.bot_name}) Bearer Tokenが未設定または初期値のままです。App Context API機能（ツイート取得など）に支障が出る可能性があります。")

        # レート制限状態の管理用変数 (App Context用)
        self.rate_limit_remaining = None
        self.rate_limit_reset_timestamp = None
        self.last_request_time_app_context = 0

    def _update_rate_limit_info(self, response_headers):
        if 'x-rate-limit-remaining' in response_headers:
            self.rate_limit_remaining = int(response_headers['x-rate-limit-remaining'])
        if 'x-rate-limit-reset' in response_headers:
            self.rate_limit_reset_timestamp = int(response_headers['x-rate-limit-reset'])
        # logger.debug(f"Rate limit updated: Remaining={self.rate_limit_remaining}, ResetAtEpoch={self.rate_limit_reset_timestamp}")

    def _wait_if_needed(self):
        # 1. 前回のApp Context APIリクエストからの経過時間を確認
        current_time = time.time()
        elapsed_since_last_request = current_time - self.last_request_time_app_context
        if elapsed_since_last_request < MIN_REQUEST_INTERVAL_SECONDS:
            wait_time = MIN_REQUEST_INTERVAL_SECONDS - elapsed_since_last_request
            logger.debug(f"Minimum request interval not met. Waiting for {wait_time:.2f} seconds.")
            time.sleep(wait_time)

        # 2. APIのレート制限情報を確認
        if self.rate_limit_remaining is not None and self.rate_limit_remaining <= 1: # 余裕をもって1以下で待機
            if self.rate_limit_reset_timestamp is not None:
                wait_until = self.rate_limit_reset_timestamp
                wait_duration = max(0, wait_until - time.time()) + 1 # リセット時刻後1秒余裕をもつ
                if wait_duration > 0:
                    logger.warning(f"Rate limit nearly exceeded (Remaining: {self.rate_limit_remaining}). Waiting for {wait_duration:.2f} seconds until reset.")
                    time.sleep(wait_duration)
                    # 待機後はレート情報を一旦リセットして再取得を促す（次のレスポンスで更新される）
                    self.rate_limit_remaining = None 
                    self.rate_limit_reset_timestamp = None
            else:
                # リセット時刻が不明な場合はデフォルト時間待機 (稀なケース)
                logger.warning(f"Rate limit nearly exceeded (Remaining: {self.rate_limit_remaining}), but reset time is unknown. Waiting for {DEFAULT_RETRY_DELAY_SECONDS} seconds.")
                time.sleep(DEFAULT_RETRY_DELAY_SECONDS)
        self.last_request_time_app_context = time.time()

    def _send_api_request(self, method: str, url: str, headers: dict, params: dict = None, data: dict = None, json_payload: dict = None):
        if not self.bearer_token or self.bearer_token == "YOUR_BEARER_TOKEN_HERE":
            logger.error(f"❌ ({self.bot_name}) Bearer Tokenが無効です。APIリクエストを送信できません。")
            return None

        attempt = 0
        while attempt < DEFAULT_RETRY_ATTEMPTS:
            self._wait_if_needed() # APIコール前にレート制限を確認・待機
            
            try:
                response = requests.request(method, url, headers=headers, params=params, data=data, json=json_payload, timeout=30)
                self._update_rate_limit_info(response.headers) # レスポンスヘッダーからレート情報を更新
                
                response.raise_for_status() # HTTPエラーステータスコードの場合は例外を発生させる
                
                # 成功時
                try:
                    return response.json()
                except json.JSONDecodeError as e_json_decode:
                    logger.error(f"❌ ({self.bot_name}) APIレスポンスのJSONデコードに失敗しました。URL: {url}, Response text: {response.text[:200]}, Error: {e_json_decode}")
                    return None # あるいは response.text を返すか検討

            except requests.exceptions.HTTPError as e_http:
                if e_http.response.status_code == 429: # Too Many Requests
                    reset_time_from_header = e_http.response.headers.get('x-rate-limit-reset')
                    wait_seconds = DEFAULT_RETRY_DELAY_SECONDS
                    if reset_time_from_header:
                        wait_seconds = max(0, int(reset_time_from_header) - time.time()) + 1 # 1秒余裕
                    
                    self.rate_limit_remaining = 0 # 強制的に0に
                    self.rate_limit_reset_timestamp = int(reset_time_from_header) if reset_time_from_header else time.time() + wait_seconds

                    logger.warning(f"❌ ({self.bot_name}) APIレート制限超過 (429)。{wait_seconds:.2f}秒待機後にリトライします... ({attempt + 1}/{DEFAULT_RETRY_ATTEMPTS}) URL: {url}")
                    time.sleep(wait_seconds)
                    attempt += 1
                    if attempt >= DEFAULT_RETRY_ATTEMPTS:
                        logger.error(f"❌ ({self.bot_name}) APIレート制限超過、最大リトライ回数({DEFAULT_RETRY_ATTEMPTS})に達しました。URL: {url}")
                        return None
                else: # その他のHTTPエラー
                    logger.error(f"❌ ({self.bot_name}) APIリクエストHTTPエラー: {e_http} URL: {url}")
                    if e_http.response is not None:
                         logger.error(f"  Response Status: {e_http.response.status_code}, Text: {e_http.response.text[:200]}")
                    return None # リトライせずに終了
            except requests.exceptions.RequestException as e_req: # タイムアウト、接続エラーなど
                logger.error(f"❌ ({self.bot_name}) APIリクエストエラー: {e_req} URL: {url}")
                # ネットワーク関連のエラーはリトライする価値があるかもしれない
                if attempt < DEFAULT_RETRY_ATTEMPTS -1 : # 最後のリトライでなければ少し待ってリトライ
                     time.sleep(5 * (attempt + 1)) # 試行回数に応じて待機時間を増やす
                attempt += 1
            except Exception as e_unexpected: # その他の予期せぬエラー
                logger.error(f"❌ ({self.bot_name}) APIリクエスト中に予期せぬエラー: {e_unexpected} URL: {url}", exc_info=True)
                return None # リトライせずに終了
        return None # リトライ回数超過

    def post_tweet(self, text_content: str, media_ids: list = None):
        """
        User Context (OAuth 1.0a) を使用してツイートを投稿する。
        Args:
            text_content (str): 投稿するテキスト。
            media_ids (list, optional): アップロード済みのメディアIDのリスト。
        Returns:
            dict: 投稿結果のレスポンスデータ。エラー時は None。
        """
        if not self.client_v2_user_context:
            logger.error(f"❌ ({self.bot_name}) Tweepy Client (User Context) が初期化されていません。投稿できません。")
            return None
        try:
            logger.info(f"({self.bot_name}) ツイート投稿中: \"{text_content[:50]}...\"")
            response = self.client_v2_user_context.create_tweet(
                text=text_content,
                media_ids=media_ids if media_ids else None
            )
            if response and response.data:
                tweet_id = response.data.get('id')
                tweet_text_response = response.data.get('text')
                logger.info(f"✅ ({self.bot_name}) ツイート投稿成功！ ID: {tweet_id}, Text: \"{tweet_text_response[:50]}...\"")
                return response.data
            else:
                err_msg = f"APIからのレスポンスが予期しない形式です。 Response: {response}"
                if hasattr(response, 'errors') and response.errors:
                    err_msg += f" エラー詳細: {response.errors}"
                logger.error(f"❌ ({self.bot_name}) ツイート投稿失敗。{err_msg}")
                return None
        except tweepy.TweepyException as e:
            logger.error(f"❌ ({self.bot_name}) TweepyException: ツイート投稿APIエラー: {e}", exc_info=True)
            if hasattr(e, 'api_errors') and e.api_errors: logger.error(f"  API Errors: {e.api_errors}")
            if hasattr(e, 'response') and e.response is not None:
                 logger.error(f"  Response Status: {e.response.status_code}")
                 logger.error(f"  Response Text: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ ({self.bot_name}) 予期せぬエラー(ツイート投稿): {e}", exc_info=True)
            return None

    def fetch_tweets_by_username_app_context(self, username: str, max_tweets_to_fetch: int = 100, until_id: Optional[str] = None, since_id: Optional[str] = None):
        """
        【App Context使用】指定ユーザーのツイートをAPI v2から取得 (ページネーション対応予定)。
        Args:
            username (str): 対象のTwitterユーザー名 (例: "elonmusk")
            max_tweets_to_fetch (int): 取得しようとする最大のツイート数。
            until_id (str, optional): このIDより古いツイートを取得 (ページネーション用)。
            since_id (str, optional): このIDより新しいツイートを取得 (最新からの差分取得用)。
        Returns:
            list: 取得したツイート情報のリスト。各要素はツイートの詳細辞書。
        """
        if not self.headers_app_context:
            logger.error(f"❌ ({self.bot_name}) Bearer Token未設定。App Contextでのツイート取得不可。")
            return []

        user_id = self._get_user_id_with_cache(username, self.headers_app_context)
        if not user_id:
            return []

        all_tweets_data = []
        pagination_token = None
        tweets_collected_count = 0
        
        # 1回のリクエストで取得できる最大件数は100 (API仕様)
        # ページネーションを考慮し、max_tweets_to_fetch に達するまでループ (またはトークンがなくなるまで)
        # ループあたりの取得件数は、残り必要数とAPI上限の小さい方
        
        while tweets_collected_count < max_tweets_to_fetch:
            results_per_page = min(max(5, max_tweets_to_fetch - tweets_collected_count), 100)
            if results_per_page <= 0: # もう取得する必要がない
                 break

            tweets_url = f"{API_BASE_URL_V2}/users/{user_id}/tweets"
            params = {
                "max_results": results_per_page,
                "tweet.fields": "created_at,text,public_metrics,entities,author_id", # author_idを追加
                "expansions": "attachments.media_keys,author_id", # author_idをexpansionに追加
                "media.fields": "url,preview_image_url,type,variants,width,height,alt_text,media_key", # media_keyも追加
                # "user.fields": "username,name" # author_idのexpansionでユーザー情報取得
            }
            if pagination_token:
                params["pagination_token"] = pagination_token
            if until_id and not pagination_token: # 初回リクエスト時のみ until_id を考慮
                params["until_id"] = until_id
            if since_id and not pagination_token: # 初回リクエスト時のみ since_id を考慮
                params["since_id"] = since_id
            
            logger.info(f"({self.bot_name}) ユーザー '{username}' (ID: {user_id}) のツイート取得中 (App Context, {tweets_collected_count}件取得済み, 次の{params['max_results']}件, PaginationToken: {pagination_token})...")
            
            tweets_response = self._send_api_request("GET", tweets_url, headers=self.headers_app_context, params=params)

            if not tweets_response: # APIリクエスト失敗 (リトライ含む)
                logger.error(f"❌ ({self.bot_name}) ユーザー '{username}' のツイート取得中にAPIリクエストが最終的に失敗しました。")
                break # ループを抜ける

            raw_tweets = tweets_response.get("data", [])
            includes_data = tweets_response.get("includes", {})
            includes_media = includes_data.get("media", [])
            includes_users = includes_data.get("users", []) # ユーザー情報も取得
            
            media_dict = {media["media_key"]: media for media in includes_media}
            user_dict = {user["id"]: user for user in includes_users} # ユーザー情報を辞書化

            if not raw_tweets:
                logger.info(f"✅ ({self.bot_name}) ユーザー '{username}' のツイートはこれ以上ありません (または指定範囲にデータなし)。")
                break

            for tweet in raw_tweets:
                author_id_from_tweet = tweet.get("author_id") # ツイートデータからauthor_idを取得
                author_info = user_dict.get(author_id_from_tweet, {}) # includesからユーザー情報を参照

                tweet_info = {
                    "id": tweet.get("id"), "text": tweet.get("text"), "created_at": tweet.get("created_at"),
                    "author_id": author_id_from_tweet, 
                    "author_username": author_info.get("username"),
                    "author_name": author_info.get("name"),
                    "public_metrics": tweet.get("public_metrics"),
                    "entities": tweet.get("entities"), "media": []
                }
                if "attachments" in tweet and "media_keys" in tweet["attachments"]:
                    for media_key in tweet["attachments"]["media_keys"]:
                        if media_key in media_dict:
                            media_item = media_dict[media_key]
                            media_url = media_item.get("url") 
                            if media_item.get("type") in ["video", "animated_gif"] and "variants" in media_item:
                                best_variant = None; max_bit_rate = -1 # -1にして確実に更新されるように
                                for variant in media_item.get("variants", []):
                                    if variant.get("content_type") == "video/mp4":
                                        current_bit_rate = variant.get("bit_rate", 0)
                                        if current_bit_rate > max_bit_rate: # よりビットレートが高いものを選択
                                            max_bit_rate = current_bit_rate
                                            best_variant = variant
                                if best_variant: media_url = best_variant.get("url")
                            
                            tweet_info["media"].append({
                                "media_key": media_key, "type": media_item.get("type"), "url": media_url,
                                "preview_image_url": media_item.get("preview_image_url"), 
                                "alt_text": media_item.get("alt_text"), "width": media_item.get("width"), 
                                "height": media_item.get("height")
                            })
                all_tweets_data.append(tweet_info)
                tweets_collected_count += 1
                if tweets_collected_count >= max_tweets_to_fetch:
                    break # 目標数に達したら内部ループも抜ける
            
            if tweets_collected_count >= max_tweets_to_fetch:
                logger.info(f"✅ ({self.bot_name}) 目標の {max_tweets_to_fetch} 件のツイート情報取得完了。")
                break

            pagination_token = tweets_response.get("meta", {}).get("next_token")
            if not pagination_token:
                logger.info(f"✅ ({self.bot_name}) これ以上取得できるツイートがありません (next_tokenなし)。")
                break
            
            # MIN_REQUEST_INTERVAL_SECONDS は _send_api_request 内で考慮されるのでここでは不要
            # time.sleep(MIN_REQUEST_INTERVAL_SECONDS) # API負荷軽減のため少し待つ (ページネーション時)

        logger.info(f"✅ ({self.bot_name}) ユーザー '{username}' から合計 {len(all_tweets_data)} 件のツイート情報処理完了 (App Context)。")
        return all_tweets_data

    def download_media_for_tweet(self, tweet_info: dict, base_download_dir: str = "./downloaded_media") -> List[str]:
        """
        指定されたツイート情報に含まれるメディアファイルをダウンロードする。
        Args:
            tweet_info (dict): fetch_tweets_by_username_app_context で取得したツイート1件分の情報。
            base_download_dir (str): メディアを保存するベースディレクトリ。
        Returns:
            List[str]: ダウンロード成功したファイルのローカルパスのリスト。
        """
        if not tweet_info or not isinstance(tweet_info.get("media"), list) or not tweet_info["media"]:
            # logger.debug(f"({self.bot_name}) ツイートID {tweet_info.get('id')} にはダウンロード可能なメディアがありません。")
            return []

        tweet_id = tweet_info.get("id", "unknown_tweet_id")
        # ユーザー名やツイートIDでサブディレクトリを作成 (オプション)
        # target_download_dir = os.path.join(base_download_dir, tweet_info.get("author_username", "unknown_user"), tweet_id)
        target_download_dir = os.path.join(base_download_dir, tweet_id) # ツイートIDごとのディレクトリ
        os.makedirs(target_download_dir, exist_ok=True)

        downloaded_file_paths = []
        media_list = tweet_info["media"]

        for i, media_item in enumerate(media_list):
            media_url = media_item.get("url")
            if not media_url:
                logger.warning(f"({self.bot_name}) メディアアイテム {i+1} (TweetID: {tweet_id}) にURLがありません。スキップします。 Details: {media_item}")
                continue

            media_type = media_item.get("type", "unknown")
            media_key = media_item.get("media_key", f"media_{i+1}")
            
            try:
                # ファイル名と拡張子を決定
                original_filename = os.path.basename(requests.utils.urlparse(media_url).path)
                _name, ext = os.path.splitext(original_filename)
                if not ext: # URLに拡張子が含まれない場合 (例: photo タイプ)
                    if media_type == "photo":
                        ext = ".jpg" # デフォルトはjpgとするが、Content-Typeを見るのがより確実
                    elif media_type == "video" or media_type == "animated_gif":
                        ext = ".mp4"
                    else:
                        ext = "" # 不明な場合は拡張子なし
                
                filename = f"{tweet_id}_{media_key}{ext}"
                local_filepath = os.path.join(target_download_dir, filename)

                logger.info(f"({self.bot_name}) メディアダウンロード開始: {media_url} -> {local_filepath}")
                
                # ここでも _send_api_request のような機構は不要（外部URLへのGETなのでレート制限はX APIとは別）
                # ただし、リトライやタイムアウトは設定しておくと良い
                media_response = requests.get(media_url, stream=True, timeout=30) # timeout追加
                media_response.raise_for_status() # HTTPエラーチェック

                with open(local_filepath, 'wb') as f:
                    for chunk in media_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"✅ ({self.bot_name}) メディアダウンロード成功: {local_filepath}")
                downloaded_file_paths.append(local_filepath)
            
            except requests.exceptions.RequestException as e_req_media:
                logger.error(f"❌ ({self.bot_name}) メディアダウンロード失敗 (RequestException): {media_url}, Error: {e_req_media}")
            except IOError as e_io:
                logger.error(f"❌ ({self.bot_name}) メディアファイルの書き込み失敗: {local_filepath}, Error: {e_io}")
            except Exception as e_gen_media:
                logger.error(f"❌ ({self.bot_name}) メディアダウンロード中に予期せぬエラー: {media_url}, Error: {e_gen_media}", exc_info=True)
        
        return downloaded_file_paths

    def _get_user_id_with_cache(self, username: str, headers_for_api_call: dict):
        user_id = None
        try:
            user_id_cache = self.twitter_api_config.get("user_id_cache", {})
            if username in user_id_cache and user_id_cache[username]:
                user_id = user_id_cache[username]
                logger.info(f"✅ ({self.bot_name}) ユーザーIDキャッシュ利用: {username} -> {user_id}")
                return user_id # キャッシュヒットしたら即座に返す
        except Exception as e:
            logger.warning(f"⚠️ ({self.bot_name}) ユーザーIDキャッシュ読込エラー: {e}。APIから取得試行。")

        # キャッシュになければAPIから取得
        user_lookup_url = f"{API_BASE_URL_V2}/users/by/username/{username}"
        logger.info(f"({self.bot_name}) ユーザー '{username}' IDをAPIから取得中... URL: {user_lookup_url}")
        
        user_data = self._send_api_request("GET", user_lookup_url, headers=self.headers_app_context, params={"user.fields": "id,username"}) # headers_for_api_call を self.headers_app_context に変更

        if user_data and "data" in user_data and "id" in user_data["data"]:
            user_id = user_data["data"]["id"]
            logger.info(f"✅ ({self.bot_name}) ユーザーID取得成功 (API): {username} -> {user_id}")
            # TODO: user_id_cache を更新する処理 (config_loader経由でYAMLに書き込むなど) は別途検討
            logger.info(f"🔔 ({self.bot_name}) config.yml の twitter_api.user_id_cache に追加推奨: {username}: \"{user_id}\"")
        else:
            logger.error(f"❌ ({self.bot_name}) '{username}' ID取得失敗(API)。レスポンス: {user_data}")
            return None
        return user_id

# --- mainブロックのテストコード (リファクタリングに合わせて修正) ---
if __name__ == "__main__":
    print("--- TwitterApiClient クラスのテスト (ツイート投稿 & 取得) ---")
    
    # このテストを実行する前に、config/config.yml に各種APIキーが設定されていることを確認してください。
    # 特に User Context API (投稿テスト用) と App Context API (取得テスト用) の両方。

    test_bot_name = "api_client_test_runner"
    try:
        api_client = TwitterApiClient(bot_name=test_bot_name)
    except ValueError as e: # config_loaderがエラーを出す場合など
        logger.error(f"テスト用APIクライアント初期化失敗: {e}")
        exit()
    except Exception as e_init:
        logger.error(f"テスト用APIクライアント初期化中に予期せぬエラー: {e_init}", exc_info=True)
        exit()

    # 1. ツイート投稿テスト (User Context)
    print("\n--- 1. ツイート投稿テスト (User Context) ---")
    if api_client.client_v2_user_context:
        import datetime
        test_tweet_text = f"これは #Tweepy と #Python ({test_bot_name}) を使ったテスト投稿です。Time: {datetime.datetime.now().isoformat()}"
        print(f"投稿予定内容: {test_tweet_text}")
        
        # 注意: 実際に投稿するとAPIリミットを消費します。
        # posted_tweet_data = api_client.post_tweet(test_tweet_text)
        # if posted_tweet_data:
        # print(f"  投稿成功。ツイートID: {posted_tweet_data.get('id')}, テキスト: {posted_tweet_data.get('text')}")
        # else:
        # print("  投稿失敗。ログを確認してください。")
        print("（実際の投稿処理はコメントアウトされています。テスト時に有効化してください。）")
    else:
        print("User Contextクライアントが初期化されていないため、投稿テストをスキップします。")
        print("config.yml に consumer_key, consumer_secret, access_token, access_token_secret を設定してください。")

    # 2. ツイート取得テスト (App Context)
    print("\n--- 2. ツイート取得テスト (App Context) ---")
    if api_client.headers_app_context: # App Contextヘッダーが準備できていれば
        test_username_for_fetch = "elonmusk" # またはAPIテストに適した公開アカウント
        num_tweets_to_fetch = 5 # メディアが含まれるツイートをテストするために少し多めに取得
        print(f"ユーザー '{test_username_for_fetch}' の最新ツイートを {num_tweets_to_fetch} 件取得します...")
        
        tweets = api_client.fetch_tweets_by_username_app_context(test_username_for_fetch, max_tweets_to_fetch=num_tweets_to_fetch)
        
        if tweets: # リストで返ってくる想定
            print(f"取得したツイート ({len(tweets)}件):")
            for i, tweet in enumerate(tweets):
                print(f"  Tweet {i+1}: ID={tweet.get('id')}, Author={tweet.get('author_username')}, Text='{tweet.get('text', '')[:60]}...'")
                if tweet.get("media"):
                    print(f"    Media ({len(tweet['media'])} attachments):")
                    for j, media_item in enumerate(tweet['media']):
                        print(f"      - {j+1}: Type={media_item.get('type')}, URL={media_item.get('url')}")
                    
                    # メディアダウンロードテスト
                    print(f"    メディアダウンロードテスト開始 (Tweet ID: {tweet.get('id')})...")
                    download_base_dir = "./test_media_downloads" # テスト用のダウンロードディレクトリ
                    downloaded_files = api_client.download_media_for_tweet(tweet, base_download_dir=download_base_dir)
                    if downloaded_files:
                        print(f"    ✅ メディアダウンロード成功 ({len(downloaded_files)}件):")
                        for file_path in downloaded_files:
                            print(f"      -> {file_path}")
                    else:
                        print(f"    メディアはあったがダウンロードされませんでした（または全て失敗）。")
                else:
                    print("    このツイートにメディア添付はありませんでした。")

        elif isinstance(tweets, list) and not tweets: # 空リストの場合 (取得試行したが0件 or APIエラーで空リスト返却)
             print(f"ユーザー '{test_username_for_fetch}' のツイートは取得できませんでした (0件またはエラー)。ログを確認してください。")
        else: # None や予期せぬ型が返った場合
             print(f"ユーザー '{test_username_for_fetch}' のツイート取得中に問題が発生しました。戻り値: {tweets}。ログを確認してください。")
    else:
        print("App Context (Bearer Token) が設定されていないため、ツイート取得テストをスキップします。")
        print("config.yml に twitter_api.bearer_token を設定してください。")

    print("\n--- TwitterApiClient テスト完了 ---")

    # 以前の __main__ であった NotionWriter 関連のテストは、このファイルとは責務が異なるため削除。
    # NotionWriter (現 notion_compiler.py) のテストは、そちらのファイルで行うべき。 