import os
import re
# import cv2 # ocr_image 内で import numpy as np, cv2 されているので不要かも
import time
import json
import shutil
import requests
import pytesseract
# import logging # logger をコンストラクタで受け取るので不要
from datetime import datetime
from PIL import Image, ImageFilter, ImageEnhance
# from selenium import webdriver # webdriver_utils に移行
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.chrome.options import Options # webdriver_utils に移行
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
    TimeoutException
)
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from .oauth_handler import OAuthHandler
from ...utils.webdriver_utils import get_driver, quit_driver
from ...utils.logger import setup_logger
import random

# 広告除外キーワード
AD_KEYWORDS = [
    "r10.to",
    "ふるさと納税",
    "カードローン",
    "お金借りられる",
    "ビューティガレージ",
    "UNEXT",
    "エコオク",
    "#PR",
    "楽天",
    "Amazon",
    "A8",
    "アフィリエイト",
    "副業",
    "bit.ly",
    "shp.ee",
    "t.co/",
]

class TweetScraper:
    def __init__(self, bot_config, parent_logger=None):
        self.bot_config = bot_config
        self.logger = parent_logger if parent_logger else setup_logger(log_dir_name='bots/curate_bot/logs', logger_name='TweetScraper_default')
        
        # bot_config からTwitterアカウント情報を取得
        twitter_account_info = self.bot_config.get("twitter_account", {})
        self.username = twitter_account_info.get("username")
        self.password = twitter_account_info.get("password")
        self.email = twitter_account_info.get("email") # Emailも追加 (必要な場合)

        # bot_config からUser-Agentリストを取得
        user_agents = self.bot_config.get("user_agents", [])
        if not user_agents:
            self.logger.warning("⚠️ User-Agentが設定されていません。デフォルトのWebDriverのUser-Agentが使用されます。")
            self.user_agent = None # get_driverにNoneを渡すとよしなに処理される
        else:
            self.user_agent = random.choice(user_agents)
            self.logger.info(f"🤖 使用するUser-Agent: {self.user_agent}")

        # bot_config からWebDriverのプロファイルパスを取得
        profile_name_suffix = twitter_account_info.get("profile_name_suffix", "default")
        self.profile_path = os.path.join(
            os.path.dirname(__file__),  # このファイル(tweet_scraper.py)のディレクトリ
            ".cache",                   # .cacheサブディレクトリ
            f"chrome_profile_{profile_name_suffix}" # プロファイル名 (アカウントごとに変える)
        )
        os.makedirs(self.profile_path, exist_ok=True)
        self.logger.info(f"Chromeプロファイルパス: {self.profile_path}")

        self.driver = None
        self._setup_driver() # コンストラクタでドライバをセットアップ

    def _setup_driver(self):
        """WebDriverを初期化する"""
        if self.driver:
            self.logger.info("WebDriverは既に初期化されています。")
            return
        try:
            self.driver = get_driver(user_agent=self.user_agent, profile_path=self.profile_path)
            self.logger.info("✅ WebDriverのセットアップが完了しました。")
        except Exception as e:
            self.logger.error(f"❌ WebDriverのセットアップ中にエラーが発生しました: {e}", exc_info=True)
            raise # エラーを再送出して、呼び出し元で処理できるようにする

    def login(self, target_username):
        if not self.driver:
            self.logger.error("❌ WebDriverが初期化されていません。ログインできません。")
            self._setup_driver() # 再度セットアップを試みる
            if not self.driver: # それでもダメなら例外
                 raise RuntimeError("WebDriverのセットアップに失敗しました。")

        if not self.username or not self.password:
            self.logger.error("❌ Twitterのユーザー名またはパスワードが設定されていません。")
            raise ValueError("Twitterの認証情報が不足しています。")

        self.logger.info(f"Twitterへのログインを開始します: {self.username}")
        self.driver.get("https://twitter.com/login")
        time.sleep(random.uniform(2, 4))

        try:
            # ユーザー名入力フィールド
            username_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='text']"))
            )
            username_input.send_keys(self.username)
            self.logger.info(f"ユーザー名 {self.username} を入力しました。")
            
            # 「次へ」ボタン (最初の画面)
            next_button_xpath = "//span[contains(text(),'Next') or contains(text(),'次へ')]"
            next_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, next_button_xpath))
            )
            next_button.click()
            self.logger.info("「次へ」ボタンをクリックしました。")
            time.sleep(random.uniform(1.5, 3))

            # パスワード入力フィールド (現在のTwitter UIでは、時々追加の確認が入ることがある)
            # 例: 電話番号やメールアドレスを要求される場合など。ここでは単純なパスワード入力のみを想定。
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
            )
            password_input.send_keys(self.password)
            self.logger.info("パスワードを入力しました。")

            # 「ログイン」ボタン
            login_button_xpath = "//span[contains(text(),'Log in') or contains(text(),'ログイン')]"
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, login_button_xpath))
            )
            login_button.click()
            self.logger.info("「ログイン」ボタンをクリックしました。")
            time.sleep(random.uniform(3, 5))

            # ログイン成功の確認 (例: タイムラインが表示されるか)
            # より堅牢な確認方法が必要な場合がある
            if "home" in self.driver.current_url.lower():
                self.logger.info("✅ Twitterへのログインに成功しました！")
            else:
                # ログイン後に想定外のURLにいる場合、追加の確認(メール認証など)を求められている可能性がある
                self.logger.warning(f"⚠️ ログイン後のURLが予期したものではありません: {self.driver.current_url}")
                if self.email: # メールアドレスが設定されていれば、それを入力してみる試み
                    try:
                        email_confirm_input_xpath = "//input[@name='text' and @type='text']" # これは推測
                        email_confirm_input = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, email_confirm_input_xpath))
                        )
                        if email_confirm_input.is_displayed():
                            self.logger.info(f"追加の確認としてメールアドレス {self.email} の入力を試みます。")
                            email_confirm_input.send_keys(self.email)
                            # 再度「次へ」ボタンを探す (同じXPATHeやCSSセレクタかもしれない)
                            next_button_after_email = WebDriverWait(self.driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH, next_button_xpath)) # 最初の「次へ」と同じセレクタを試す
                            )
                            next_button_after_email.click()
                            self.logger.info("メールアドレス入力後の「次へ」ボタンをクリックしました。")
                            time.sleep(random.uniform(3,5))
                            if "home" in self.driver.current_url.lower():
                                self.logger.info("✅ メールアドレスによる追加確認後、ログインに成功しました！")
                            else:
                                self.logger.error(f"❌ メールアドレス入力後もログインに失敗しました。現在のURL: {self.driver.current_url}")
                                raise Exception("ログインシーケンスの追加確認に失敗しました。")
                    except Exception as e_confirm:
                        self.logger.error(f"❌ ログイン後の追加確認処理中にエラーが発生しました: {e_confirm}", exc_info=False)
                        # 追加確認が失敗しても、元のログイン失敗として扱う
                        self.logger.error("❌ Twitterへのログインに失敗しました。 (追加確認プロセス後)")
                        # ここでスクリーンショットを取るなどのデバッグ情報を追加しても良い
                        # self.driver.save_screenshot(os.path.join(self.profile_path, "login_failure_screenshot.png"))
                        raise Exception("ログインに失敗しました。タイムラインに遷移できませんでした。")
                else:
                    self.logger.error("❌ Twitterへのログインに失敗しました。 (追加確認が必要そうですがメールアドレス未設定)")
                    raise Exception("ログインに失敗しました。タイムlineに遷移できませんでした。")

        except Exception as e:
            self.logger.error(f"❌ ログイン処理中にエラーが発生しました: {e}", exc_info=True)
            # self.driver.save_screenshot(os.path.join(self.profile_path, "login_error_screenshot.png"))
            self.cleanup()
            raise

    def extract_tweets(self, username, max_tweets, globally_processed_ids):
        if not self.driver:
            self.logger.error("❌ WebDriverが初期化されていません。ツイートを収集できません。")
            raise RuntimeError("WebDriverが初期化されていません。")

        self.logger.info(f"{username} のツイート収集を開始します。最大 {max_tweets} 件。")
        self.driver.get(f"https://twitter.com/{username}")
        time.sleep(random.uniform(3,5)) # ページ読み込み待ち

        tweets_data = []
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        collected_count = 0

        while collected_count < max_tweets:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2,4)) # スクロール後のコンテンツ読み込み待ち
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            # ページ上のツイート要素を取得 (セレクタはXのUI変更に合わせて調整が必要な場合がある)
            # ここでは 'article' タグでツイートを大まかに取得する例
            tweet_elements = self.driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
            self.logger.info(f"現在 {len(tweet_elements)} 個のツイート要素を検出しました。")

            for el in tweet_elements:
                if collected_count >= max_tweets:
                    break
                try:
                    tweet_text_element = el.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
                    tweet_text = tweet_text_element.text
                    # tweet_id はURLなどから取得する必要がある。
                    # XPATHで permalink を探し、その href からIDを抽出する例
                    permalink_element = el.find_element(By.XPATH, ".//a[contains(@href, '/status/') and .//time]")
                    tweet_link = permalink_element.get_attribute('href')
                    tweet_id = tweet_link.split('/')[-1]

                    if tweet_id in globally_processed_ids:
                        self.logger.debug(f"スキップ (処理済み): {tweet_id}")
                        continue
                        
                    # 画像/動画のURLを取得 (複数ある場合も考慮)
                    media_urls = [] 
                    # 画像の場合: .//div[@data-testid='photos']//img
                    image_elements = el.find_element(By.XPATH, ".//div[@data-testid='photos']//img[contains(@src, 'format=')]")
                    for img_el in image_elements:
                        img_src = img_el.get_attribute('src')
                        # URLからクエリパラメータを除去して高解像度版を取得する試み (例: &name=small を除く)
                        img_src_high_res = img_src.split('&name=')[0] if '&name=' in img_src else img_src
                        media_urls.append(img_src_high_res)
                    
                    # 動画の場合: .//div[@data-testid='videoPlayer']//video (これは簡略化された例、実際はもっと複雑)
                    # Xの動画は直接的な <video src="..."> 形式ではないことが多い。
                    # ストリーミングマニフェスト (m3u8) や blob URL を扱う必要があるかもしれない。
                    # ここでは単純化のため、動画の直接的な抽出は実装していない。
                    # 代わりに、動画を含むツイートの permalink をメディアとして扱うことも考えられる。

                    tweets_data.append({
                        "id": tweet_id,
                        "text": tweet_text,
                        "user": username, # 本来はツイートから取得すべき
                        "url": tweet_link,
                        "media_urls": media_urls,
                        "created_at": permalink_element.find_element(By.TAG_NAME, "time").get_attribute("datetime") # 投稿日時
                    })
                    globally_processed_ids.add(tweet_id) # 収集済みとしてIDを記録
                    collected_count += 1
                    self.logger.info(f"収集済み: {collected_count}/{max_tweets} (ID: {tweet_id}) - Media: {len(media_urls)}")

                except Exception as e:
                    # self.logger.warning(f"ツイート要素の解析中にエラー: {e}", exc_info=True)
                    # 一つのツイートの解析エラーで全体を止めない
                    pass 
            
            if new_height == last_height and collected_count < max_tweets:
                self.logger.info("ページの最下部までスクロールしましたが、新しいツイートはありませんでした。収集を終了します。")
                break
            last_height = new_height
            if collected_count == 0 and len(tweet_elements) > 50: # 要素は大量にあるのに一つも収集できない場合（セレクタが古い可能性など）
                self.logger.warning("多数のツイート要素を検出しましたが、内容を抽出できませんでした。セレクタが古い可能性があります。")
                break

        self.logger.info(f"収集完了: {username} から {collected_count} 件のツイートを取得しました。")
        return tweets_data[:max_tweets] # max_tweets を超えないようにスライス

    def cleanup(self):
        if self.driver:
            self.logger.info("WebDriverをクリーンアップします。")
            quit_driver(self.driver)
            self.driver = None

    def _save_dom_error_log(self, element_html, error_identifier):
        """DOMエラーHTMLをファイルに保存し、ファイルパスを返す"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        # Sanitize error_identifier for filename
        safe_error_identifier = re.sub(r'[^a-zA-Z0-9_\'-]', '_', error_identifier)
        filename = f"error_dom_{safe_error_identifier}_{timestamp}.html"
        filepath = os.path.join(self.dom_error_log_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(element_html)
            return filepath
        except Exception as e:
            self.logger.error(f"DOMエラーログファイルの保存に失敗しました: {filepath}, Error: {e}")
            return None

    def extract_tweet_id(self, article):
        """ツイートIDの抽出"""
        tweet_id_xpath = ".//a[contains(@href, '/status/')]"
        try:
            href_els = article.find_elements(By.XPATH, tweet_id_xpath)
            for el in href_els:
                h = el.get_attribute("href")
                m = re.search(r"/status/(\d+)", h or "")
                if m:
                    return m.group(1)
        except NoSuchElementException:
            article_html = article.get_attribute('innerHTML')
            log_path = self._save_dom_error_log(article_html, "tweet_id_extraction")
            self.logger.error(f"❌ ツイートIDのhref要素が見つかりません。XPath: {tweet_id_xpath}. HTMLログ: {log_path}")
        return None

    def ocr_image(self, image_path):
        """画像のOCR処理"""
        try:
            img = Image.open(image_path)
            img = img.convert("L")
            img = img.resize((img.width * 2, img.height * 2))
            img = ImageEnhance.Contrast(img).enhance(2.0)
            img = img.filter(ImageFilter.SHARPEN)
            import numpy as np

            img_np = np.array(img)
            img_np = cv2.medianBlur(img_np, 3)
            _, img_np = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            img = Image.fromarray(img_np)
            text = pytesseract.image_to_string(img, lang="jpn", config="--oem 1 --psm 6")
            self.logger.info(f"📝 OCR画像({image_path})結果:\n{text.strip()}")
            if not text.strip() or sum(c.isalnum() for c in text) < 3:
                self.logger.warning(f"⚠️ OCR画像({image_path})で文字化けまたは認識失敗の可能性")
            return text.strip()
        except Exception as e:
            self.logger.error(f"OCR失敗({image_path}): {e}")
            return "[OCRエラー]"

    def is_ad_post(self, text):
        """広告投稿の判定"""
        lowered = text.lower()
        return any(k.lower() in lowered for k in AD_KEYWORDS)

    def _download_media(self, media_url, tweet_id):
        """Downloads media from a URL to a temporary local path."""
        try:
            response = requests.get(media_url, stream=True)
            response.raise_for_status()
            
            # Extract filename from URL or generate one
            filename = media_url.split("/")[-1].split("?")[0] # Basic filename
            if not filename:
                filename = f"{tweet_id}_{datetime.now().strftime('%Y%m%d%HM%S%f')}"
            
            # Ensure filename has an extension (guess if necessary)
            if '.' not in filename:
                content_type = response.headers.get('content-type')
                if content_type:
                    if 'image/jpeg' in content_type: filename += '.jpg'
                    elif 'image/png' in content_type: filename += '.png'
                    elif 'video/mp4' in content_type: filename += '.mp4'
                    # Add more content types as needed
                    else: filename += '.tmp' # Fallback
                else:
                    filename += '.tmp' # Fallback if no content type

            local_filepath = os.path.join(self.temp_download_dir, filename)
            
            with open(local_filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            self.logger.info(f"⬇️ Media downloaded: {media_url} to {local_filepath}")
            return local_filepath
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Failed to download media {media_url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"❌ Unexpected error downloading media {media_url}: {e}")
            return None

    def _upload_to_drive_and_get_link(self, local_filepath, tweet_id):
        """Uploads a file to Google Drive and returns a shareable link."""
        if not self.drive_service:
            self.logger.error("❌ Drive service not initialized. Cannot upload.")
            return None
        if not local_filepath or not os.path.exists(local_filepath):
            self.logger.error(f"❌ Local file not found for upload: {local_filepath}")
            return None

        try:
            file_metadata = {
                'name': os.path.basename(local_filepath),
                'parents': [self.google_drive_config.get("folder_id")] 
            }
            media = MediaFileUpload(local_filepath, resumable=True)
            file = self.drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
            
            file_id = file.get("id")
            shareable_link = file.get("webViewLink") # This is a direct view link

            # Make the file publicly readable (or share with specific users/groups if needed)
            # For simplicity, making it publicly readable. Adjust permissions as needed.
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            self.drive_service.permissions().create(fileId=file_id, body=permission).execute()
            
            # To get a direct download link, a bit more work is needed, or use webViewLink
            self.logger.info(f"⬆️ File uploaded to Drive: {os.path.basename(local_filepath)}, ID: {file_id}, Link: {shareable_link}")
            
            # Clean up local file after upload
            try:
                os.remove(local_filepath)
                self.logger.info(f"🗑️ Temporary local file deleted: {local_filepath}")
            except OSError as e:
                self.logger.error(f"❌ Failed to delete temporary local file {local_filepath}: {e}")

            return shareable_link
        except Exception as e:
            self.logger.error(f"❌ Failed to upload to Drive or set permissions for {local_filepath}: {e}")
            return None 