# アカウント管理ハイブリッドシステム
# セキュリティレベルに応じた情報分離

import os
import sys
from typing import Dict, List, Optional

# プロジェクトルートをパスに追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from config import config_loader

class AccountManager:
    """
    セキュアなアカウント管理システム
    
    スプレッドシート保存:
    - アカウント名
    - ワークシート名
    - 表示名
    - 有効/無効状態
    - 投稿スケジュール設定
    
    環境変数/Secrets保存:
    - API認証情報
    - パスワード
    """
    
    def __init__(self):
        self.config = config_loader.get_bot_config("auto_post_bot")
        
    def get_accounts_from_spreadsheet(self) -> List[Dict]:
        """
        スプレッドシートからアカウント設定を取得
        機密情報は含まない
        """
        try:
            # アカウント管理専用シートから取得
            accounts_data = config_loader.load_records_from_sheet(
                "システム管理", 
                "アカウント設定",
                "gspread-key.json"
            )
            
            return [
                {
                    "account_id": row.get("アカウントID"),
                    "display_name": row.get("表示名"),
                    "worksheet_name": row.get("ワークシート名"),
                    "enabled": row.get("有効") == "TRUE",
                    "schedule_enabled": row.get("スケジュール有効") == "TRUE",
                    "posts_per_day": int(row.get("1日投稿回数", 1)),
                    "priority": int(row.get("優先度", 100))
                }
                for row in accounts_data
                if row.get("アカウントID")
            ]
        except Exception as e:
            print(f"スプレッドシートからのアカウント取得エラー: {e}")
            return []
    
    def get_account_credentials(self, account_id: str) -> Optional[Dict]:
        """
        環境変数またはSecretsから認証情報を取得
        """
        try:
            # 環境変数名のパターン
            env_prefix = f"TWITTER_{account_id.upper()}_"
            
            credentials = {
                "consumer_key": os.getenv(f"{env_prefix}CONSUMER_KEY"),
                "consumer_secret": os.getenv(f"{env_prefix}CONSUMER_SECRET"),
                "access_token": os.getenv(f"{env_prefix}ACCESS_TOKEN"),
                "access_token_secret": os.getenv(f"{env_prefix}ACCESS_TOKEN_SECRET"),
                "email": os.getenv(f"{env_prefix}EMAIL"),
                "username": os.getenv(f"{env_prefix}USERNAME"),
                "password": os.getenv(f"{env_prefix}PASSWORD")  # 参考用
            }
            
            # 必須項目のチェック
            required_fields = ["consumer_key", "consumer_secret", "access_token", "access_token_secret"]
            if all(credentials.get(field) for field in required_fields):
                return credentials
            else:
                print(f"アカウント {account_id} の認証情報が不完全です")
                return None
                
        except Exception as e:
            print(f"認証情報取得エラー: {e}")
            return None
    
    def get_active_accounts(self) -> List[Dict]:
        """
        有効なアカウントの完全な設定を取得
        """
        accounts_config = self.get_accounts_from_spreadsheet()
        complete_accounts = []
        
        for account_config in accounts_config:
            if not account_config.get("enabled"):
                continue
                
            account_id = account_config["account_id"]
            credentials = self.get_account_credentials(account_id)
            
            if credentials:
                # 設定と認証情報をマージ
                complete_account = {**account_config, **credentials}
                complete_account["google_sheets_source"] = {
                    "enabled": True,
                    "worksheet_name": account_config["worksheet_name"]
                }
                complete_accounts.append(complete_account)
            else:
                print(f"⚠️ アカウント {account_id} の認証情報が見つかりません")
        
        return complete_accounts
    
    def get_scheduler_accounts(self) -> List[str]:
        """
        スケジューラ用のアカウントIDリストを取得
        """
        accounts = self.get_accounts_from_spreadsheet()
        return [
            acc["account_id"] 
            for acc in accounts 
            if acc.get("enabled") and acc.get("schedule_enabled")
        ]

# スプレッドシート用のサンプルデータ構造
SPREADSHEET_SCHEMA = {
    "シート名": "システム管理",
    "ワークシート名": "アカウント設定",
    "列構成": [
        "アカウントID",      # jadiAngkat, hinataHHHHHH など
        "表示名",            # 管理用の表示名
        "ワークシート名",    # 都内メンエス, 都内セクキャバ など
        "有効",              # TRUE/FALSE
        "スケジュール有効",  # TRUE/FALSE
        "1日投稿回数",       # 1, 2, 3 など
        "優先度",            # 100, 200 など (小さい方が高優先度)
        "備考"               # 管理用メモ
    ]
}

# 環境変数の設定例
ENV_VARIABLES_EXAMPLE = """
# jadiAngkat アカウント用
TWITTER_JADIANGKAT_CONSUMER_KEY=your_consumer_key
TWITTER_JADIANGKAT_CONSUMER_SECRET=your_consumer_secret
TWITTER_JADIANGKAT_ACCESS_TOKEN=your_access_token
TWITTER_JADIANGKAT_ACCESS_TOKEN_SECRET=your_access_token_secret
TWITTER_JADIANGKAT_EMAIL=email@example.com
TWITTER_JADIANGKAT_USERNAME=jadiAngkat

# hinataHHHHHH アカウント用
TWITTER_HINATAHHHHHH_CONSUMER_KEY=your_consumer_key
TWITTER_HINATAHHHHHH_CONSUMER_SECRET=your_consumer_secret
TWITTER_HINATAHHHHHH_ACCESS_TOKEN=your_access_token
TWITTER_HINATAHHHHHH_ACCESS_TOKEN_SECRET=your_access_token_secret
TWITTER_HINATAHHHHHH_EMAIL=email@example.com
TWITTER_HINATAHHHHHH_USERNAME=hinataHHHHHH
""" 