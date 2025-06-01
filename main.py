#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os
from datetime import datetime, date
import sys # sys をインポート

# engine_core パッケージのモジュールをインポートするために、
# プロジェクトルートを sys.path に追加
project_root_path = os.path.dirname(os.path.abspath(__file__))
# main.py が InboundEngine ディレクトリ直下にあるので、project_root_path が InboundEngine を指す
# engine_core はその下にあるので、project_root_path を sys.path に追加すれば良い
sys.path.insert(0, project_root_path)


try:
    from engine_core.config import Config
    from engine_core.workflow_manager import WorkflowManager
except ImportError as e: # 具体的なエラーも表示
    print(f"ERROR: engine_coreモジュールが見つかりません。PYTHONPATHを確認するか、プロジェクトルートから実行してください。詳細: {e}")
    print(f"現在のsys.path: {sys.path}")
    print("例: `python main.py` (プロジェクトルートにいる場合)")
    exit(1)


# ロガー設定 (workflow_manager.py から移動)
# デフォルトのログレベルを WARNING に変更
logging.basicConfig(level=logging.WARNING,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # main.py 用のロガー

# ライブラリのロガーレベルを調整
logging.getLogger("urllib3").setLevel(logging.INFO)
logging.getLogger("tweepy").setLevel(logging.INFO)
logging.getLogger("requests").setLevel(logging.INFO)
logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
logging.getLogger("oauthlib").setLevel(logging.WARNING)

def main():
    logger.info("システムメイン処理を開始します。")

    parser = argparse.ArgumentParser(description="Twitter自動投稿システム ワークフロー管理")
    parser.add_argument("--generate-schedule", action="store_true", help="指定日 (デフォルトは今日) のスケジュールを生成・保存します。")
    parser.add_argument("--process-now", action="store_true", help="保存された指定日 (デフォルトは今日) のスケジュールに基づき、期限の来た投稿を実行します。")
    parser.add_argument("--date", type=str, help="対象日をYYYY-MM-DD形式で指定。デフォルトは今日。")
    parser.add_argument("--force-regenerate", action="store_true", help="スケジュール生成時に既存ファイルを無視して強制再生成します。")
    parser.add_argument("--config", type=str, default="config/config.yml", help="設定ファイルのパス (デフォルト: config/config.yml)")
    parser.add_argument("--debug", action="store_true", help="デバッグログを有効にします。")
    parser.add_argument("--info", action="store_true", help="INFOレベルのログを有効にします。")
    parser.add_argument("--use-test-schedule", action="store_true", help="テスト用のスケジュールファイルと実行ログファイルを使用します。config.ymlに test_schedule_file と test_executed_file が定義されている必要があります。")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("デバッグログモードが有効になりました。")
    elif args.info:
        logging.getLogger().setLevel(logging.INFO)
        logger.info("INFOログモードが有効になりました。")


    try:
        # config.yml のパスを解決
        config_file_path_main = args.config
        if not os.path.isabs(config_file_path_main):
            project_root = os.path.dirname(os.path.abspath(__file__))
            config_file_path_main = os.path.join(project_root, args.config)
        logger.debug(f"使用する設定ファイル (絶対パス): {config_file_path_main}")
        
        if not os.path.exists(config_file_path_main):
            logger.critical(f"設定ファイルが見つかりません: {config_file_path_main}")
            print(f"エラー: 設定ファイル {config_file_path_main} が見つかりません。")
            print("`--config` 引数で正しいパスを指定するか、プロジェクトルートに `config/config.yml` を配置してください。")
            exit(1)

        config_instance = Config(config_path=config_file_path_main)
        
        # WorkflowManager に渡すファイルパスを決定
        schedule_settings = config_instance.get_schedule_config()
        if not schedule_settings:
            raise ValueError("config.ymlに auto_post_bot.schedule_settings が見つかりません。")

        logs_dir_from_config = config_instance.get_logs_directory() # Configから取得
        logger.debug(f"configから読み込んだ common.logs_directory: '{logs_dir_from_config}'")
        if not logs_dir_from_config:
             logger.warning(f"config.yml の common.logs_directory が未設定のため、デフォルトの 'logs' を使用します。")
             logs_dir_from_config = "logs" # デフォルト値
        
        if not os.path.isabs(logs_dir_from_config):
             config_dir = os.path.dirname(config_file_path_main)
             resolved_logs_dir = os.path.join(config_dir, '..', logs_dir_from_config)
             logger.debug(f"相対パスのlogs_directoryを解決: config_dir='{config_dir}', resolved_logs_dir='{resolved_logs_dir}'")
        else:
            resolved_logs_dir = logs_dir_from_config
            logger.debug(f"絶対パスのlogs_directoryを使用: '{resolved_logs_dir}'")

        if args.use_test_schedule:
            schedule_file = schedule_settings.get("test_schedule_file")
            executed_file = schedule_settings.get("test_executed_file")
            if not schedule_file or not executed_file:
                logger.critical("テスト用スケジュールファイルまたは実行済みファイルがconfig.ymlのschedule_settingsに定義されていません。")
                exit(1)
            logger.info(f"テストモード: schedule_fileキー='{schedule_file}', executed_fileキー='{executed_file}' を使用します。")
        else:
            schedule_file = schedule_settings.get("schedule_file")
            executed_file = schedule_settings.get("executed_file")
            if not schedule_file or not executed_file:
                logger.critical("通常用のスケジュールファイルまたは実行済みファイルがconfig.ymlのschedule_settingsに定義されていません。")
                exit(1)
            logger.debug(f"通常モード: schedule_fileキー='{schedule_file}', executed_fileキー='{executed_file}' を使用します。")

        # ファイル名を logs_dir と結合してフルパスにする
        final_schedule_file_path = os.path.join(resolved_logs_dir, schedule_file)
        final_executed_file_path = os.path.join(resolved_logs_dir, executed_file)
        logger.debug(f"最終的なスケジュールファイルパス: '{final_schedule_file_path}'")
        logger.debug(f"最終的な実行済みファイルパス: '{final_executed_file_path}'")

        workflow_manager = WorkflowManager(
            config=config_instance,
            schedule_file_path=final_schedule_file_path,
            executed_file_path=final_executed_file_path
        )

        target_d: date
        if args.date:
            try:
                target_d = datetime.strptime(args.date, "%Y-%m-%d").date()
            except ValueError:
                logger.error("日付の形式が不正です。YYYY-MM-DD形式で指定してください。")
                print("エラー: 日付の形式が不正です。YYYY-MM-DD形式で指定してください。")
                exit(1)
        else:
            target_d = date.today() # 実行環境のローカルタイムゾーンでの「今日」

        if args.generate_schedule:
            logger.info(f"{target_d.isoformat()} のスケジュールを生成します... 強制: {args.force_regenerate}")
            workflow_manager.generate_daily_schedule(target_date=target_d, force_regenerate=args.force_regenerate)
        
        if args.process_now:
            logger.info(f"{target_d.isoformat()} のスケジュール投稿処理を実行します...")
            # WorkflowManager 内では timezone.utc を使用しているので、日付のみを渡す
            workflow_manager.process_scheduled_posts_now(target_date=target_d) 
        
        if not args.generate_schedule and not args.process_now:
            print("実行するアクションが指定されていません。--generate-schedule または --process-now を使用してください。")
            parser.print_help()
            exit(1) # 何も実行しない場合はエラーコードで終了

        logger.info("システムメイン処理を正常に終了しました。")

    except ValueError as ve: # Configの初期化失敗なども含む
        logger.critical(f"設定エラーまたはコマンドライン引数エラー: {ve}", exc_info=True)
        print(f"致命的なエラー: {ve}")
    except ImportError as ie: # これは初期のインポートチェックで捕捉されるはずだが念のため
        logger.critical(f"モジュールのインポートエラー: {ie}. 構造やPYTHONPATHを確認してください。", exc_info=True)
        print(f"致命的なエラー: {ie}")
    except Exception as e:
        logger.critical(f"メイン処理中に予期せぬ最上位エラー: {e}", exc_info=True)
        print(f"致命的なエラーが発生しました: {e}")

if __name__ == '__main__':
    main() 