import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
import argparse # argparse をインポート
from engine_core.config import Config # Configクラスをインポート

# --- 設定ここから ---
TEST_SCHEDULE_FILE_PATH = "logs/test_schedule.txt"
EXECUTED_SCHEDULE_FILE_PATH = "logs/test_executed_schedule.txt"
MINUTES_TO_ADD_FOR_SCHEDULE = 1 # 1分後に変更
CONFIG_FILE_PATH = "config/config.yml" # config.ymlのパス
DEFAULT_WORKSHEET_NAME_IF_NOT_SPECIFIED = "Sheet1" # アカウントに紐づくWS名が取得できない場合のデフォルト
# --- 設定ここまで ---

def get_account_info_from_config(target_account_id: str = None):
    """config.yml からアカウントIDとそれに対応するワークシート名を取得する。
    target_account_id が指定されていればそのアカウントを、なければ最初のアクティブなアカウントを探す。
    """
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"ERROR: 設定ファイルが見つかりません: {CONFIG_FILE_PATH}")
        return None, None
    
    try:
        config = Config(config_path=CONFIG_FILE_PATH)
        # get_active_twitter_accounts() を使うと、最初から有効なものだけが対象になるが、
        # 個別に指定されたものが無効だった場合に「見つからない」ではなく「無効」と伝えたいので、
        # まず全アカウントを取得し、enabledフラグをチェックする方針とする。
        all_twitter_accounts = config.get_twitter_accounts() # enabledフラグが付与された全アカウント

        if not all_twitter_accounts or not isinstance(all_twitter_accounts, list):
            print(f"WARN: {CONFIG_FILE_PATH} に `twitter_accounts` のリストが見つからないか、形式が正しくありません。")
            return None, None

        if target_account_id:
            # 指定されたアカウントIDを探す
            account_found = False
            for acc in all_twitter_accounts:
                if isinstance(acc, dict) and acc.get("account_id") == target_account_id:
                    account_found = True
                    if not acc.get("enabled", True): # enabledがない場合はTrue扱いだが、Config側で付与済みのはず
                        print(f"ERROR: 指定されたアカウントID '{target_account_id}' は config.yml で無効化 (enabled: false) されています。")
                        return None, None
                    
                    worksheet_name = acc.get("google_sheets_source", {}).get("worksheet_name")
                    if not worksheet_name:
                         print(f"WARN: アカウント '{target_account_id}' にワークシート名が設定されていません。デフォルト値 '{DEFAULT_WORKSHEET_NAME_IF_NOT_SPECIFIED}' を使用します。")
                         worksheet_name = DEFAULT_WORKSHEET_NAME_IF_NOT_SPECIFIED
                    print(f"INFO: 指定されたアカウント情報を使用: Account='{target_account_id}', Worksheet='{worksheet_name}'")
                    return target_account_id, worksheet_name
            if not account_found:
                print(f"ERROR: 指定されたアカウントID '{target_account_id}' が config.yml に見つかりません。")
            return None, None # 見つからないか、上記で既にreturn済み
        else:
            # 指定がない場合は最初のアクティブなアカウント
            active_accounts = [acc for acc in all_twitter_accounts if acc.get("enabled", True)]
            if active_accounts:
                first_active_account = active_accounts[0]
                # first_active_account は辞書であることは active_accounts の生成条件から期待できる
                account_id = first_active_account.get("account_id")
                worksheet_name = first_active_account.get("google_sheets_source", {}).get("worksheet_name")
                
                if not account_id: # 通常は起こらないはず
                    print(f"ERROR: config.yml の最初のアクティブなTwitterアカウントに account_id がありません。")
                    return None, None
                if not worksheet_name:
                    print(f"WARN: アカウント '{account_id}' にワークシート名が設定されていません。デフォルト値 '{DEFAULT_WORKSHEET_NAME_IF_NOT_SPECIFIED}' を使用します。")
                    worksheet_name = DEFAULT_WORKSHEET_NAME_IF_NOT_SPECIFIED
                
                print(f"INFO: config.ymlの最初のアクティブなアカウント情報を使用: Account='{account_id}', Worksheet='{worksheet_name}'")
                return account_id, worksheet_name
            
            print(f"ERROR: config.yml に有効な (enabled: true) Twitterアカウント設定が見つかりません。")
            return None, None

    except Exception as e:
        print(f"ERROR: config.yml の読み込みまたは解析中にエラーが発生しました: {e}")
        return None, None

