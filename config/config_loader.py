import os
# import json # jsonモジュールをインポート -> yamlに変更
import yaml # yamlモジュールをインポート
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Union, Optional # Union, Optional をインポート
# from dotenv import load_dotenv, find_dotenv # find_dotenv をインポート
import sys

# .envファイルから環境変数を読み込む (モジュール読み込み時に一度だけ実行)
# まずは find_dotenv() で .env ファイルのパスを探す (プロジェクトルートにあるはず)
# dotenv_path = find_dotenv(filename='.env', raise_error_if_not_found=False, usecwd=True) # usecwd=Trueでカレント作業ディレクトリも検索対象に含める
# print(f"DEBUG: find_dotenv() path: {dotenv_path}") # .envのパス確認

# found_dotenv = False
# if dotenv_path: # パスが見つかればそれを読み込む
#     found_dotenv = load_dotenv(dotenv_path=dotenv_path)
# else: # 見つからなければ、従来通り親ディレクトリを遡って探す (フォールバック)
#     found_dotenv = load_dotenv() # この場合、以前の print(f"DEBUG: load_dotenv() result: {found_dotenv}") の found_dotenv はここを参照する

# 既存のデバッグプリントは残す (if dotenv_path else ブロックの外で共通の found_dotenv 変数を見る形でも良いし、それぞれの結果を見る形でも良い)
# print(f"DEBUG: load_dotenv() result: {found_dotenv}") # これは↑の分岐後の found_dotenv の値
# より明確にするため、どの load_dotenv が呼ばれたかの結果を見る
# if dotenv_path:
#     print(f"DEBUG: load_dotenv(dotenv_path='{dotenv_path}') result: {found_dotenv}")
# else:
#     print(f"DEBUG: load_dotenv() (auto-search) result: {found_dotenv}")

# print(f"DEBUG: TWITTER_BEARER_TOKEN from env after load_dotenv: {os.getenv('TWITTER_BEARER_TOKEN')}")

# ============================
# ✅ 定数定義（目的と意味付き）
# ============================

# Google サービスアカウントの認証鍵ファイル名
# config.yml の common.file_paths.google_key_file から取得する
# GOOGLE_KEY_FILE = "gspread-key.json" # 旧定義

# Google Sheets / Drive API にアクセスするためのスコープ（権限）
GOOGLE_API_SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

# 設定情報を取得するスプレッドシートの名称（ファイル名）
# config.yml の auto_post_bot.google_sheets_source.sheet_name などから取得
# DEFAULT_CONFIG_SHEET_NAME = "アカウント設定DB群" # 旧定義

# 上記スプレッドシート内の "設定" 用タブ（ワークシート）の名称
# config.yml の auto_post_bot.google_sheets_source.worksheet_name などから取得
# DEFAULT_CONFIG_WORKSHEET_NAME = "運用アカウント情報" # 旧定義

# メインの設定ファイルパス (config.yml に変更)
# SETTINGS_FILE_PATH = os.path.join(os.path.dirname(__file__), "settings.json") # 旧定義
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "config.yml") # 新定義
CONFIG_DIR = os.path.dirname(__file__) # configディレクトリのパス

_config_cache = None
_env_loaded = False # .env読み込み済みフラグ (load_dotenv()がグローバルなので不要かもだが念のため)

