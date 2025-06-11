import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from ..config import Config
from ..utils.logging_utils import get_logger
from ..spreadsheet_manager import SpreadsheetManager
from ..twitter_client import TwitterClient

logger = get_logger(__name__)

class ScheduledPostExecutor:
    """
    1件の投稿処理（スプレッドシートからの記事取得、投稿、ステータス更新）を
    担当するクラス。
    """
    def __init__(self, config: Config, spreadsheet_manager: SpreadsheetManager):
        self.config = config
        self.spreadsheet_manager = spreadsheet_manager
        self.twitter_clients: Dict[str, TwitterClient] = {}

    def execute_post(self, scheduled_post: Dict[str, Any]) -> Optional[str]:
        """
        実際に投稿処理を実行する。
        成功した場合は tweet_id を、投稿対象がない場合は None を返す。
        エラーの場合は例外を送出する。
        """
        account_id = scheduled_post["account_id"]
        worksheet_name = scheduled_post["worksheet_name"]
        
        logger.info(f"投稿処理を開始します: アカウント='{account_id}', ワークシート='{worksheet_name}'")

        try:
            # 1. 投稿内容をスプレッドシートから取得
            post_content = self.spreadsheet_manager.get_post_candidate(worksheet_name)
            logger.info(f"取得した投稿候補の内容: {post_content}")

            if not post_content:
                logger.warning(f"アカウント '{account_id}' のワークシート '{worksheet_name}' に投稿可能な記事がありませんでした。処理をスキップします。")
                return None

            # 2. Twitterクライアントを初期化（アカウントごとに初回のみ）
            if account_id not in self.twitter_clients:
                account_details = self.config.get_active_twitter_account_details(account_id)
                if not account_details:
                    raise ValueError(f"アカウント '{account_id}' の設定情報（APIキーなど）が見つからないか、無効です。")

                self.twitter_clients[account_id] = TwitterClient(
                    consumer_key=account_details["consumer_key"],
                    consumer_secret=account_details["consumer_secret"],
                    access_token=account_details["access_token"],
                    access_token_secret=account_details["access_token_secret"],
                    bearer_token=account_details.get("bearer_token") # 任意
                )
            client = self.twitter_clients[account_id]

            # 3. 投稿を実行
            logger.info(f"アカウント'{account_id}' でツイートを投稿します...")
            logger.debug(f"投稿内容: Text='{post_content['text']}', Media='{post_content.get('media_path')}'")
            
            # post_tweet は media_path を受け取らないため、post_with_media_url を使用する
            tweet_response = client.post_with_media_url(
                text=post_content["text"],
                media_url=post_content.get("media_path")
            )
            
            if not tweet_response or 'id' not in tweet_response:
                # 投稿失敗のケース。post_with_media_url 内でエラーログは出力されているはず。
                raise Exception(f"アカウント '{account_id}' の投稿に失敗しました。レスポンス: {tweet_response}")

            tweet_id = tweet_response['id']
            logger.info(f"アカウント '{account_id}' の投稿が成功しました。Tweet ID: {tweet_id}")

            # 4. 投稿済みとしてスプレッドシートを更新
            self.spreadsheet_manager.update_post_status(
                worksheet_name=worksheet_name,
                row_index=post_content["row_index"],
                posted_at=datetime.now(timezone.utc)
            )
            
            return tweet_id

        except Exception as e:
            logger.error(f"アカウント '{account_id}' の投稿処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
            # エラーが発生した場合はNoneではなく例外を再送出する
            raise 