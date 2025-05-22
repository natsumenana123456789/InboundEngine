import unittest
import os
import shutil
from unittest.mock import patch, MagicMock # webdriver.Chrome をモックするために追加

# プロジェクトルートを基準にパスを設定
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

import sys
sys.path.insert(0, PROJECT_ROOT)

from utils.webdriver_utils import get_driver
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver

class TestWebDriverUtils(unittest.TestCase):

    TEST_CACHE_DIR = os.path.join(PROJECT_ROOT, 'tests', '.cache') # テスト用のキャッシュディレクトリ

    def setUp(self):
        """各テストの前にキャッシュディレクトリをクリーンアップ"""
        # webdriver_utils が PROJECT_ROOT/.cache/chrome_profiles を使うため、
        # tests/.cache/chrome_profiles のようなテスト専用の場所にしたいが、
        # get_driver内の project_root の解決方法に依存する。
        # webdriver_utils.py の project_root は os.path.dirname(__file__), '..' で決定されるため、
        # どのスクリプトから呼び出すかで変わる。
        # ここでは、テスト実行時に utils/.cache ができてしまうことを許容し、
        # クリーンアップは utils/.cache に対して行うか、
        # get_driver にキャッシュルートを渡せるように変更することを検討。
        # 現状の実装では、 PROJECT_ROOT/.cache が使われる。
        self.default_profile_base = os.path.join(PROJECT_ROOT, ".cache", "chrome_profiles")
        if os.path.exists(self.default_profile_base):
            # 中身だけ消すか、ディレクトリごと消すかは注意が必要。
            # ここではテストで使われたプロファイルのみを消すのが理想だが、特定が難しいのでベースごと。
            # ただし、他のテストや実際の運用プロファイルを消さないように注意。
            # 安全のため、テスト専用のベースパスを使うのが良い。
            # 今回は webdriver_utils の実装を変えずに、テスト後に default_profile ができたら消す方針。
            pass # tearDown で対応

    def tearDown(self):
        """各テストの後に作成された可能性のあるプロファイルディレクトリをクリーンアップ"""
        # デフォルトのプロファイルパスを対象にクリーンアップ
        # ただし、これは get_driver の実装に強く依存するため、将来的な変更に注意
        test_profile_name1 = "test_profile_default"
        test_profile_name2 = "test_profile_custom_args"
        path1 = os.path.join(self.default_profile_base, test_profile_name1)
        path2 = os.path.join(self.default_profile_base, test_profile_name2)
        if os.path.exists(path1):
            shutil.rmtree(path1)
        if os.path.exists(path2):
            shutil.rmtree(path2)
        # もし default_profile_base が空ならそれも消す (他のものが入ってない限り)
        # try:
        #     if os.path.exists(self.default_profile_base) and not os.listdir(self.default_profile_base):
        #         os.rmdir(self.default_profile_base)
        #     if os.path.exists(os.path.dirname(self.default_profile_base)) and not os.listdir(os.path.dirname(self.default_profile_base)):
        #          os.rmdir(os.path.dirname(self.default_profile_base))
        # except OSError:
        #     pass # 消せなくてもエラーにしない

    @patch('utils.webdriver_utils.webdriver.Chrome') # webdriver.Chrome をモック
    def test_01_get_driver_returns_webdriver_instance_mocked(self, mock_chrome_driver):
        """get_driverがモックされたWebDriverインスタンスを返すかのテスト"""
        mock_driver_instance = MagicMock(spec=ChromeWebDriver)
        mock_chrome_driver.return_value = mock_driver_instance
        
        driver = get_driver(profile_user_name="mock_test_profile")
        self.assertIs(driver, mock_driver_instance)
        mock_chrome_driver.assert_called_once() # Chromeが一回呼ばれたか
        # オプションの検証 (引数optionsの内容を確認)
        args, kwargs = mock_chrome_driver.call_args
        called_options = kwargs.get('options')
        self.assertIsNotNone(called_options)
        self.assertIn("--disable-blink-features=AutomationControlled", called_options.arguments)
        self.assertTrue(any("user-agent=" in arg for arg in called_options.arguments))
        self.assertTrue(any(f"user-data-dir=" in arg and "mock_test_profile" in arg for arg in called_options.arguments))

    # 実際のWebDriverの起動を伴うテスト (環境に依存)
    # @unittest.skipIf(os.environ.get("CI") == "true", "WebDriverの起動テストはCI環境ではスキップ")
    def test_02_get_driver_with_default_profile(self):
        """get_driverがデフォルトプロファイルでWebDriverインスタンスを返すか (実際の起動あり)"""
        profile_name = "test_profile_default"
        driver = None
        try:
            driver = get_driver(profile_user_name=profile_name)
            self.assertIsInstance(driver, ChromeWebDriver)
            # プロファイルディレクトリが作成されていることを確認 (間接的)
            # webdriver_utils.py の print 文で確認するか、実際にパスが存在するか
            expected_profile_dir = os.path.join(self.default_profile_base, profile_name)
            self.assertTrue(os.path.exists(expected_profile_dir))
        except Exception as e:
            self.fail(f"get_driver (デフォルト) 実行中にエラー: {e}. ChromeDriverがインストールされ、パスが通っているか確認してください。")
        finally:
            if driver:
                driver.quit()

    # @unittest.skipIf(os.environ.get("CI") == "true", "WebDriverの起動テストはCI環境ではスキップ")
    def test_03_get_driver_with_custom_user_agent_and_profile(self):
        """get_driverがカスタム引数でWebDriverインスタンスを返すか (実際の起動あり)"""
        custom_agents = ["TestAgent/1.0 (Test)"]
        profile_name = "test_profile_custom_args"
        driver = None
        try:
            driver = get_driver(user_agent_list=custom_agents, profile_user_name=profile_name)
            self.assertIsInstance(driver, ChromeWebDriver)
            expected_profile_dir = os.path.join(self.default_profile_base, profile_name)
            self.assertTrue(os.path.exists(expected_profile_dir))
            # User-Agentが実際に設定されたかは、driver.execute_script("return navigator.userAgent;") で確認できるが、
            # ここではget_driverがエラーなく実行されることを主眼とする
        except Exception as e:
            self.fail(f"get_driver (カスタム引数) 実行中にエラー: {e}. ChromeDriverがインストールされ、パスが通っているか確認してください。")
        finally:
            if driver:
                driver.quit()

if __name__ == '__main__':
    # 実行時に "[WebDriverUtils]" のprint出力がされます
    unittest.main() 