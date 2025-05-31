import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

class SpreadsheetManager:
    def __init__(self, config: Dict[str, Any], logger=None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.client = None
        self.worksheets = {}
        self._initialize_client()

    def _initialize_client(self):
        """Google Sheetsクライアントの初期化"""
        try:
            key_file = self.config["common"]["file_paths"]["google_key_file"]
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            
            creds = ServiceAccountCredentials.from_json_keyfile_name(key_file, scope)
            self.client = gspread.authorize(creds)
            
            # 各アカウントのワークシートを初期化
            for account in self.config["twitter_accounts"]:
                if account["google_sheets_source"]["enabled"]:
                    spreadsheet = self.client.open_by_key(
                        self.config["auto_post_bot"]["google_sheets_source"]["spreadsheet_id"]
                    )
                    worksheet = spreadsheet.worksheet(account["google_sheets_source"]["worksheet_name"])
                    self.worksheets[account["account_id"]] = worksheet
                    
            self.logger.info("Spreadsheet manager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize spreadsheet manager: {str(e)}")
            raise

    def get_posts_for_account(self, account_id: str) -> List[Dict[str, Any]]:
        """アカウント用の投稿データを取得"""
        try:
            worksheet = self.worksheets.get(account_id)
            if not worksheet:
                raise ValueError(f"No worksheet found for account: {account_id}")

            # ヘッダー行を取得
            headers = worksheet.row_values(1)
            
            # 全データを取得
            all_values = worksheet.get_all_values()[1:]  # ヘッダーを除外
            
            posts = []
            for row in all_values:
                if len(row) != len(headers):
                    continue
                
                post = dict(zip(headers, row))
                
                # 投稿可能かチェック
                if post.get("投稿可能", "").lower() != "true":
                    continue
                    
                # 最終投稿からの経過時間をチェック
                last_posted = post.get("最終投稿日時")
                if last_posted:
                    try:
                        last_posted_dt = datetime.fromisoformat(last_posted)
                        hours_since_last = (datetime.now() - last_posted_dt).total_seconds() / 3600
                        if hours_since_last < self.config["auto_post_bot"]["posting_settings"]["min_interval_hours"]:
                            continue
                    except ValueError:
                        pass  # 日時のパースに失敗した場合は無視
                
                posts.append(post)
            
            return posts
            
        except Exception as e:
            self.logger.error(f"Failed to get posts for account {account_id}: {str(e)}")
            return []

    def update_post_status(self, account_id: str, post_id: str, success: bool, tweet_url: Optional[str] = None):
        """投稿ステータスを更新"""
        try:
            worksheet = self.worksheets.get(account_id)
            if not worksheet:
                raise ValueError(f"No worksheet found for account: {account_id}")

            # IDで行を検索
            cell = worksheet.find(post_id)
            if not cell:
                raise ValueError(f"Post ID {post_id} not found")

            row = cell.row
            headers = worksheet.row_values(1)

            # 投稿回数をインクリメント
            post_count_col = headers.index("投稿済み回数") + 1
            current_count = worksheet.cell(row, post_count_col).value
            new_count = int(current_count) + 1 if current_count.isdigit() else 1
            worksheet.update_cell(row, post_count_col, new_count)

            # 最終投稿日時を更新
            last_posted_col = headers.index("最終投稿日時") + 1
            worksheet.update_cell(row, last_posted_col, datetime.now().isoformat())

            self.logger.info(f"Updated post status for ID {post_id}: count={new_count}")

        except Exception as e:
            self.logger.error(f"Failed to update post status: {str(e)}")
            raise 