#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os
from datetime import datetime, date, timedelta, timezone
import sys
import json

# engine_core パッケージのモジュールをインポートするために、
# プロジェクトルートを sys.path に追加
project_root_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root_path)


try:
    from engine_core.config import Config
    from engine_core.workflow_manager import WorkflowManager
except ImportError as e: 
    print(f"ERROR: engine_coreモジュールが見つかりません。PYTHONPATHを確認するか、プロジェクトルートから実行してください。詳細: {e}")
    print(f"現在のsys.path: {sys.path}")
    print("例: `python main.py` (プロジェクトルートにいる場合)")
    exit(1)

# ロガーのグローバル設定は main() の中で Config からレベルを取得した後に行う
logger = logging.getLogger(__name__) 

# ライブラリのロガーレベル調整 (main() の中で適用しても良いが、ここでは早期に設定)
logging.getLogger("urllib3").setLevel(logging.INFO)
logging.getLogger("tweepy").setLevel(logging.INFO)
logging.getLogger("requests").setLevel(logging.INFO)
logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
logging.getLogger("oauthlib").setLevel(logging.WARNING)

# --- 手動テスト用ヘルパー関数 (変更なし) ---
DEFAULT_WORKSHEET_NAME_IF_NOT_SPECIFIED = "Sheet1"
MINUTES_TO_ADD_FOR_SCHEDULE = 1

def _get_manual_test_account_info(config_instance: Config, target_account_id: str):
    all_twitter_accounts = config_instance.get_twitter_accounts()
    if not all_twitter_accounts:
        logger.error("APP_CONFIG_JSON の twitter_accounts が見つからないか空です。") # メッセージ変更
        return None, None
    account_found = False
    for acc in all_twitter_accounts:
        if isinstance(acc, dict) and acc.get("account_id") == target_account_id:
            account_found = True
            if not acc.get("enabled", True):
                logger.error(f"指定されたアカウントID '{target_account_id}' は設定で無効化されています。")
                return None, None
            worksheet_name = acc.get("google_sheets_source", {}).get("worksheet_name")
            if not worksheet_name:
                 logger.warning(f"アカウント '{target_account_id}' にワークシート名が設定されていません。デフォルト値 '{DEFAULT_WORKSHEET_NAME_IF_NOT_SPECIFIED}' を使用します。")
                 worksheet_name = DEFAULT_WORKSHEET_NAME_IF_NOT_SPECIFIED
            logger.info(f"手動テスト対象アカウント: Account='{target_account_id}', Worksheet='{worksheet_name}'")
            return target_account_id, worksheet_name
    if not account_found:
        logger.error(f"指定されたアカウントID '{target_account_id}' が設定に見つかりません。")
    return None, None

def _prepare_manual_test_schedule_file(schedule_file_path: str, account_id: str, worksheet_name: str) -> bool:
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    scheduled_time_local = now + timedelta(minutes=MINUTES_TO_ADD_FOR_SCHEDULE)
    scheduled_time_utc_str = scheduled_time_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schedule_content = {
        today_str: [
            {"account_id": account_id, "scheduled_time": scheduled_time_utc_str, "worksheet_name": worksheet_name}
        ]
    }
    try:
        os.makedirs(os.path.dirname(schedule_file_path), exist_ok=True)
        with open(schedule_file_path, 'w', encoding='utf-8') as f:
            json.dump(schedule_content, f, indent=4, ensure_ascii=False)
        logger.info(f"手動テスト用スケジュールファイル '{schedule_file_path}' を更新しました。")
        logger.info(f"  - 日付キー: {today_str}")
        logger.info(f"  - スケジュール時刻 (UTC): {scheduled_time_utc_str} (アカウント: {account_id}, WS: {worksheet_name})")
        return True
    except IOError as e:
        logger.error(f"手動テスト用スケジュールファイル '{schedule_file_path}' の書き込みに失敗しました: {e}")
        return False

