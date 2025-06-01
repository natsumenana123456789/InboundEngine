import yaml
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class Config:
    _instance = None
    _config_data: Optional[Dict[str, Any]] = None
    _gspread_key_path: Optional[str] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: str = "config/config.yml"):
        if self._config_data is None:  # 初回のみロード
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config_data = yaml.safe_load(f)
                logger.info(f"設定ファイル {config_path} を読み込みました。")

                # gspread-key.json のパスを解決
                # config.yml からファイル名を取得
                default_gspread_key_filename = "gspread-key.json"
                # self.get() は _config_data が設定された後に呼び出す必要があるため、一時的に直接アクセス
                gspread_key_filename_from_config = None
                if self._config_data and \
                   isinstance(self._config_data.get("common"), dict) and \
                   isinstance(self._config_data["common"].get("file_paths"), dict):
                    gspread_key_filename_from_config = self._config_data["common"]["file_paths"].get("google_key_file")

                if gspread_key_filename_from_config:
                    gspread_key_filename = str(gspread_key_filename_from_config)
                else:
                    gspread_key_filename = default_gspread_key_filename
                    logger.warning(f"config.ymlに 'common.file_paths.google_key_file' が見つからないか、パスが不正なため、デフォルト名 '{default_gspread_key_filename}' を使用します。")

                config_dir = os.path.dirname(os.path.abspath(config_path))
                self._gspread_key_path = os.path.join(config_dir, gspread_key_filename)
                
                if not os.path.exists(self._gspread_key_path):
                    logger.warning(f"gspreadキーファイルが見つかりません: {self._gspread_key_path}")
                    # パスが存在しない場合、SpreadsheetManagerでエラーになることを期待し、ここではNoneにしない
                else:
                    logger.info(f"gspreadキーファイルを確認: {self._gspread_key_path}")

            except FileNotFoundError:
                logger.error(f"設定ファイルが見つかりません: {config_path}")
                raise
            except yaml.YAMLError as e:
                logger.error(f"設定ファイルの解析に失敗しました: {config_path}, Error: {e}")
                raise
            except Exception as e:
                logger.error(f"設定ファイルの読み込み中に予期せぬエラーが発生しました: {e}")
                raise

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        if self._config_data is None:
            logger.error("設定データがロードされていません。")
            return default
        keys = key.split('.')
        value = self._config_data
        try:
            for k in keys:
                if isinstance(value, dict):
                    value = value[k]
                else: # リストのインデックス等は非対応
                    logger.warning(f"設定キー '{key}' のパス '{k}' が不正です。")
                    return default
            return value
        except KeyError:
            logger.warning(f"設定キー '{key}' が見つかりません。")
            return default
        except TypeError: # valueがNoneの場合など
            logger.warning(f"設定キー '{key}' の途中でNoneが見つかりました。")
            return default


    @property
    def gspread_service_account_key_path(self) -> Optional[str]:
        return self._gspread_key_path

    def get_spreadsheet_id(self) -> Optional[str]:
        return self.get("auto_post_bot.google_sheets_source.spreadsheet_id")

    def get_twitter_accounts(self) -> List[Dict[str, Any]]:
        return self.get("auto_post_bot.twitter_accounts", [])

    def get_active_twitter_account_details(self, account_id: str) -> Optional[Dict[str, Any]]:
        accounts = self.get_twitter_accounts()
        for acc in accounts:
            if acc.get("account_id") == account_id:
                return acc
        logger.warning(f"TwitterアカウントID '{account_id}' の設定が見つかりません。")
        return None

    def get_discord_webhook_url(self, notifier_id: str = "default") -> Optional[str]:
        notifiers = self.get("auto_post_bot.notifiers.discord", [])
        for notifier in notifiers:
            if notifier.get("id") == notifier_id:
                return notifier.get("webhook_url")
        logger.warning(f"Discord通知先ID '{notifier_id}' の設定が見つかりません。")
        return None

    def get_spreadsheet_columns(self, bot_type: str = "auto_post_bot") -> Optional[List[str]]:
        return self.get(f"{bot_type}.columns")

    def get_schedule_config(self) -> Optional[Dict[str, Any]]:
        return self.get("auto_post_bot.schedule_settings")

    def get_posts_per_account_schedule(self) -> Optional[Dict[str, int]]:
        schedule_config = self.get_schedule_config()
        if schedule_config:
            return schedule_config.get("posts_per_account")
        return None

    def get_logs_directory(self) -> Optional[str]:
        return self.get("common.logs_directory", "logs") # デフォルト値を "logs" に設定

    # 必要に応じて他の設定値取得メソッドを追加

if __name__ == '__main__':
    # 簡単なテスト
    logging.basicConfig(level=logging.INFO)
    try:
        # プロジェクトルートからの相対パスでconfig.ymlを指定
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # engine_coreの親がプロジェクトルート
        config_file_path = os.path.join(project_root, "config/config.yml")

        config = Config(config_path=config_file_path)

        print(f"Spreadsheet ID: {config.get_spreadsheet_id()}")
        print(f"GSpread Key Path: {config.gspread_service_account_key_path}")
        
        twitter_accounts = config.get_twitter_accounts()
        if twitter_accounts:
            print(f"最初のTwitterアカウントID: {twitter_accounts[0].get('account_id')}")
            details = config.get_active_twitter_account_details(twitter_accounts[0].get('account_id'))
            if details:
                print(f"  Consumer Key: {details.get('consumer_key')}")

        print(f"Discord Webhook (default): {config.get_discord_webhook_url()}")
        print(f"Spreadsheet Columns (auto_post_bot): {config.get_spreadsheet_columns()}")
        
        schedule_conf = config.get_schedule_config()
        if schedule_conf:
            print(f"Scheduler start_hour: {schedule_conf.get('start_hour')}")
            print(f"Scheduler posts_per_account: {config.get_posts_per_account_schedule()}")

    except Exception as e:
        print(f"エラー: {e}") 