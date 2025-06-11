import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .config import AppConfig
from .utils.logging_utils import get_logger
from .spreadsheet_manager import SpreadsheetManager
from .twitter_client import TwitterClient

logger = get_logger(__name__)

class ScheduledPostExecutor:
    """
    1件の投稿処理（スプレッドシートからの記事取得、投稿、ステータス更新）を
    担当するクラス。
    """
    def __init__(self, config: AppConfig, spreadsheet_manager: SpreadsheetManager):
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
            post_content = self.spreadsheet_manager.get_post_content(worksheet_name)

            if not post_content:
                logger.warning(f"アカウント '{account_id}' のワークシート '{worksheet_name}' に投稿可能な記事がありませんでした。処理をスキップします。")
                return None

            # 2. Twitterクライアントを初期化（アカウントごとに初回のみ）
            if account_id not in self.twitter_clients:
                self.twitter_clients[account_id] = TwitterClient(self.config, account_id)
            client = self.twitter_clients[account_id]

            # 3. 投稿を実行
            logger.info(f"アカウント'{account_id}' でツイートを投稿します...")
            logger.debug(f"投稿内容: Text='{post_content['text']}', Media='{post_content.get('media_path')}'")
            
            tweet_id = client.post_tweet(
                text=post_content["text"],
                media_path=post_content.get("media_path")
            )
            
            logger.info(f"アカウント '{account_id}' の投稿が成功しました。Tweet ID: {tweet_id}")

            # 4. 投稿済みとしてスプレッドシートを更新
            self.spreadsheet_manager.mark_as_posted(
                worksheet_name=worksheet_name,
                row_index=post_content["row_index"],
                tweet_id=tweet_id
            )
            
            return tweet_id

        except Exception as e:
            logger.error(f"アカウント '{account_id}' の投稿処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
            # エラーが発生した場合はNoneではなく例外を再送出する
            raise 