def update_test_schedule_file(account_id_to_test: str, worksheet_name_to_test: str):
    """テスト用のスケジュールファイルを現在時刻ベースで更新する"""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    scheduled_time_local = now + timedelta(minutes=MINUTES_TO_ADD_FOR_SCHEDULE)
    scheduled_time_utc_str = scheduled_time_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    schedule_content = {
        today_str: [
            {
                "account_id": account_id_to_test,
                "scheduled_time": scheduled_time_utc_str,
                "worksheet_name": worksheet_name_to_test
            }
        ]
    }
    try:
        os.makedirs(os.path.dirname(TEST_SCHEDULE_FILE_PATH), exist_ok=True)
        with open(TEST_SCHEDULE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(schedule_content, f, indent=4, ensure_ascii=False)
        print(f"INFO: '{TEST_SCHEDULE_FILE_PATH}' を更新しました。")
        print(f"  - 日付キー: {today_str}")
        print(f"  - スケジュール時刻 (UTC): {scheduled_time_utc_str} (アカウント: {account_id_to_test}, WS: {worksheet_name_to_test})")
        return True
    except IOError as e:
        print(f"ERROR: スケジュールファイル '{TEST_SCHEDULE_FILE_PATH}' の書き込みに失敗しました: {e}")
        return False

def delete_executed_schedule_file():
    """実行済みスケジュールファイルを削除する"""
    if os.path.exists(EXECUTED_SCHEDULE_FILE_PATH):
        try:
            os.remove(EXECUTED_SCHEDULE_FILE_PATH)
            print(f"INFO: '{EXECUTED_SCHEDULE_FILE_PATH}' を削除しました。")
        except OSError as e:
            print(f"WARN: '{EXECUTED_SCHEDULE_FILE_PATH}' の削除に失敗しました: {e}")
    else:
        print(f"INFO: '{EXECUTED_SCHEDULE_FILE_PATH}' は存在しません。削除はスキップされました。")

def run_main_script(target_date_str: str):
    """main.py を実行する"""
    command = [
        "python", "main.py", 
        "--process-now",  # コメントアウトを解除
        "--use-test-schedule", 
        "--info", 
        "--date", target_date_str
    ]
    print(f"INFO: 次のコマンドを実行します: {' '.join(command)}")
    try:
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        print("INFO: main.py の標準出力:")
        print(process.stdout)
        if process.stderr:
            print("INFO: main.py の標準エラー出力:")
            print(process.stderr)
        print("INFO: main.py の実行が完了しました。")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: main.py の実行に失敗しました (終了コード: {e.returncode})。")
        print("標準出力:")
        print(e.stdout)
        print("標準エラー出力:")
        print(e.stderr)
    except FileNotFoundError:
        print("ERROR: python または main.py が見つかりません。パスを確認してください。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="手動テスト実行スクリプト")
    parser.add_argument(
        "--account_id", 
        type=str, 
        help="テストに使用するTwitterアカウントのID (config.ymlに設定されているもの)"
    )
    args = parser.parse_args()

    print("--- 手動テスト準備開始 ---")

    # logsディレクトリがなければ作成
    if not os.path.exists("logs"):
        try:
            os.makedirs("logs")
            print("INFO: 'logs' ディレクトリを作成しました。")
        except OSError as e:
            print(f"ERROR: 'logs' ディレクトリの作成に失敗しました: {e}")
            print("--- 手動テスト準備完了 (エラーあり) ---")
            exit(1)

    # アカウント情報取得
    account_to_use, worksheet_to_use = get_account_info_from_config(args.account_id)

    if not account_to_use or not worksheet_to_use:
        print("ERROR: テスト用のアカウント情報がconfig.ymlから取得できませんでした。処理を中止します。")
        print("--- 手動テスト準備完了 (エラーあり) ---")
        exit(1)
    
    # スケジュールファイル更新
    if not update_test_schedule_file(account_to_use, worksheet_to_use):
        print("ERROR: スケジュールファイルの更新に失敗したため、後続処理を中止します。")
        print("--- 手動テスト準備完了 (エラーあり) ---")
        exit(1)

    # 実行済みファイル削除
    delete_executed_schedule_file()

    # main.py 実行
    today_for_main = datetime.now().strftime("%Y-%m-%d") # main.pyの--dateは実行日の日付
    run_main_script(today_for_main)

    print("--- 手動テスト準備完了 ---") 