def _delete_manual_test_executed_log(executed_log_path: str):
    if os.path.exists(executed_log_path):
        try:
            os.remove(executed_log_path)
            logger.info(f"手動テスト用実行済みログファイル '{executed_log_path}' を削除しました。")
        except OSError as e:
            logger.warning(f"手動テスト用実行済みログファイル '{executed_log_path}' の削除に失敗しました: {e}")
    else:
        logger.info(f"手動テスト用実行済みログファイル '{executed_log_path}' は存在しません。削除はスキップされました。")

# --- ここまでヘルパー関数 ---

def main():
    # --- 引数パーサーの設定 ---
    parser = argparse.ArgumentParser(description="Twitter自動投稿ボット")
    
    # デフォルトの設定ファイルパス
    default_config_path = "config/app_config.dev.json"
    
    parser.add_argument(
        "--config",
        type=str,
        default=default_config_path,
        help=f"使用する設定ファイルのパス (デフォルト: {default_config_path})"
    )
    
    parser.add_argument(
        "--process",
        action="store_true",
        help="投稿時間になったアカウントの投稿処理を（司令塔として）起動します。"
    )
    parser.add_argument(
        "--manual-test",
        type=str,
        metavar="ACCOUNT_ID",
        help="指定したアカウントIDでテスト投稿を1件実行します（最終投稿日時は更新されません）。"
    )
    parser.add_argument(
        "--worker",
        type=str,
        metavar="ACCOUNT_ID",
        help="（内部用）指定したアカウントの投稿処理をワーカーとして実行します。"
    )
    parser.add_argument("--debug", action="store_true", help="デバッグログを有効にします (Config設定を上書き)。")

    args = parser.parse_args()

    # --- ロギング設定 ---
    try:
        # 指定された設定ファイルを使用
        config = Config(config_path=args.config)
        log_level_str = config.get_log_level()
        numeric_log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        logging.basicConfig(level=numeric_log_level,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger.info(f"Configから取得したログレベル '{log_level_str}' を設定しました。")
    except FileNotFoundError:
        print(f"エラー: 指定された設定ファイルが見つかりません: {args.config}")
        sys.exit(1)
    except Exception as e:
        print(f"設定ファイルの読み込み中にエラーが発生しました: {e}")
        sys.exit(1)
    
    logger.info("システムメイン処理を開始します。")

    if args.process and args.manual_test:
        parser.error("--process と --manual-test は同時に指定できません。")

    if not args.process and not args.manual_test and not args.worker:
        logger.warning("実行モードが指定されていません。--process, --manual-test, --worker のいずれかを指定してください。")
        parser.print_help()
        exit(0)

    try:
        # (重要) このファイルが engine_core の外にあるため、
        # engine_core をパッケージとして正しく認識させるために
        # プロジェクトルートをPythonのモジュール検索パスに追加する
        project_root = get_project_root()
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from engine_core.config import AppConfig
        from engine_core.workflow_manager import WorkflowManager

        config = AppConfig(config_path=args.config)
        manager = WorkflowManager(config=config)

        if args.process:
            logger.info("モード: --process (司令塔)")
            manager.launch_pending_posts()
        elif args.worker:
            logger.info(f"モード: --worker (アカウントID: {args.worker})")
            manager.execute_worker_post(args.worker)
        elif args.manual_test:
            logger.info(f"モード: --manual-test (アカウントID: {args.manual_test})")
            manager.run_manual_test_post(args.manual_test)

        logger.info("システムメイン処理を正常に終了しました。")

    except (ModuleNotFoundError, ImportError) as e:
        logger.error(f"engine_coreモジュールが見つかりません。PYTHONPATHを確認するか、プロジェクトルートから実行してください。詳細: {e}")
        logger.error(f"現在のsys.path: {sys.path}")
        print("\nERROR: engine_coreモジュールが見つかりません。PYTHONPATHを確認するか、プロジェクトルートから実行してください。", file=sys.stderr)
        print(f"詳細: {e}", file=sys.stderr)
        print(f"現在のsys.path: {sys.path}", file=sys.stderr)
        print("例: `python main.py` (プロジェクトルートにいる場合)", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.critical(f"予期せぬクリティカルなエラーが発生しました: {e}", exc_info=True)
        print(f"予期せぬクリティカルなエラーが発生しました: {e}", file=sys.stderr)

if __name__ == '__main__':
    main() 