import os
import json # jsonモジュールをインポート
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ============================
# ✅ 定数定義（目的と意味付き）
# ============================

# Google サービスアカウントの認証鍵ファイル名
# Google Cloud Console から発行した JSON ファイルのパスを指定します。
# これは settings.json の file_paths.google_key_file から取得することを検討
GOOGLE_KEY_FILE = "gspread-key.json" # 当面はこのまま

# Google Sheets / Drive API にアクセスするためのスコープ（権限）
GOOGLE_API_SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

# 設定情報を取得するスプレッドシートの名称（ファイル名）
# settings.json の google_sheets.sheet_name から取得することを検討
DEFAULT_CONFIG_SHEET_NAME = "アカウント設定DB群" # 当面はこのまま

# 上記スプレッドシート内の "設定" 用タブ（ワークシート）の名称
# settings.json の google_sheets.worksheet_name から取得することを検討
DEFAULT_CONFIG_WORKSHEET_NAME = "運用アカウント情報" # 当面はこのまま

# メインの設定ファイルパス (settings.json)
# このローダー自身の場所を基準に config/settings.json を指すようにする
SETTINGS_FILE_PATH = os.path.join(os.path.dirname(__file__), "settings.json")
CONFIG_DIR = os.path.dirname(__file__) # configディレクトリのパス

_config_cache = None

def _load_settings_from_json_once():
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    
    if not os.path.exists(SETTINGS_FILE_PATH):
        raise FileNotFoundError(f"❌ 設定ファイルが見つかりません: {SETTINGS_FILE_PATH}")
    try:
        with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
        return _config_cache
    except json.JSONDecodeError as e:
        raise ValueError(f"❌ 設定ファイル ({SETTINGS_FILE_PATH}) のJSON形式が正しくありません: {e}")
    except Exception as e:
        raise RuntimeError(f"❌ 設定ファイル ({SETTINGS_FILE_PATH}) の読み込み中にエラーが発生しました: {e}")

def get_full_config():
    """設定ファイル全体を読み込んで返す（主に内部利用やデバッグ用）"""
    return _load_settings_from_json_once()

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
    # ボット設定セクションをコピーして変更（元のキャッシュに影響を与えないため）
    bot_specific_config = config.get(bot_name, {}).copy()

    if not bot_specific_config or not bot_specific_config.get("enabled", False):
        # print(f"ボット '{bot_name}' の設定が見つからないか、無効になっています。")
        return None

    # Twitterアカウント情報の解決
    active_account_id_key = f"active_{bot_name.replace('_bot', '')}_account_id"
    active_account_id = bot_specific_config.get(active_account_id_key)
    
    resolved_twitter_account = None
    twitter_accounts_list = bot_specific_config.get("twitter_accounts", [])
    if active_account_id:
        for acc in twitter_accounts_list:
            if acc.get("account_id") == active_account_id:
                resolved_twitter_account = acc
                break
    elif twitter_accounts_list: # active_id指定がないがリストにアカウントがあれば最初の一つを使う
        resolved_twitter_account = twitter_accounts_list[0]
        # print(f"警告: ボット '{bot_name}' のアクティブなTwitterアカウントIDが指定されていません。リストの最初のアカウントを使用します。")
    
    if resolved_twitter_account:
        bot_specific_config["twitter_account"] = resolved_twitter_account
    else:
        # print(f"警告: ボット '{bot_name}' に有効なTwitterアカウント設定が見つかりません。")
        bot_specific_config["twitter_account"] = {} # フォールバックとして空の辞書

    # User-Agentの解決
    common_config = get_common_config()
    # ボット個別指定がない (null or 未定義) 場合に共通設定を使用
    if bot_specific_config.get("user_agents") is None: 
        bot_specific_config["user_agents"] = common_config.get("default_user_agents", [])
    
    return bot_specific_config

# ============================
# ✅ 設定読み込みエントリーポイント
# ============================

def load_config():
    """
    settings.json から設定を読み込み、key-value 形式の辞書を返す。
    スプレッドシートからの設定読み込みは load_config_from_sheet() を別途呼び出す。
    """
    return load_settings_from_json()

def load_settings_from_json(file_path=SETTINGS_FILE_PATH):
    """
    指定されたJSONファイルから設定を読み込む。
    """
    if not os.path.exists(file_path):
        print(f"❌ 設定ファイルが見つかりません: {file_path}")
        # より堅牢にするなら、ここで例外を発生させるか、空の辞書やNoneを返すかなど検討
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        return config_data
    except json.JSONDecodeError as e:
        print(f"❌ 設定ファイル ({file_path}) のJSON形式が正しくありません: {e}")
        return {}
    except Exception as e:
        print(f"❌ 設定ファイル ({file_path}) の読み込み中にエラーが発生しました: {e}")
        return {}

