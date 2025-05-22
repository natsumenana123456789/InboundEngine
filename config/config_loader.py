import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ============================
# ✅ 定数定義（目的と意味付き）
# ============================

# Google サービスアカウントの認証鍵ファイル名
# Google Cloud Console から発行した JSON ファイルのパスを指定します。
GOOGLE_KEY_FILE = "gspread-key.json"

# Google Sheets / Drive API にアクセスするためのスコープ（権限）
# スプレッドシートの読み書きやドライブ上のファイル参照に必要です。
GOOGLE_API_SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

# 設定情報を取得するスプレッドシートの名称（ファイル名）
# これは Google Drive 上に存在するスプレッドシートのタイトルと一致している必要があります。
DEFAULT_CONFIG_SHEET_NAME = "アカウント設定DB群"

# 上記スプレッドシート内の "設定" 用タブ（ワークシート）の名称
# このタブには `key,value` 形式で設定情報を記述しておくことを前提とします。
DEFAULT_CONFIG_WORKSHEET_NAME = "運用アカウント情報"


# ============================
# ✅ 設定読み込みエントリーポイント
# ============================

def load_config():
    """
    スプレッドシートから設定を読み込み、key-value 形式の辞書を返す。
    accounts.json は開発フェーズでも使用しません。
    """
    return load_config_from_sheet()


# ============================
# ✅ 本番・開発共通：スプレッドシートから設定情報を取得
# ============================

def load_config_from_sheet(
    sheet_name=DEFAULT_CONFIG_SHEET_NAME,
    worksheet_name=DEFAULT_CONFIG_WORKSHEET_NAME
):
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_KEY_FILE, GOOGLE_API_SCOPE)
    client = gspread.authorize(creds)

    sheet = client.open(sheet_name).worksheet(worksheet_name)
    rows = sheet.get_all_values()

    # key-value 形式で辞書化して返す
    return {row[0]: row[1] for row in rows if len(row) >= 2}

# ============================
# ✅ デバッグ用コード（単体実行時）
# ============================

if __name__ == "__main__":
    from pprint import pprint

    print("\n📘 投稿設定の確認:")
    config = load_config()
    pprint(config)

    print("\n👤 アカウント情報一覧:")
    accounts = load_account_info()
    pprint(accounts)

    # 例: defaultアカウントのemailを表示
    if "default" in accounts:
        print("\n📧 default アカウントの email:", accounts["default"].get("email"))
    else:
        print("\n❌ default アカウントが見つかりません")

    print("\n✅ 検証：投稿設定に必要なキーがあるか")
    required_keys = ["SHEET_NAME", "WORKSHEET_NAME", "TWITTER_USERNAME"]
    for key in required_keys:
        if key in config:
            print(f"  ✅ {key} = {config[key]}")
        else:
            print(f"  ❌ {key} が見つかりません")

    print("\n✅ 検証：全アカウントに email / SHEET_NAME / WORKSHEET_NAME が含まれるか")
    for acc_id, info in accounts.items():
        missing = [k for k in ["email", "SHEET_NAME", "WORKSHEET_NAME"] if not info.get(k)]
        if missing:
            print(f"  ❌ {acc_id} → 欠損: {', '.join(missing)}")
        else:
            print(f"  ✅ {acc_id} → OK")
