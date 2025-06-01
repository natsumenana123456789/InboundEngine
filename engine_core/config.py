import yaml
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class Config:
    # _instance = None # シングルトン無効化
    # _config_data: Optional[Dict[str, Any]] = None # __init__で毎回Noneに初期化するのでここでは不要かも
    # _gspread_key_path: Optional[str] = None # 同上

    # def __new__(cls, *args, **kwargs):
    #     if not cls._instance:
    #         cls._instance = super().__new__(cls)
    #     return cls._instance

    def __init__(self, config_path: str = "config/config.yml"):
        self._config_data: Optional[Dict[str, Any]] = None # 毎回Noneに初期化
        self._gspread_key_path: Optional[str] = None # 毎回Noneに初期化
        
        # if self._config_data is None:  # 強制再読み込みテストで行った変更を元に戻し、常にロードする
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config_data = yaml.safe_load(f)
            logger.info(f"設定ファイル {config_path} を読み込みました。 (シングルトン解除テスト)")
            logger.debug(f"読み込んだ schedule_settings: {self._config_data.get('auto_post_bot', {}).get('schedule_settings')}")

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
                # worksheet_name をアカウント詳細に含める
                if isinstance(acc.get("google_sheets_source"), dict):
                    acc["spreadsheet_worksheet"] = acc["google_sheets_source"].get("worksheet_name")
                return acc
        logger.warning(f"TwitterアカウントID '{account_id}' の設定が見つかりません。")
        return None

    def get_discord_webhook_url(self, notifier_id: str = "default") -> Optional[str]:
        # notifier_id を無視し、固定のパスからwebhook_urlを取得
        return self.get("auto_post_bot.discord_notification.webhook_url")

    def get_spreadsheet_columns(self, bot_type: str = "auto_post_bot") -> Optional[List[str]]:
        return self.get(f"{bot_type}.columns")

    def get_schedule_config(self) -> Optional[Dict[str, Any]]:
        return self.get("auto_post_bot.schedule_settings")

    def get_posts_per_account_schedule(self) -> Optional[Dict[str, int]]:
        accounts = self.get_twitter_accounts()
        if not accounts:
            logger.warning("Twitterアカウント設定が見つからないため、投稿スケジュールを生成できません。")
            return None

        default_posts_per_account = self.get("auto_post_bot.posting_settings.posts_per_account")
        
        schedule: Dict[str, int] = {}
        for account in accounts:
            account_id = account.get("account_id")
            if not account_id:
                logger.warning("アカウントIDがないTwitterアカウント設定が見つかりました。スキップします。")
                continue

            posts_today = account.get("posts_today") # config.yml の各アカウントに posts_today: X を追加することを想定
            if isinstance(posts_today, int):
                schedule[account_id] = posts_today
            elif isinstance(default_posts_per_account, int): # 個別設定がなく、デフォルト設定が有効な場合
                schedule[account_id] = default_posts_per_account
            else:
                logger.warning(
                    f"アカウント '{account_id}' の投稿数が個別にもデフォルトにも有効に設定されていません。"
                    f" (個別: {posts_today}, デフォルト: {default_posts_per_account}). "
                    f"このアカウントのスケジュールは生成されません。"
                )
        
        if not schedule: # 有効なスケジュールが一つも生成できなかった場合
            logger.error("有効なアカウント別投稿スケジュールを一つも生成できませんでした。")
            return None
            
        return schedule

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