def _load_config_from_yaml_once():
    global _config_cache
    _config_cache = None # ★★★ 強制的にキャッシュをクリアして再読み込み ★★★
    if _config_cache is not None:
        return _config_cache
    
    config_from_yaml = {}
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"⚠️ 設定ファイルが見つかりません: {CONFIG_FILE_PATH}。")
    else:
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                config_from_yaml = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"❌ 設定ファイル ({CONFIG_FILE_PATH}) のYAML形式が正しくありません: {e}")
        except Exception as e:
            raise RuntimeError(f"❌ 設定ファイル ({CONFIG_FILE_PATH}) の読み込み中にエラーが発生しました: {e}")

    # config.yml の値を直接使用する (os.getenv を削除)
    
    # Notion
    notion_config_original = config_from_yaml.get("notion", {}) # 元のnotionセクション全体を取得
    config_from_yaml["notion"] = { # 新しい辞書として格納
        "token": notion_config_original.get("token"),
        "databases": notion_config_original.get("databases", {}) # databases セクションもコピー
    }

    # Gemini API
    gemini_config = config_from_yaml.get("gemini_api", {})
    config_from_yaml["gemini_api"] = {"api_key": gemini_config.get("api_key"), "service_account_file": gemini_config.get("service_account_file")}

    # OpenAI API
    openai_config = config_from_yaml.get("openai_api", {})
    config_from_yaml["openai_api"] = {"api_key": openai_config.get("api_key")}

    # Twitter API
    twitter_api_config = config_from_yaml.get("twitter_api", {})
    config_from_yaml["twitter_api"] = {
        "bearer_token": twitter_api_config.get("bearer_token"),
        "consumer_key": twitter_api_config.get("consumer_key"),
        "consumer_secret": twitter_api_config.get("consumer_secret"),
        "access_token": twitter_api_config.get("access_token"),
        "access_token_secret": twitter_api_config.get("access_token_secret"),
        "user_id_cache": twitter_api_config.get("user_id_cache", {})
    }

    # Curate Bot Twitter Account
    curate_bot_config_original = config_from_yaml.get("curate_bot", {})
    curate_bot_accounts_original = curate_bot_config_original.get("twitter_accounts", [])
    # ここでは active_curation_account_id や twitter_accounts の email/username/password は
    # config.yml に直接書かれている値をそのまま使うため、os.getenvによる上書きロジックは削除。
    # 必要な値は config.yml に直接記述されている前提とする。
    config_from_yaml["curate_bot"] = curate_bot_config_original # 元の値をそのまま使う

    # Auto Post Bot Twitter Account
    auto_post_bot_config_original = config_from_yaml.get("auto_post_bot", {})
    auto_post_bot_accounts_original = auto_post_bot_config_original.get("twitter_accounts", [])
    # 同様に、config.yml に直接書かれている値をそのまま使う
    config_from_yaml["auto_post_bot"] = auto_post_bot_config_original # 元の値をそのまま使う

    # Twitter Login Info (スクレイピング用などのグローバルなログイン情報)
    twitter_login_info_config = config_from_yaml.get("twitter_login_info", {})
    config_from_yaml["twitter_login_info"] = {
        "username": twitter_login_info_config.get("username"),
        "password": twitter_login_info_config.get("password")
        # 必要であれば email も追加
    }

    # Google Drive
    curate_bot_google_drive_config = config_from_yaml.get("curate_bot", {}).get("google_drive", {})
    if "curate_bot" in config_from_yaml: # curate_bot セクションがある場合のみ
        config_from_yaml["curate_bot"].setdefault("google_drive", {})["folder_id"] = curate_bot_google_drive_config.get("folder_id")

    _config_cache = config_from_yaml
    # ★★★ デバッグ出力追加 ★★★
    if _config_cache and "twitter_api" in _config_cache:
        print(f"DEBUG: [_load_config_from_yaml_once] twitter_api section loaded: {_config_cache.get('twitter_api')}")
    else:
        print("DEBUG: [_load_config_from_yaml_once] twitter_api section NOT FOUND or config_cache is None.")
    # ★★★ デバッグ出力ここまで ★★★
    return _config_cache

def get_full_config():
    """設定ファイル全体を読み込んで返す（主に内部利用やデバッグ用）"""
    return _load_config_from_yaml_once()

def get_common_config():
    """共通設定セクションを取得する"""
    config = get_full_config()
    return config.get("common", {})

