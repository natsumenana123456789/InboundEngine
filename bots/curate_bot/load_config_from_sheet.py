import gspread
from google.oauth2.service_account import Credentials

def load_config_from_sheet(
    spreadsheet_id,
    sheet_name,
    credentials_path,
    account_key="default"
):
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(spreadsheet_id)
    worksheet = sh.worksheet(sheet_name)
    rows = worksheet.get_all_values()
    headers = rows[0]
    config_row = None
    for row in rows[1:]:
        if len(row) > 1 and row[1] == account_key:
            config_row = row
            break
    if not config_row:
        raise ValueError(f"{account_key} の設定が見つかりません")
    config = {}
    for i, key in enumerate(headers):
        if key and i < len(config_row) and config_row[i]:
            config[key] = config_row[i]
    return config 