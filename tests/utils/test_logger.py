import unittest
import os
import logging
import shutil # ログディレクトリ削除用

# プロジェクトルートを基準にパスを設定
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

import sys
sys.path.insert(0, PROJECT_ROOT)

from utils.logger import setup_logger, get_logger, simple_log

class TestLogger(unittest.TestCase):

    TEST_LOG_DIR_BASE = os.path.join(PROJECT_ROOT, 'tests', 'temp_logs')

    def setUp(self):
        """各テストの前にログディレクトリをクリーンアップ"""
        if os.path.exists(self.TEST_LOG_DIR_BASE):
            shutil.rmtree(self.TEST_LOG_DIR_BASE)
        os.makedirs(self.TEST_LOG_DIR_BASE, exist_ok=True)

    def tearDown(self):
        """各テストの後にログディレクトリをクリーンアップ"""
        if os.path.exists(self.TEST_LOG_DIR_BASE):
            shutil.rmtree(self.TEST_LOG_DIR_BASE)

    def test_01_setup_logger_basic(self):
        """setup_logger の基本的な動作テスト"""
        logger_name = "TestSetupBasic"
        log_file = "basic.log"
        # utils.logger の project_root が 'utils' の一つ上なので、
        # ここで渡す log_dir_name は 'tests/temp_logs' のような形になる
        log_dir_rel_to_project = os.path.join('tests', 'temp_logs', 'basic_logs')
        
        logger = setup_logger(log_dir_name=log_dir_rel_to_project, log_file_name=log_file, logger_name=logger_name, level=logging.DEBUG)
        
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, logger_name)
        self.assertEqual(logger.level, logging.DEBUG)
        
        # ログファイルが作成されたか確認
        expected_log_path = os.path.join(PROJECT_ROOT, log_dir_rel_to_project, log_file)
        self.assertTrue(os.path.exists(expected_log_path), f"ログファイル {expected_log_path} が作成されていません。")
        
        # ハンドラの数（ファイルとコンソールで2つのはず）
        self.assertEqual(len(logger.handlers), 2)

        # 簡単なログ出力テスト（ファイルへの書き込みはここでは直接検証しない）
        try:
            logger.info("This is an info message for basic setup test.")
            logger.debug("This is a debug message for basic setup test.")
        except Exception as e:
            self.fail(f"ロギング中にエラーが発生しました: {e}")

    def test_02_get_logger_new_and_existing(self):
        """get_logger で新規作成と既存取得のテスト"""
        logger_name1 = "TestGetLogger1"
        # get_logger はデフォルトでプロジェクトルート直下の 'logs' を使う
        # ここでは setup_logger を使ってテスト用ディレクトリに作成
        log_dir_rel_to_project1 = os.path.join('tests', 'temp_logs', 'get_logger1')
        logger1_setup = setup_logger(log_dir_name=log_dir_rel_to_project1, log_file_name="get1.log", logger_name=logger_name1)
        
        logger1_get = get_logger(logger_name1)
        self.assertIs(logger1_setup, logger1_get, "get_loggerが既存のロガーインスタンスを返しませんでした。")

        logger_name2 = "TestGetLoggerUnseen"
        # get_loggerで未設定のものを取得すると、デフォルト設定で作成される
        # デフォルトでは logs/app.log になるので、テスト後のクリーンアップが難しい
        # そのため、get_loggerが内部で呼び出すsetup_loggerの挙動を変えるか、
        # ここでは get_logger の「設定済みならそれを返す」部分のみを主眼に置く。
        # 未設定の場合のデフォルト作成先は、実際の運用で確認する。
        # logger2 = get_logger(logger_name2)
        # self.assertEqual(logger2.name, logger_name2)
        # self.assertTrue(logger2.hasHandlers(), "get_loggerが新規ロガーにハンドラを設定しませんでした。")
        # ログファイルパスの確認は、デフォルトパスに依存するため、ここでは省略

    def test_03_logger_level(self):
        """ログレベルが正しく設定されているかのテスト"""
        logger_name = "TestLogLevel"
        log_dir_rel = os.path.join('tests', 'temp_logs', 'level_test')
        logger_info = setup_logger(log_dir_name=log_dir_rel, log_file_name="info.log", logger_name=logger_name + "Info", level=logging.INFO)
        logger_debug = setup_logger(log_dir_name=log_dir_rel, log_file_name="debug.log", logger_name=logger_name + "Debug", level=logging.DEBUG)

        self.assertEqual(logger_info.level, logging.INFO)
        self.assertEqual(logger_debug.level, logging.DEBUG)
        
        # isEnabledFor の確認
        self.assertTrue(logger_info.isEnabledFor(logging.INFO))
        self.assertTrue(logger_info.isEnabledFor(logging.WARNING))
        self.assertFalse(logger_info.isEnabledFor(logging.DEBUG))

        self.assertTrue(logger_debug.isEnabledFor(logging.DEBUG))
        self.assertTrue(logger_debug.isEnabledFor(logging.INFO))

    def test_04_simple_log(self):
        """simple_log 関数の基本的な動作テスト (標準出力へのprint)"""
        # simple_log は print するだけなので、厳密なテストは難しい
        # ここではエラーなく実行されるかを確認
        try:
            simple_log("This is a test message from simple_log.")
        except Exception as e:
            self.fail(f"simple_logの実行中にエラー: {e}")

    def test_05_log_file_creation_in_specified_subdir(self):
        """指定したサブディレクトリにログファイルが作成されるかのテスト"""
        logger_name = "SubdirTestLogger"
        # utils.logger の setup_logger は project_root からの相対パスを期待する
        log_dir_from_project_root = os.path.join('tests', 'temp_logs', 'subdir_test', 'deep_logs')
        log_file = "subdir.log"
        
        _ = setup_logger(log_dir_name=log_dir_from_project_root, log_file_name=log_file, logger_name=logger_name)
        expected_log_path = os.path.join(PROJECT_ROOT, log_dir_from_project_root, log_file)
        self.assertTrue(os.path.exists(expected_log_path), f"指定したサブディレクトリにログファイル {expected_log_path} が作成されませんでした。")

if __name__ == '__main__':
    unittest.main() 