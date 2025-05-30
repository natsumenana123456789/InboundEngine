import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

def login_to_twitter_with_selenium(driver, username, password, email=None, logger=None):
    """
    Twitterログイン共通処理。
    - 既存セッションの確認
    - セッションが無効な場合のみ新規ログイン
    - ログイン成功でTrue、失敗でFalse
    """
    try:
        # ログイン情報の確認
        if logger:
            logger.info(f"ログイン情報: username={username}, email={email}")
            logger.info(f"パスワードの長さ: {len(password) if password else 0}")

        # まずホームページにアクセスしてセッション確認
        driver.get("https://twitter.com/home")
        time.sleep(random.uniform(3, 5))

        # セッションが有効かチェック（ツイートボタンの存在で判定）
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='tweetTextarea_0']"))
            )
            if logger: logger.info("既存のセッションが有効です。ログインはスキップします。")
            return True
        except TimeoutException:
            if logger: logger.info("既存のセッションが無効です。新規ログインを開始します。")

        # 現在のURLを確認
        current_url = driver.current_url
        if logger: logger.info(f"現在のURL: {current_url}")

        # リダイレクトURLの場合も含めてログインページにアクセス
        if "flow/login" in current_url:
            if logger: logger.info("リダイレクトURLからログインを試みます。")
        else:
            driver.get("https://twitter.com/i/flow/login")
            time.sleep(random.uniform(3, 5))

        # ユーザー名入力欄を探す（複数のセレクタを試す）
        username_input = None
        selectors = [
            "input[autocomplete='username']",
            "input[name='text']",
            "input[type='text']",
            "input[placeholder*='ユーザー名']",
            "input[placeholder*='username']"
        ]

        if logger: logger.info("ユーザー名入力欄を探しています...")
        for selector in selectors:
            try:
                if logger: logger.info(f"セレクタ '{selector}' を試しています...")
                username_input = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                if username_input:
                    if logger: logger.info(f"セレクタ '{selector}' でユーザー名入力欄を見つけました。")
                    break
            except TimeoutException:
                if logger: logger.info(f"セレクタ '{selector}' では見つかりませんでした。")
                continue

        if not username_input:
            if logger: logger.info("セレクタでの検索に失敗したため、全input要素を確認します...")
            # 最後の手段として、すべてのinput要素を確認
            all_inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in all_inputs:
                ph = inp.get_attribute("placeholder")
                if logger: logger.info(f"input要素のplaceholder: {ph}")
                if ph and ("ユーザー名" in ph or "username" in ph.lower()):
                    username_input = inp
                    if logger: logger.info("placeholderからユーザー名入力欄を見つけました。")
                    break

        if not username_input:
            if logger: logger.error("ユーザー名入力欄が見つかりませんでした。")
            return False

        # ユーザー名入力
        if logger: 
            logger.info("ユーザー名入力欄が見つかりました。ユーザー名を入力します。")
            logger.info(f"入力するユーザー名: {username}")
        username_input.clear()
        username_input.send_keys(username)
        username_input.send_keys(Keys.RETURN)
        time.sleep(random.uniform(3, 5))

        # メールアドレス入力欄 or パスワード入力欄のどちらが出るか判定
        email_input = None
        password_input = None

        # メールアドレス入力欄を探す
        email_selectors = [
            "input[name='text']",
            "input[type='text']",
            "input[placeholder*='メール']",
            "input[placeholder*='email']"
        ]

        if logger: logger.info("メールアドレス入力欄を探しています...")
        for selector in email_selectors:
            try:
                if logger: logger.info(f"セレクタ '{selector}' を試しています...")
                email_input = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                if email_input:
                    if logger: logger.info(f"セレクタ '{selector}' でメールアドレス入力欄を見つけました。")
                    break
            except TimeoutException:
                if logger: logger.info(f"セレクタ '{selector}' では見つかりませんでした。")
                continue

        # パスワード入力欄を探す
        try:
            if logger: logger.info("パスワード入力欄を探しています...")
            password_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
            )
            if logger: logger.info("パスワード入力欄を見つけました。")
        except TimeoutException:
            if logger: logger.info("パスワード入力欄が見つかりませんでした。")

        if email_input:
            if logger: 
                logger.info("メールアドレス入力欄が表示されました。メールアドレスを入力します。")
                logger.info(f"入力するメールアドレス: {email}")
            email_input.clear()
            email_input.send_keys(email)
            email_input.send_keys(Keys.RETURN)
            time.sleep(random.uniform(3, 5))
            
            # メールアドレス入力後、パスワード入力欄を待つ
            try:
                password_input = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
                )
                if logger: logger.info("メールアドレス入力後、パスワード入力欄を見つけました。")
            except TimeoutException:
                if logger: logger.error("メールアドレス入力後、パスワード入力欄が見つかりませんでした。")
                return False
        elif password_input:
            if logger: logger.info("メールアドレス入力欄はスキップされ、パスワード入力欄が表示されました。パスワードを入力します。")
        else:
            if logger: logger.error("メールアドレス入力欄もパスワード入力欄も見つかりませんでした。")
            return False

        # パスワード入力
        if logger: 
            logger.info("パスワードを入力します。")
            logger.info(f"パスワードの長さ: {len(password)}")
        password_input.clear()
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)
        time.sleep(random.uniform(4, 6))

        # ログイン成功の確認
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='tweetTextarea_0']"))
            )
            if logger: logger.info("ログインに成功しました。")
            return True
        except TimeoutException:
            if logger: logger.error("ログイン後のホーム画面への遷移が確認できませんでした。")
            return False

    except Exception as e:
        if logger:
            logger.error(f"ログイン中にエラーが発生しました: {e}", exc_info=True)
        return False 