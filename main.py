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
    # Configインスタンスを早期に作成してログレベルを設定
    config_instance = Config()
    
    # logging.basicConfig をここで設定
    log_level_str = config_instance.get_log_level() # "INFO", "DEBUG"など
    numeric_log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logging.basicConfig(level=numeric_log_level,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info(f"Configから取得したログレベル '{log_level_str}' を設定しました。")


    parser = argparse.ArgumentParser(description="Twitter自動投稿システム ワークフロー管理")
    workflow_group = parser.add_argument_group('Workflow Options')
    workflow_group.add_argument("--generate-schedule", action="store_true", help="指定日 (デフォルトは今日) のスケジュールを生成・保存します。")
    workflow_group.add_argument("--process-now", action="store_true", help="保存された指定日 (デフォルトは今日) のスケジュールに基づき、期限の来た投稿を実行します。")
    workflow_group.add_argument("--manual-test", type=str, metavar="ACCOUNT_ID", help="指定したACCOUNT_IDで即時実行のテスト投稿を1件行います。他のワークフローオプションとは併用できません。")

    common_options = parser.add_argument_group('Common Options')
    common_options.add_argument("--date", type=str, help="対象日をYYYY-MM-DD形式で指定。デフォルトは今日。")
    common_options.add_argument("--force-regenerate", action="store_true", help="スケジュール生成時に既存ファイルを無視して強制再生成します。 (generate-schedule時のみ有効)")
    # common_options.add_argument("--config", type=str, default="config/config.yml", help="設定ファイルのパス (デフォルト: config/config.yml)") # 削除
    common_options.add_argument("--debug", action="store_true", help="デバッグログを有効にします (Config設定を上書き)。")
    common_options.add_argument("--info", action="store_true", help="INFOレベルのログを有効にします (Config設定を上書き)。")
    common_options.add_argument("--use-test-schedule", action="store_true", help="テスト用のスケジュールファイルと実行ログファイルを使用します。")

    args = parser.parse_args()

    # コマンドライン引数によるログレベル上書き
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("デバッグログモードが有効になりました (コマンドライン引数により上書き)。")
    elif args.info:
        if logging.getLogger().getEffectiveLevel() > logging.INFO : # 現在のレベルがINFOより詳細でない場合のみINFOに設定
            logging.getLogger().setLevel(logging.INFO)
            logger.info("INFOログモードが有効になりました (コマンドライン引数により上書き)。")
    
    logger.info("システムメイン処理を開始します。") # ログレベル設定後に実行

    if args.manual_test and (args.generate_schedule or args.process_now):
        parser.error("--manual-test オプションは --generate-schedule や --process-now と併用できません。")

    try:
        # config_instance は既に作成済み
        
        schedule_settings = config_instance.get_schedule_config()
        if not schedule_settings:
            # このエラーは Config の DEFAULT_CONFIG があれば通常発生しないはず
            raise ValueError("スケジュール設定 (APP_CONFIG_JSONのauto_post_bot.schedule_settingsまたはデフォルト値) が見つかりません。")

        logs_dir_name = config_instance.get_logs_directory() # "logs" またはカスタム名 (プロジェクトルートからの相対)
        # project_root_path はファイルの先頭で定義済み
        resolved_logs_dir = os.path.join(project_root_path, logs_dir_name)
        
        logger.debug(f"ログディレクトリ (絶対パス): '{resolved_logs_dir}'")
        os.makedirs(resolved_logs_dir, exist_ok=True)


        schedule_file_key = ""
        executed_file_key = ""
        use_test_files = args.use_test_schedule or bool(args.manual_test)

        if use_test_files:
            schedule_file_key = "test_schedule_file"
            executed_file_key = "test_executed_file"
            logger.info(f"テストモード相当のファイルパスを使用します。 (manual_test: {bool(args.manual_test)}, use_test_schedule: {args.use_test_schedule})")
        else:
            schedule_file_key = "schedule_file"
            executed_file_key = "executed_file"
        
        schedule_file_name = schedule_settings.get(schedule_file_key)
        executed_file_name = schedule_settings.get(executed_file_key)

        if not schedule_file_name or not executed_file_name:
            logger.critical(f"使用すべきスケジュールファイルキー '{schedule_file_key}' または実行ログファイルキー '{executed_file_key}' が設定に見つかりません。")
            exit(1)
        
        final_schedule_file_path = os.path.join(resolved_logs_dir, schedule_file_name)
        final_executed_file_path = os.path.join(resolved_logs_dir, executed_file_name)
        logger.debug(f"最終的なスケジュールファイルパス: '{final_schedule_file_path}'")
        logger.debug(f"最終的な実行済みファイルパス: '{final_executed_file_path}'")

        target_d: date
        if args.date:
            try:
                target_d = datetime.strptime(args.date, "%Y-%m-%d").date()
            except ValueError:
                logger.error("日付の形式が不正です。YYYY-MM-DD形式で指定してください。")
                exit(1)
        else:
            target_d = date.today()

        if args.manual_test:
            logger.info(f"--- 手動テストモード開始 (アカウントID: {args.manual_test}) ---")
            account_id_to_test, worksheet_name_to_test = _get_manual_test_account_info(config_instance, args.manual_test)
            if not account_id_to_test or not worksheet_name_to_test:
                logger.error("手動テスト用のアカウント情報が取得できなかったため、処理を中止します。")
                exit(1)
            if not _prepare_manual_test_schedule_file(final_schedule_file_path, account_id_to_test, worksheet_name_to_test):
                logger.error("手動テスト用スケジュールファイルの準備に失敗したため、処理を中止します。")
                exit(1)
            _delete_manual_test_executed_log(final_executed_file_path)
            workflow_manager = WorkflowManager(
                config=config_instance,
                schedule_file_path=final_schedule_file_path
            )
            logger.info(f"手動テストのため、{target_d.isoformat()} のスケジュール投稿処理 (process_scheduled_posts_now) を実行します...")
            workflow_manager.process_scheduled_posts_now(target_date=target_d)
            logger.info(f"--- 手動テストモード完了 (アカウントID: {args.manual_test}) ---")
        else:
            workflow_manager = WorkflowManager(
                config=config_instance,
                schedule_file_path=final_schedule_file_path
            )
            # 現在時刻を取得 (generate_daily_schedule に渡すため)
            now_for_schedule_generation = datetime.now(timezone.utc) if args.generate_schedule else None

            if args.generate_schedule:
                logger.info(f"{target_d.isoformat()} のスケジュールを生成します... 強制: {args.force_regenerate}")
                workflow_manager.generate_daily_schedule(
                    target_date=target_d, 
                    force_regenerate=args.force_regenerate,
                    execution_trigger_time_utc=now_for_schedule_generation
                )
            if args.process_now:
                logger.info(f"{target_d.isoformat()} のスケジュール投稿処理を実行します...")
                workflow_manager.process_scheduled_posts_now(target_date=target_d) 
            if not args.generate_schedule and not args.process_now: # --manual-test でない場合のみ実行
                logger.info(f"{target_d.isoformat()} のスケジュール処理を開始します (日次バッチ)。")
                total_processed, total_successful = workflow_manager.process_scheduled_posts_for_day(date_str=target_d.isoformat())
                logger.info(f"{target_d.isoformat()} の日次バッチ処理完了。処理対象 {total_processed}件、成功 {total_successful}件。")

        logger.info("システムメイン処理を正常に終了しました。")

    except ValueError as ve: 
        logger.critical(f"設定エラーまたはコマンドライン引数エラー: {ve}", exc_info=True)
        print(f"致命的なエラー: {ve}")
    except ImportError as ie: 
        logger.critical(f"モジュールのインポートエラー: {ie}. 構造やPYTHONPATHを確認してください。", exc_info=True)
        print(f"致命的なエラー: {ie}")
    except Exception as e:
        logger.critical(f"メイン処理中に予期せぬ最上位エラー: {e}", exc_info=True)
        print(f"致命的なエラーが発生しました: {e}")

if __name__ == '__main__':
    main() 