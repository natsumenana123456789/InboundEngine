import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# DEFAULT_CONFIG は廃止

class Config:
    def __init__(self):
        self._config_data: Dict[str, Any] = {}
        # config.py が engine_core の中にある前提でプロジェクトルートを推定
        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._load_settings()

    # _deep_update は DEFAULT_CONFIG とのマージがなくなったため不要。削除。

    def _load_settings(self):
        loaded_config_source = None
        config_json_str = None

        # 1. 環境変数 APP_CONFIG_JSON を試す (最優先)
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
            if acc.get("account_id") == account_id:
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
        
        required_files = ["schedule_file", "executed_file", "test_schedule_file", "test_executed_file"]
        for req_file_key in required_files:
            if not cfg.get(req_file_key) or not isinstance(cfg.get(req_file_key), str):
                logger.critical(f"スケジュール設定内の必須ファイルパス auto_post_bot.schedule_settings.{req_file_key} が未設定または文字列ではありません。")
                return None
        return cfg

    def get_posts_per_account_schedule(self) -> Optional[Dict[str, int]]:
        accounts = self.get_active_twitter_accounts()
        if not accounts:
            logger.warning("有効なTwitterアカウントがないため、アカウント別投稿数スケジュールを生成できません。")
            return None

        default_posts_val = self.get("auto_post_bot.posting_settings.posts_per_account")
        default_posts_per_account: Optional[int] = None
        if default_posts_val is not None:
            if isinstance(default_posts_val, int) and default_posts_val >= 0:
                default_posts_per_account = default_posts_val
            else:
                logger.warning(f"共通投稿数設定 (auto_post_bot.posting_settings.posts_per_account: {default_posts_val}) が不正(数値でないか負)です。無視されます。")
        
        schedule: Dict[str, int] = {}
        has_valid_schedule_entry = False
        for account in accounts:
            account_id = account.get("account_id")
            if not account_id: continue

            posts_today_val = account.get("posts_today")
            account_posts: Optional[int] = None

            if posts_today_val is not None:
                if isinstance(posts_today_val, int) and posts_today_val >= 0:
                    account_posts = posts_today_val
                else:
                    logger.warning(f"アカウント {account_id} の個別投稿数設定 (posts_today: {posts_today_val}) が不正(数値でないか負)です。共通設定を参照します。")
            
            if account_posts is not None:
                schedule[account_id] = account_posts
                has_valid_schedule_entry = True
            elif default_posts_per_account is not None:
                schedule[account_id] = default_posts_per_account
                has_valid_schedule_entry = True
            else:
                logger.info(
                    f"アカウント '{account_id}' の投稿数が個別にも共通設定にも有効に設定されていません。"
                    "このアカウントのスケジュールは投稿数0として扱われるか、処理対象外となる可能性があります。"
                )
        
        if not has_valid_schedule_entry: # 少なくとも1つのアカウントで投稿数が設定されているか
            logger.warning("有効なアカウント別投稿数スケジュールを一つも生成できませんでした。全アカウントの投稿数が未設定の可能性があります。")
            return None
        return schedule

    def should_notify_daily_schedule_summary(self) -> Optional[bool]:
        val = self.get("auto_post_bot.discord_notification.notify_daily_schedule_summary")
        if val is None:
            logger.info("Discord日次サマリー通知設定 (auto_post_bot.discord_notification.notify_daily_schedule_summary) が未設定です。")
            return None # 通知しない場合のデフォルトをNoneとするかFalseとするかは呼び出し元で判断
        if not isinstance(val, bool):
            logger.warning(f"Discord日次サマリー通知設定の値 ({val}) がブール値ではありません。")
            return None
        return val

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    current_script_path = os.path.abspath(__file__)
    engine_core_dir = os.path.dirname(current_script_path)
    project_root_for_test = os.path.dirname(engine_core_dir)
    config_dir_for_test = os.path.join(project_root_for_test, "config")
    # テスト専用の設定ファイル名に変更
    test_runner_config_file_name = "app_config.test_runner.json"
    dev_config_file_for_test = os.path.join(config_dir_for_test, test_runner_config_file_name)

    os.makedirs(config_dir_for_test, exist_ok=True)

    def cleanup_test_env():
        if "APP_CONFIG_JSON" in os.environ: del os.environ["APP_CONFIG_JSON"]
        # テスト専用ファイルのみを削除対象とする
        if os.path.exists(dev_config_file_for_test): os.remove(dev_config_file_for_test)

    logger.info("--- Config class self-tests (DEFAULT_CONFIG廃止版) START ---")

    # --- シナリオ1: 設定なし ---
    cleanup_test_env()
    # このシナリオでは、Configクラスが config/app_config.dev.json を探しに行くが、
    # テストコードはそれを作成しないので、ユーザーが作成したものがもしあればそれが読まれる。
    # ただし、テストとしては「何もない状態」をシミュレートしたいので、
    # もしユーザーの config/app_config.dev.json が存在すると、このテストシナリオ1の純粋性が損なわれる。
    # より厳密にするなら、テスト実行前にユーザーのファイルも一時的にリネームするなどの工夫が必要だが、
    # ここではテスト専用ファイルに影響を与えないことを主眼とする。
    logger.info("[Test Scenario 1] No config source (relies on no app_config.dev.json existing or APP_CONFIG_JSON being unset outside this test)...")
    config1 = Config() 
    # シナリオ1の検証は、ユーザーの環境に app_config.dev.json が *ない* ことを前提とする。
    # もしあれば、その内容次第で以下のassertは失敗する可能性がある。
    # ここでは、テストコードがユーザーのファイルを削除しないことを優先し、
    # シナリオ1の完全な独立性は少し犠牲になる。
    if not os.path.exists(os.path.join(config_dir_for_test, "app_config.dev.json")) and "APP_CONFIG_JSON" not in os.environ:
        assert config1._config_data == {}, "Scenario 1 Failed: config_data should be empty if no user config exists"
        assert config1.get_log_level() is None, "Scenario 1 Failed: LogLevel should be None if no user config exists"
        assert config1.get_spreadsheet_id() is None, "Scenario 1 Failed: SpreadsheetID should be None if no user config exists"
        logger.info("  Scenario 1 OK (CRITICAL logs expected for missing config source).")
    else:
        logger.warning("  Scenario 1 SKIPPED or behavior depends on existing user configuration (app_config.dev.json or APP_CONFIG_JSON).")


    # --- シナリオ2: テスト専用ファイルからロード (最小限の必須設定) ---
    cleanup_test_env() # test_runner_config_file_name のファイルを消す
    logger.info(f"[Test Scenario 2] Loading from test runner file: {dev_config_file_for_test} (minimal)...")
    dev_file_content_s2 = {
        "common": {"log_level": "DEBUG", "logs_directory": "dev_logs"},
        "google_sheets": {
            "spreadsheet_id": "dev_sheet_id_s2", 
            # service_account_credentials を直接オブジェクトとして記述
            "service_account_credentials": {"type":"service_account", "project_id": "dev_project_s2"}
        },
        "twitter_accounts": [{
            "account_id": "dev_user_s2", "enabled": True, 
            "consumer_key":"k", "consumer_secret":"s", "access_token":"t", "access_token_secret":"as"
        }],
        "auto_post_bot": {
            "columns": ["ID", "Text"],
            "schedule_settings": {
                "schedule_file": "s.json", "executed_file": "e.log", 
                "test_schedule_file": "ts.json", "test_executed_file": "te.log"
            }
        }
    }
    with open(dev_config_file_for_test, 'w', encoding='utf-8') as f: json.dump(dev_file_content_s2, f)
    
    config2 = Config()
    assert config2.get_log_level() == "DEBUG", "Scenario 2 Failed: LogLevel"
    assert config2.get_logs_directory() == "dev_logs", "Scenario 2 Failed: LogsDirectory"
    assert config2.get_spreadsheet_id() == "dev_sheet_id_s2", "Scenario 2 Failed: SpreadsheetID"
    assert config2.get_gspread_service_account_dict() == {"type":"service_account", "project_id": "dev_project_s2"}, "Scenario 2 Failed: GSpreadCreds"
    assert len(config2.get_active_twitter_accounts()) == 1, "Scenario 2 Failed: ActiveTwitterAccounts"
    active_acc_details_s2 = config2.get_active_twitter_account_details("dev_user_s2")
    assert active_acc_details_s2 is not None and active_acc_details_s2.get("consumer_key") == "k", "Scenario 2 Failed: DevUser Details"
    assert config2.get_spreadsheet_columns() == ["ID", "Text"], "Scenario 2 Failed: Columns"
    assert config2.get_schedule_config() is not None, "Scenario 2 Failed: ScheduleConfig"
    logger.info("  Scenario 2 OK.")

    # --- シナリオ3: 環境変数からロード (テスト専用ファイルより優先) ---
    cleanup_test_env() # test_runner_config_file_name のファイルを消す
    # ダミーのテスト専用開発ファイル
    with open(dev_config_file_for_test, 'w', encoding='utf-8') as f: json.dump({"common":{"log_level":"INFO"}}, f)

    logger.info("[Test Scenario 3] Loading from ENV var (priority over test runner file)..")
    env_var_content_s3 = {
        "common": {"log_level": "WARNING", "logs_directory": "env_logs_s3"},
        "google_sheets": {
            "spreadsheet_id": "env_sheet_id_s3", 
            # service_account_credentials を直接オブジェクトとして記述
            "service_account_credentials": {"env_key":"val", "project_id": "env_project_s3"}
        },
        "twitter_accounts": [{
            "account_id": "env_user_s3", "enabled": True, 
            "consumer_key":"ek", "consumer_secret":"es", "access_token":"et", "access_token_secret":"eas"
        }],
        "auto_post_bot": { 
            "columns": ["EnvCol1"],
             "schedule_settings": { # schedule_settings も完備
                "schedule_file": "s_env.json", "executed_file": "e_env.log", 
                "test_schedule_file": "ts_env.json", "test_executed_file": "te_env.log"
            }
        }
    }
    os.environ["APP_CONFIG_JSON"] = json.dumps(env_var_content_s3)

    config3 = Config()
    assert config3.get_log_level() == "WARNING", "Scenario 3 Failed: LogLevel"
    assert config3.get_logs_directory() == "env_logs_s3", "Scenario 3 Failed: LogsDirectory"
    assert config3.get_spreadsheet_id() == "env_sheet_id_s3", "Scenario 3 Failed: SpreadsheetID"
    assert config3.get_gspread_service_account_dict() == {"env_key":"val", "project_id": "env_project_s3"}, "Scenario 3 Failed: GSpreadCreds"
    active_acc_details_s3 = config3.get_active_twitter_account_details("env_user_s3")
    assert active_acc_details_s3 is not None and active_acc_details_s3.get("consumer_key") == "ek", "Scenario 3 Failed: EnvUser Details"
    assert config3.get_spreadsheet_columns() == ["EnvCol1"], "Scenario 3 Failed: Columns"
    assert config3.get_schedule_config() is not None, "Scenario 3 Failed: ScheduleConfig should be present"
    logger.info("  Scenario 3 OK.")


    # --- シナリオ4: 必須項目が欠けたテスト専用ファイル ---
    cleanup_test_env() # test_runner_config_file_name のファイルを消す
    logger.info(f"[Test Scenario 4] Loading from test runner file with missing critical parts: {dev_config_file_for_test}...")
    # google_sheets セクション全体、twitter_accounts 配列が空、auto_post_bot.columns, auto_post_bot.schedule_settings なし
    dev_file_content_s4_missing = { 
        "common": {"log_level": "INFO", "logs_directory": "logs_s4"},
        "twitter_accounts": [] 
    }
    with open(dev_config_file_for_test, 'w', encoding='utf-8') as f: json.dump(dev_file_content_s4_missing, f)
    
    config4 = Config()
    assert config4.get_log_level() == "INFO", "Scenario 4 Failed: LogLevel"
    assert config4.get_spreadsheet_id() is None, "Scenario 4 Failed: SpreadsheetID (CRITICAL log expected)"
    assert config4.get_gspread_service_account_dict() is None, "Scenario 4 Failed: GSpreadCreds (CRITICAL log expected)"
    assert len(config4.get_twitter_accounts()) == 0, "Scenario 4 Failed: TwitterAccounts" # 警告ログ期待
    assert config4.get_spreadsheet_columns() is None, "Scenario 4 Failed: Columns (CRITICAL log expected)"
    assert config4.get_schedule_config() is None, "Scenario 4 Failed: ScheduleConfig (CRITICAL log expected)"
    logger.info("  Scenario 4 OK (CRITICAL/WARNING logs expected for missing sections).")

    cleanup_test_env()
    logger.info("--- Config class self-tests (DEFAULT_CONFIG廃止版) FINISHED ---") 