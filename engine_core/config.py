import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# DEFAULT_CONFIG は廃止

class Config:
    def __init__(self, config_path: Optional[str] = None):
        self._config_data: Dict[str, Any] = {}
        self.config_path = config_path # 引数で渡されたパスを保存
        # config.py が engine_core の中にある前提でプロジェクトルートを推定
        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._load_settings()

    # _deep_update は DEFAULT_CONFIG とのマージがなくなったため不要。削除。

    def _load_settings(self):
        loaded_config_source = None
        config_json_str = None

        # 0. 引数で指定された config_path を最優先で試す
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_json_str = f.read()
                loaded_config_source = f"指定された設定ファイル ({self.config_path})"
            except Exception as e:
                logger.critical(f"{self.config_path} の読み込み中にエラー: {e}")
                config_json_str = None

        # 1. 環境変数 APP_CONFIG_JSON を試す
        if not config_json_str:
            app_config_json_str_env = os.environ.get("APP_CONFIG_JSON")
            if app_config_json_str_env:
                config_json_str = app_config_json_str_env
                loaded_config_source = "環境変数 APP_CONFIG_JSON"
        
        # 2. 環境変数からロードされなかった場合、開発用設定ファイルを試す
        if not config_json_str:
            dev_config_file_name = "app_config.dev.json"
            dev_config_file_path = os.path.join(self._project_root, "config", dev_config_file_name)
            
            if os.path.exists(dev_config_file_path):
                try:
                    with open(dev_config_file_path, 'r', encoding='utf-8') as f:
                        config_json_str = f.read()
                    loaded_config_source = f"開発用設定ファイル ({dev_config_file_path})"
                except Exception as e:
                    logger.critical(f"{dev_config_file_path} の読み込み中にエラー: {e}")
                    config_json_str = None 
            else:
                logger.info(f"開発用設定ファイル ({dev_config_file_path}) は見つかりませんでした。")

        # 3. 設定情報をパースして self._config_data に格納
        if config_json_str:
            try:
                self._config_data = json.loads(config_json_str)
                logger.info(f"{loaded_config_source} から設定を読み込みました。")
            except json.JSONDecodeError as e:
                logger.critical(f"{loaded_config_source} のJSONパースに失敗しました: {e}。設定は空になります。")
                self._config_data = {}
            except Exception as e:
                logger.critical(f"{loaded_config_source} のJSONパース処理中に予期せぬエラー: {e}。設定は空になります。")
                self._config_data = {}
        else:
            logger.critical(
                "設定情報源 (環境変数 APP_CONFIG_JSON または config/app_config.dev.json) が見つからないか、読み込めませんでした。"
                "アプリケーションは正しく動作しない可能性があります。"
            )
            self._config_data = {}

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        keys = key.split('.')
        value = self._config_data
        try:
            for k in keys:
                if isinstance(value, dict):
                    value = value[k]
                else:
                    return default
            return value
        except KeyError:
            return default
        except TypeError: 
            return default

    def get_log_level(self) -> Optional[str]:
        level = self.get("common.log_level")
        if not level or not isinstance(level, str) or level.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            logger.critical(f"ログレベル設定 (common.log_level: {level}) が不正または未設定です。実行に問題が生じる可能性があります。")
            return None
        return level.upper()

    def get_logs_directory(self) -> Optional[str]:
        path = self.get("common.logs_directory")
        if not path or not isinstance(path, str):
            logger.critical("ログディレクトリパス (common.logs_directory) が未設定または不正です。実行に問題が生じる可能性があります。")
            return None
        return path

    def get_gspread_service_account_dict(self) -> Optional[Dict[str, Any]]:
        # キー名を変更し、直接辞書を取得するようにする
        creds_dict = self.get("google_sheets.service_account_credentials") 
        if not creds_dict or not isinstance(creds_dict, dict):
            # 古いキー名もフォールバックとしてチェックし、警告を出す (任意)
            creds_str_old = self.get("google_sheets.service_account_credentials_json_str")
            if creds_str_old and isinstance(creds_str_old, str):
                logger.warning(
                    "古い設定キー 'google_sheets.service_account_credentials_json_str' が使用されています。"
                    "今後は 'google_sheets.service_account_credentials' を使用し、JSONオブジェクトを直接記述してください。"
                )
                try:
                    return json.loads(creds_str_old)
                except json.JSONDecodeError as e:
                    logger.critical(f"古いキー 'google_sheets.service_account_credentials_json_str' のJSONパースに失敗: {e}")
                    return None
            
            logger.critical("Googleサービスアカウント認証情報 (google_sheets.service_account_credentials) が未設定または辞書形式ではありません。")
            return None
        return creds_dict # 既に辞書なのでそのまま返す

    def get_spreadsheet_id(self) -> Optional[str]:
        sid = self.get("google_sheets.spreadsheet_id")
        if not sid or not isinstance(sid, str):
            logger.critical("スプレッドシートID (google_sheets.spreadsheet_id) が未設定または文字列ではありません。")
            # Noneを返すか、あるいはここでプログラムを終了させるべきか検討の余地あり
        return sid 

    def get_twitter_accounts(self) -> List[Dict[str, Any]]:
        accounts_data = self.get("twitter_accounts", []) # 見つからなければ空リスト
        processed_accounts = []
        if not isinstance(accounts_data, list):
            logger.critical(f"設定内の twitter_accounts がリスト形式ではありません。型: {type(accounts_data)}")
            return []
        
        for acc_raw in accounts_data:
            if not isinstance(acc_raw, dict):
                logger.warning(f"twitter_accounts 内に辞書でない要素が含まれています: {acc_raw}")
                continue
            
            acc = dict(acc_raw)
            if 'enabled' not in acc:
                acc['enabled'] = True

            if not acc.get("account_id"):
                logger.warning(f"twitter_accounts 内のアカウント設定に account_id がありません: {acc}")
                continue
            processed_accounts.append(acc)
        
        if not processed_accounts: # 有効無効に関わらず、リストが空なら警告
            logger.warning("設定ファイルに twitter_accounts が見つからないか、有効なアカウント設定がありません。")
        return processed_accounts

    def get_active_twitter_accounts(self) -> List[Dict[str, Any]]:
        all_accounts = self.get_twitter_accounts()
        active_accounts = []
        for acc in all_accounts:
            if acc.get("enabled", False):
                active_accounts.append(acc)
        if not active_accounts:
            logger.warning("有効化 (enabled: true) されたTwitterアカウントが設定に一つも見つかりません。")
        return active_accounts

    def get_active_twitter_account_details(self, account_id: str) -> Optional[Dict[str, Any]]:
        accounts = self.get_active_twitter_accounts()
        for acc in accounts:
            # 比較前に両方を小文字に変換
            if acc.get("account_id", "").lower() == account_id.lower():
                required_keys = ["consumer_key", "consumer_secret", "access_token", "access_token_secret"]
                missing_keys = [key for key in required_keys if not acc.get(key) or not isinstance(acc.get(key), str)]
                if missing_keys:
                    logger.critical(f"アカウント {account_id} の設定に必須のTwitter APIキーが不足または不正です: {missing_keys}")
                    return None
                
                if isinstance(acc.get("google_sheets_source"), dict):
                    ws_name = acc["google_sheets_source"].get("worksheet_name")
                    if ws_name and isinstance(ws_name, str):
                         acc["spreadsheet_worksheet"] = ws_name
                    else:
                        logger.warning(f"アカウント {account_id} の google_sheets_source.worksheet_name が未設定または不正です。")
                else: 
                    logger.warning(f"アカウント {account_id} の設定に google_sheets_source (ワークシート名含む) がありません。")
                return acc
        return None

    def get_discord_webhook_url(self) -> Optional[str]:
        url = self.get("discord_webhook_url")
        if url and not isinstance(url, str):
            logger.warning(f"Discord Webhook URL (discord_webhook_url) が文字列ではありません。型: {type(url)}")
            return None
        if not url:
            logger.info("Discord Webhook URL (discord_webhook_url) が未設定です。Discord通知は行われません。")
        return url

    def get_spreadsheet_columns(self) -> Optional[List[str]]:
        columns = self.get("auto_post_bot.columns")
        logger.info(f"読み込まれたカラム設定 (get_spreadsheet_columns): {columns}")
        if columns is None:
            logger.critical("スプレッドシートのカラム設定 (auto_post_bot.columns) が見つかりません。")
            return None
        if not isinstance(columns, list) or not all(isinstance(item, str) for item in columns):
            logger.critical("スプレッドシート列定義 (auto_post_bot.columns) がリスト形式でないか、文字列以外の要素を含んでいます。")
            return None
        return columns

    def get_schedule_config(self) -> Optional[Dict[str, Any]]:
        cfg = self.get("auto_post_bot.schedule_settings")
        if not cfg or not isinstance(cfg, dict):
            logger.critical("スケジュール設定 (auto_post_bot.schedule_settings) が未設定または辞書形式ではありません。")
            return None
        return cfg

    def get_post_interval_hours(self) -> Optional[int]:
        """投稿間隔を時間単位で取得する。"""
        interval = self.get("auto_post_bot.schedule_settings.post_interval_hours")
        if interval is None:
            logger.warning("投稿間隔 (post_interval_hours) が設定されていません。")
            return None
        if isinstance(interval, int) and interval > 0:
            return interval
        logger.error(f"投稿間隔 (post_interval_hours: {interval}) の設定が不正です。正の整数である必要があります。")
        return None

    def get_posts_per_account_schedule(self) -> Optional[Dict[str, int]]:
        # ... (このメソッドは古いロジックの名残であり、現在は使用されていません)
        return None

    def should_notify_daily_schedule_summary(self) -> Optional[bool]:
        val = self.get("auto_post_bot.discord_notification.notify_daily_schedule_summary")
        if val is None:
            return None
        if not isinstance(val, bool):
            logger.warning(f"Discord日次サマリー通知設定の値 ({val}) がブール値ではありません。")
            return None
        return val