import os
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
# from utils.logger import get_logger # 循環参照を避けるため、ここでは直接呼び出さない

# logger = get_logger(__name__) # モジュール名でロガーを取得

# この関数内で USER_AGENTS や TWITTER_USERNAME が必要になるため、
# 設定ファイルから読み込むか、引数で渡す必要がある。
# ここでは、呼び出し元から設定情報を渡してもらうことを想定。

def get_driver(user_agent: str = None, profile_path: str = None, headless: bool = False):
    """
    共通のWebDriver初期化処理。
    User-Agent文字列とプロファイルパスを直接受け取るように変更。
    webdriver-managerでchromedriverを自動管理。
    """
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--start-maximized")
    # options.add_argument("--no-sandbox") # Linux環境で問題が起きる場合
    # options.add_argument("--disable-dev-shm-usage") # Docker環境などで

    if headless:
        options.add_argument("--headless")
        options.add_argument("--window-size=1920x1080") # ヘッドレスでもウィンドウサイズを指定

    # User-Agentの設定
    if user_agent:
        options.add_argument(f"user-agent={user_agent}")
        print(f"[WebDriverUtils] 使用するUser-Agent: {user_agent}") # ロガーがなければprint
    else:
        # デフォルトのUser-Agent (もし指定がなかった場合)
        default_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        options.add_argument(f"user-agent={default_ua}")
        print(f"[WebDriverUtils] デフォルトUser-Agentを使用: {default_ua}")

    # プロファイルディレクトリの設定
    if profile_path:
        # profile_path は呼び出し元で既に .cache/chrome_profiles/some_profile のようなフルパスが指定される想定
        os.makedirs(profile_path, exist_ok=True) # 念のため作成
        options.add_argument(f"--user-data-dir={profile_path}")
        print(f"[WebDriverUtils] ユーザープロファイルディレクトリ: {profile_path}")
    else:
        print("[WebDriverUtils] プロファイルパスが指定されなかったため、デフォルトプロファイルが使用されます。")

    try:
        # webdriver-managerでchromedriverを自動ダウンロード・管理
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        print("[WebDriverUtils] WebDriverの初期化が完了しました。(webdriver-manager使用)")
        return driver
    except Exception as e:
        print(f"[WebDriverUtils] WebDriverの初期化中にエラーが発生しました: {e}")
        # エラーログに詳細を出すため、可能であればロガーを使用したい
        # logger.error(f"WebDriverの初期化エラー: {e}", exc_info=True)
        raise # エラーを再送出

def quit_driver(driver):
    """WebDriverを安全に終了する"""
    if driver:
        try:
            driver.quit()
            print("[WebDriverUtils] WebDriverを正常に終了しました。")
        except Exception as e:
            print(f"[WebDriverUtils] WebDriver終了時にエラー: {e}")
            # logger.error(f"WebDriver終了エラー: {e}", exc_info=True)

if __name__ == '__main__':
    print("WebDriverUtils のテスト実行")
    
    # テスト用のUser-Agentとプロファイルパス
    test_ua = "TestAgent/3.0 (WebDriverUtils Test)"
    # プロジェクトルートを基準に .cache/test_profile を作成
    project_root_for_test = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # utilsの一つ上がプロジェクトルート
    test_profile_dir = os.path.join(project_root_for_test, ".cache", "chrome_profiles_test", "test_profile_main")
    print(f"テスト用プロファイルディレクトリ: {test_profile_dir}")

    # 1. User-Agentとプロファイルパスを指定して起動
    print("\n--- Test 1: UAとプロファイル指定 ---")
    driver1 = None
    try:
        driver1 = get_driver(user_agent=test_ua, profile_path=test_profile_dir)
        if driver1:
            print("Driver 1 起動成功、google.com を開きます...")
            driver1.get("https://www.google.com")
            print(f"現在のURL: {driver1.current_url}, タイトル: {driver1.title}")
            # driver1.save_screenshot(os.path.join(os.path.dirname(__file__), "test_google.png"))
            # print("スクリーンショット test_google.png を保存しました。")
        else:
            print("Driver 1 の取得に失敗しました。")
    except Exception as e:
        print(f"Test 1 でエラー: {e}")
    finally:
        if driver1:
            quit_driver(driver1)

    # 2. ヘッドレスモードで起動 (UAとプロファイルは同じものを使用)
    print("\n--- Test 2: ヘッドレスモード --- ")
    driver2 = None
    try:
        driver2 = get_driver(user_agent=test_ua, profile_path=test_profile_dir, headless=True)
        if driver2:
            print("Driver 2 (headless) 起動成功、bing.com を開きます...")
            driver2.get("https://www.bing.com")
            print(f"現在のURL: {driver2.current_url}, タイトル: {driver2.title}")
        else:
            print("Driver 2 の取得に失敗しました。")
    except Exception as e:
        print(f"Test 2 でエラー: {e}")
    finally:
        if driver2:
            quit_driver(driver2)

    # 3. 引数なし (デフォルト動作の確認)
    print("\n--- Test 3: 引数なし (デフォルト) ---")
    driver3 = None
    try:
        driver3 = get_driver() # プロファイルパスは指定しない
        if driver3:
            print("Driver 3 起動成功、example.com を開きます...")
            driver3.get("http://example.com")
            print(f"現在のURL: {driver3.current_url}, タイトル: {driver3.title}")
        else:
            print("Driver 3 の取得に失敗しました。")
    except Exception as e:
        print(f"Test 3 でエラー: {e}")
    finally:
        if driver3:
            quit_driver(driver3)

    print("\nWebDriverUtils のテスト完了") 