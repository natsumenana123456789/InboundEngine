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