def get_bot_config(bot_name: str):
    """
    指定されたボットの設定を取得する。
    アクティブなTwitterアカウント情報やUser-Agentを解決して含める。
    """
    config = get_full_config()
    bot_specific_config = config.get(bot_name, {}).copy()

    active_account_id_key = f"active_{bot_name.replace('_bot', '')}_account_id"
    active_account_id = bot_specific_config.get(active_account_id_key)
    
    resolved_twitter_account = None
    twitter_accounts_list = bot_specific_config.get("twitter_accounts", [])
    if active_account_id:
        for acc in twitter_accounts_list:
            if acc.get("account_id") == active_account_id:
                resolved_twitter_account = acc
                break
    elif twitter_accounts_list:
        resolved_twitter_account = twitter_accounts_list[0]
    
    if resolved_twitter_account:
        bot_specific_config["twitter_account"] = resolved_twitter_account
    else:
        bot_specific_config["twitter_account"] = {}

    common_config = get_common_config()
    if bot_specific_config.get("user_agents") is None: 
        bot_specific_config["user_agents"] = common_config.get("default_user_agents", [])
    
    return bot_specific_config

def get_gemini_api_key():
    """Gemini APIキーをconfig.ymlから取得する"""
    config = get_full_config() # キャッシュされた設定全体を取得
    gemini_config = config.get("gemini_api", {})
    return gemini_config.get("api_key")

# ============================
# ✅ 設定読み込みエントリーポイント
# ============================

def load_config():
    """
    config.yml から設定を読み込み、key-value 形式の辞書を返す。
    （注意: この関数はキャッシュを利用しません。通常は get_full_config() を使用してください。）
    スプレッドシートからの設定読み込みは load_config_from_sheet() を別途呼び出す。
    """
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"❌ 設定ファイルが見つかりません: {CONFIG_FILE_PATH}")
        return {}
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        return config_data
    except yaml.YAMLError as e:
        print(f"❌ 設定ファイル ({CONFIG_FILE_PATH}) のYAML形式が正しくありません: {e}")
        return {}
    except Exception as e:
        print(f"❌ 設定ファイル ({CONFIG_FILE_PATH}) の読み込み中にエラーが発生しました: {e}")
        return {}

# ============================
# ✅ スプレッドシートから設定情報を取得 (必要に応じて個別呼び出し)
# ============================

