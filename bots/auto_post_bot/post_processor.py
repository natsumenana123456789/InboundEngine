import logging
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from twitter_client import TwitterClient
from spreadsheet_manager import SpreadsheetManager
from discord_notifier import DiscordNotifier

class PostProcessor:
    def __init__(self, config: Dict[str, Any], logger=None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.twitter_client = TwitterClient(config, logger)
        self.spreadsheet_manager = SpreadsheetManager(config, logger)
        self.discord_notifier = DiscordNotifier(config, logger)

    def process_posts(self):
        """全アカウントの投稿を処理"""
        for account in self.config["twitter_accounts"]:
            account_id = account["account_id"]
            self.logger.info(f"Processing posts for account: {account_id}")

            try:
                # 投稿可能時間帯かチェック
                if not self._is_posting_time():
                    self.logger.info("Outside of posting hours, skipping...")
                    continue

                # 投稿データを取得
                posts = self.spreadsheet_manager.get_posts_for_account(account_id)
                if not posts:
                    self.logger.info(f"No posts available for account: {account_id}")
                    continue

                # 優先順位でソート
                sorted_posts = self._sort_posts_by_priority(posts)
                
                # 投稿を実行
                for post in sorted_posts:
                    result = self._process_single_post(account_id, post)
                    if result["success"]:
                        break  # 1回の実行で1投稿のみ
                    
            except Exception as e:
                self.logger.error(f"Error processing posts for {account_id}: {str(e)}")
                self.discord_notifier.send_error(f"投稿処理エラー: {str(e)}", account_id)

    def _process_single_post(self, account_id: str, post: Dict[str, Any]) -> Dict[str, Any]:
        """単一の投稿を処理"""
        try:
            # テキストの準備
            text = self._prepare_text(post["本文"])
            
            # メディアURLの処理
            media_urls = self._parse_media_urls(post.get("画像/動画URL", ""))

            # ツイート投稿
            result = self.twitter_client.post_tweet(account_id, text, media_urls)

            if result["success"]:
                # スプレッドシートの更新
                self.spreadsheet_manager.update_post_status(
                    account_id,
                    post["ID"],
                    True,
                    result["tweet_url"]
                )

                # 成功通知
                self.discord_notifier.send_post_success(
                    text,
                    result["tweet_url"],
                    account_id
                )
            else:
                # エラー通知
                self.discord_notifier.send_error(
                    f"投稿失敗: {result.get('error', '不明なエラー')}",
                    account_id
                )

            return result

        except Exception as e:
            self.logger.error(f"Error processing post {post.get('ID')}: {str(e)}")
            return {"success": False, "error": str(e)}

    def _prepare_text(self, text: str) -> str:
        """投稿テキストの準備（重複防止のためのスペース挿入）"""
        # ランダムな位置にスペースを挿入
        words = text.split()
        if len(words) > 1:
            insert_pos = random.randint(0, len(words) - 1)
            words[insert_pos] = words[insert_pos] + " "
        return " ".join(words)

    def _parse_media_urls(self, media_url_str: str) -> Optional[List[str]]:
        """メディアURLの文字列をリストに変換"""
        if not media_url_str:
            return None
        return [url.strip() for url in media_url_str.split(",") if url.strip()]

    def _is_posting_time(self) -> bool:
        """現在が投稿可能な時間帯かチェック"""
        now = datetime.now()
        start_hour = self.config["auto_post_bot"]["schedule_settings"]["start_hour"]
        end_hour = self.config["auto_post_bot"]["schedule_settings"]["end_hour"]
        return start_hour <= now.hour < end_hour

    def _sort_posts_by_priority(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """投稿を優先順位でソート"""
        def get_priority(post):
            # 投稿回数が少ないものを優先
            post_count = int(post.get("投稿済み回数", "0") or "0")
            
            # 最終投稿からの経過時間を考慮
            last_posted = post.get("最終投稿日時")
            hours_since_last = 0
            if last_posted:
                try:
                    last_posted_dt = datetime.fromisoformat(last_posted)
                    hours_since_last = (datetime.now() - last_posted_dt).total_seconds() / 3600
                except ValueError:
                    pass

            # 優先度スコアを計算（投稿回数が少なく、最後の投稿から時間が経っているものが優先）
            return (-post_count, hours_since_last)

        return sorted(posts, key=get_priority) 