# ============================
# ✅ スプレッドシートから設定情報を取得 (必要に応じて個別呼び出し)
# ============================

def load_config_from_sheet(
    sheet_name=DEFAULT_CONFIG_SHEET_NAME, 
    worksheet_name=DEFAULT_CONFIG_WORKSHEET_NAME,
    key_file_path=GOOGLE_KEY_FILE # settings.jsonから渡せるように引数追加も検討
):
    # key_file_path は settings.json の file_paths.google_key_file を参照するように変更も検討
    # 例: config_settings = load_settings_from_json()
    # key_file_path = os.path.join(os.path.dirname(SETTINGS_FILE_PATH), config_settings.get("file_paths",{}).get("google_key_file"))
    # sheet_name = config_settings.get("google_sheets", {}).get("sheet_name", DEFAULT_CONFIG_SHEET_NAME)
    # worksheet_name = config_settings.get("google_sheets", {}).get("worksheet_name", DEFAULT_CONFIG_WORKSHEET_NAME)

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(key_file_path, GOOGLE_API_SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        rows = sheet.get_all_values()
        # key-value 形式で辞書化して返す (ヘッダー行をキーにする場合などは別途処理が必要)
        # 現在の実装は1列目をキー、2列目を値としている
        return {row[0]: row[1] for row in rows if len(row) >= 2 and row[0]}
    except FileNotFoundError:
        print(f"❌ Googleサービスアカウントのキーファイルが見つかりません: {key_file_path}")
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

# ============================
# ✅ デバッグ用コード（単体実行時）
# ============================

if __name__ == "__main__":
    from pprint import pprint

    print("\n📘 メイン設定 (settings.json) の確認:")
    main_settings = load_config()
    pprint(main_settings)

    if main_settings:
        print("\n✅ 検証：settings.json に主要なキーがあるか")
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
    # スプレッドシートからの読み込みには認証情報が必要なため、
    # 環境によっては `GOOGLE_KEY_FILE` のパスが正しいか、ファイルが存在するか確認が必要。
    # 必要であれば、settings.jsonからキーファイルのパスやシート名を取得するように修正してください。
    sheet_config = load_config_from_sheet()
    if sheet_config:
        print("  スプレッドシートから以下の設定が読み込まれました:")
        pprint(sheet_config)
    else:
        print("  スプレッドシートからの設定読み込みに失敗したか、設定が空でした。")

    # 以前の load_account_info() に相当する機能は、main_settings や sheet_config を
    # 適宜組み合わせて利用する形になります。
    # 例えば、Twitterアカウント情報は main_settings["twitter_account"] から取得します。

    # print("\n👤 アカウント情報一覧:") # 以前のものは accounts.json 前提だったためコメントアウト
    # accounts = load_account_info() # この関数は削除または再設計が必要
    # pprint(accounts)

    print("--- Common Config ---")
    pprint(get_common_config())

    print("\n--- Curate Bot Config ---")
    curate_cfg = get_bot_config("curate_bot")
    pprint(curate_cfg)
    if curate_cfg:
        print(f"  Curate Bot - Active Twitter Username: {curate_cfg.get('twitter_account',{}).get('username')}")
        print(f"  Curate Bot - User Agents (first one): {curate_cfg.get('user_agents',[])[0] if curate_cfg.get('user_agents') else 'N/A'}")

    print("\n--- Auto Post Bot Config ---")
    autopost_cfg = get_bot_config("auto_post_bot")
    pprint(autopost_cfg)
    if autopost_cfg:
        print(f"  AutoPost Bot - Active Twitter Username: {autopost_cfg.get('twitter_account',{}).get('username')}")
        gs_source = autopost_cfg.get("google_sheets_source")
        if gs_source and gs_source.get("enabled"):
            print(f"  AutoPost Bot - GSheets Sheet Name: {gs_source.get('sheet_name')}")
            # records = load_records_from_sheet(gs_source.get('sheet_name'), gs_source.get('worksheet_name'))
            # print(f"    GSheet Records (first 2 if any): {records[:2] if records else 'No records'}")

    print("\n--- Analyze Bot Config (should be None if disabled or not found) ---")
    analyze_cfg = get_bot_config("analyze_bot")
    pprint(analyze_cfg)

    # print("\n--- Full Raw Config (for debugging) ---")
    # pprint(get_full_config())