def load_config_from_sheet(
    sheet_name: str,
    worksheet_name: str,
    key_file_path: str
):
    actual_key_file_path = os.path.join(CONFIG_DIR, key_file_path) if not os.path.isabs(key_file_path) else key_file_path

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(actual_key_file_path, GOOGLE_API_SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        rows = sheet.get_all_values()
        return {row[0]: row[1] for row in rows if len(row) >= 2 and row[0]}
    except FileNotFoundError:
        print(f"❌ Googleサービスアカウントのキーファイルが見つかりません: {actual_key_file_path}")
        return {}
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ スプレッドシートが見つかりません: {sheet_name}")
        return {}
    except gspread.exceptions.WorksheetNotFound:
        print(f"❌ ワークシートが見つかりません: {worksheet_name} (シート: {sheet_name})")
        return {}
    except Exception as e:
        print(f"❌ スプレッドシートからの設定読み込み中にエラー: {e}")
        return {}

def load_records_from_sheet(
    sheet_name: str,
    worksheet_name: str,
    key_file_path: str
) -> list[dict]:
    """
    指定されたGoogleスプレッドシートのワークシートから全てのレコードを
    辞書のリストとして取得する。各辞書は1行を表し、キーはヘッダー行の値。
    """
    actual_key_file_path = os.path.join(CONFIG_DIR, key_file_path) if not os.path.isabs(key_file_path) else key_file_path
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(actual_key_file_path, GOOGLE_API_SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        records = sheet.get_all_records() # ヘッダーをキーとした辞書のリストを取得
        return records
    except FileNotFoundError:
        print(f"❌ Googleサービスアカウントのキーファイルが見つかりません: {actual_key_file_path}")
        return [] # 空のリストを返す
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ スプレッドシートが見つかりません: {sheet_name}")
        return []
    except gspread.exceptions.WorksheetNotFound:
        print(f"❌ ワークシートが見つかりません: {worksheet_name} (シート: {sheet_name})")
        return []
    except Exception as e:
        print(f"❌ スプレッドシートからのレコード読み込み中にエラー: {e}")
        return []

def find_row_index_by_id(sheet_obj, id_column_header: str, target_id: str) -> Optional[int]:
    """
    指定されたgspreadシートオブジェクト内で、ID列のヘッダー名とターゲットIDを使って
    該当する行のインデックス (1オリジン) を検索する。
    見つからない場合は None を返す。
    """
    try:
        id_list = sheet_obj.col_values(sheet_obj.find(id_column_header).col)
        # ヘッダー行を除外して検索する場合があるため、IDが見つかったインデックスに +1 する。
        # col_values はリストなので0オリジン。gspreadの行番号は1オリジン。
        for i, cell_value in enumerate(id_list):
            if str(cell_value) == str(target_id):
                return i + 1 # gspreadの行インデックスは1から始まる
        return None
    except gspread.exceptions.CellNotFound:
        print(f"⚠️ ID列ヘッダー '{id_column_header}' がシート内に見つかりませんでした。")
        return None
    except Exception as e:
        print(f"⚠️ IDによる行検索中にエラー: {e}")
        return None

def update_cell_in_sheet(sheet_name: str, worksheet_name: str, key_file_path: str, target_row_index: int, target_col_index: int, new_value: str):
    """
    指定されたGoogleスプレッドシートの特定のセルを新しい値で更新する。
    target_row_index と target_col_index は1オリジン。
    """
    actual_key_file_path = os.path.join(CONFIG_DIR, key_file_path) if not os.path.isabs(key_file_path) else key_file_path
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(actual_key_file_path, GOOGLE_API_SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        sheet.update_cell(target_row_index, target_col_index, new_value)
        print(f"✅ スプレッドシート ({sheet_name} - {worksheet_name}) のセル ({target_row_index}, {target_col_index}) を '{new_value}' に更新しました。")
        return True
    except FileNotFoundError:
        print(f"❌ Googleサービスアカウントのキーファイルが見つかりません: {actual_key_file_path}")
        return False
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ スプレッドシートが見つかりません: {sheet_name}")
        return False
    except gspread.exceptions.WorksheetNotFound:
        print(f"❌ ワークシートが見つかりません: {worksheet_name} (シート: {sheet_name})")
        return False
    except Exception as e:
        print(f"❌ スプレッドシートのセル更新中にエラー: {e}")
        return False

# ============================
# ✅ デバッグ用コード（単体実行時）
# ============================

if __name__ == "__main__":
    from pprint import pprint

    print("\n📘 メイン設定 (config.yml) の確認:")
    main_settings = get_full_config()
    pprint(main_settings)

    if main_settings:
        print("\n✅ 検証：config.yml に主要なキーがあるか")
        required_top_keys = ["twitter_account", "scraping", "notion", "posting", "google_sheets", "scheduler", "file_paths"]
        for key in required_top_keys:
            if key in main_settings:
                print(f"  ✅ {key} が存在します。")
            else:
                print(f"  ❌ {key} が見つかりません。")
        
        if "twitter_account" in main_settings and "username" in main_settings["twitter_account"]:
            print(f"  👤 Twitter Username: {main_settings['twitter_account']['username']}")
        else:
            print("  ❌ Twitter username が見つかりません。")

    print("\n📊 スプレッドシートからの設定読み込みテスト:")
    common_conf = get_common_config()
    gkey_file = common_conf.get("file_paths", {}).get("google_key_file")
    
    autopost_conf = get_bot_config("auto_post_bot")
    sheet_cfg = {}
    if autopost_conf and autopost_conf.get("google_sheets_source", {}).get("enabled") and gkey_file:
        gs_source = autopost_conf.get("google_sheets_source")
        sheet_n = gs_source.get("sheet_name")
        worksheet_n = gs_source.get("worksheet_name")
        if sheet_n and worksheet_n:
            print(f"Attempting to load from GSheet: {sheet_n} - {worksheet_n} using key: {gkey_file}")
            sheet_cfg = load_config_from_sheet(sheet_name=sheet_n, worksheet_name=worksheet_n, key_file_path=gkey_file)
    
    if sheet_cfg:
        print("  スプレッドシートから以下の設定が読み込まれました:")
        pprint(sheet_cfg)
    else:
        print("  スプレッドシートからの設定読み込みに失敗したか、設定が空、または設定が無効でした。")

    print("--- Common Config ---")
    pprint(get_common_config())

    print("\n--- Curate Bot Config ---")
    curate_cfg = get_bot_config("curate_bot")
    pprint(curate_cfg)
    if curate_cfg:
        print(f"  Curate Bot - Active Twitter Username: {curate_cfg.get('twitter_account',{}).get('username')}")
        if curate_cfg.get('user_agents'):
            print(f"  Curate Bot - User Agents (first one): {curate_cfg.get('user_agents',[])[0]}")
        else:
            print("  Curate Bot - User Agents: Not Set or Empty")

    print("\n--- Auto Post Bot Config ---")
    autopost_cfg = get_bot_config("auto_post_bot")
    pprint(autopost_cfg)
    if autopost_cfg:
        print(f"  AutoPost Bot - Active Twitter Username: {autopost_cfg.get('twitter_account',{}).get('username')}")
        gs_source = autopost_cfg.get("google_sheets_source")
        if gs_source and gs_source.get("enabled"):
            print(f"  AutoPost Bot - GSheets Sheet Name: {gs_source.get('sheet_name')}")

    print("\n--- Analyze Bot Config (should be None if disabled or not found) ---")
    analyze_cfg = get_bot_config("analyze_bot")
    pprint(analyze_cfg)

    # print("\n--- Full Raw Config (for debugging) ---")
    # pprint(get_full_config())

def get_config():
    """config.yml全体を読み込んで返す"""
    if _config_cache: # 既にキャッシュがあればそれを返すことで、twitter_apiセクションなども含めた全体が返る
        # ただし、最初にload_configやget_bot_configなどが呼ばれて部分的にキャッシュされている場合、
        # 全体が含まれていない可能性があるので、キャッシュ戦略を見直すか、常にファイルから読み直すか検討が必要。
        # ここでは、_config_cacheに全体が入っていることを期待する。
        # もし_config_cacheがload_config等でボット固有設定のみになっている場合、不整合が起きる。
        # より安全なのは、常にファイルから読み直すか、_config_cacheを確実に全体を保持するように修正すること。
        # 現状の_config_cacheの使われ方だと、最初に呼ばれた関数の結果がキャッシュされるため、
        # get_configが最初に呼ばれれば問題ないが、そうでない場合は不完全なキャッシュかもしれない。
        # 一旦、ファイルから常に読み込むように修正する方が安全か。
        pass # 下のファイル読み込みに処理を継続させる

    # キャッシュがあっても、twitter_apiのようなトップレベルのセクションを確実に含めるため、
    # 常にファイルから全体を読み込み、それをキャッシュにマージ（または上書き）する方針が良いかもしれない。
    # ただし、_config_cache の意図（一度読み込んだ設定は変更されない前提での高速化）と衝突する可能性も。

    # 現状のconfig_loaderの設計では、_config_cacheは起動時に一度だけ全量読み込まれることを想定しているように見える。
    # load_config() がそれを担っていたが、get_bot_config() などに置き換わった。
    # get_bot_config や get_common_config は _config_cache があればそれを使う。
    # なので、_config_cache に最初に全量データが入っていれば問題ない。
    # 起動時に一度、全量を読み込んでキャッシュに格納する処理がどこかで行われているか確認が必要。
    # もしそのような処理がない場合、get_config() が呼ばれるたびにファイルを読むことになる。

    # load_config()関数が以前その役割を担っていたようなので、それに近い形で実装する。
    # loggerのインポートがここにあるか確認。なければ標準エラー出力。
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        if config_data: # 読み込み成功かつデータあり
            _config_cache.clear() # 既存のキャッシュをクリアして新しい全体データで更新
            _config_cache.update(config_data)
            return _config_cache.copy() # copyを返すのが安全
        else:
            print(f"WARNING: 設定ファイルは空か、読み込みに失敗しました: {CONFIG_FILE_PATH}", file=sys.stderr)
            return {}
    except FileNotFoundError:
        print(f"ERROR: 設定ファイルが見つかりません: {CONFIG_FILE_PATH}", file=sys.stderr)
        return {}
    except yaml.YAMLError as e:
        print(f"ERROR: 設定ファイルの解析に失敗しました: {e}", file=sys.stderr)
        return {}
