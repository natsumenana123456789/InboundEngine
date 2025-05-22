import os
import re
import cv2
import time
import json
import shutil
import requests
import pytesseract
import logging
from datetime import datetime
from PIL import Image, ImageFilter, ImageEnhance
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
    TimeoutException
)
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from .oauth_handler import OAuthHandler # Changed to local relative import

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
    def __init__(self, config):
        self.config = config
        self.twitter_config = config.get("twitter_account", {})
        self.scraping_config = config.get("scraping", {})
        self.google_drive_config = config.get("google_drive", {}) # Added for Drive
        self.driver = None
        self.logger = logging.getLogger(__name__)
        self.dom_error_log_dir = os.path.join(os.path.dirname(__file__), "logs", "dom_errors")
        if not os.path.exists(self.dom_error_log_dir):
            os.makedirs(self.dom_error_log_dir)

        # Initialize Google Drive Service
        self.drive_service = None
        if self.google_drive_config.get("enabled", False):
            try:
                oauth_handler = OAuthHandler() # Uses oauth_credentials.json and token.json from config/
                credentials = oauth_handler.get_credentials()
                self.drive_service = build('drive', 'v3', credentials=credentials)
                self.logger.info("✅ Google Drive service initialized successfully.")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize Google Drive service: {e}")
        
        self.temp_download_dir = os.path.join(os.path.dirname(__file__), "temp_media")
        if not os.path.exists(self.temp_download_dir):
            os.makedirs(self.temp_download_dir)

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

    def setup_driver(self):
        """ブラウザドライバーの設定"""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=ja-JP")
        options.add_argument("--disable-blink-features=AutomationControlled")
        # Add a common User-Agent string
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        options.add_argument(f"user-agent={user_agent}")
        # Add a unique user-data-dir to prevent session conflicts
        user_data_dir = os.path.join(os.path.dirname(__file__), 'chrome_profile', datetime.now().strftime('%Y%m%d%H%M%S%f'))
        options.add_argument(f"--user-data-dir={user_data_dir}")
        self.driver = webdriver.Chrome(options=options)
        return self.driver

    def login(self, target=None):
        """Twitterへのログイン処理"""
        cookies_path = os.path.join(os.path.dirname(__file__), ".cache", "twitter_cookies.json")
        if os.path.exists(cookies_path):
            self.logger.info("✅ Cookieセッション検出 → ログインスキップ")
            self.logger.info("🌐 https://twitter.com にアクセスしてクッキー読み込み中…")
            self.driver.get("https://twitter.com/")
            self.driver.delete_all_cookies()
            with open(cookies_path, "r") as f:
                cookies = json.load(f)
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
            self.driver.get(f"https://twitter.com/{target or self.twitter_config.get('username')}")
            return

        self.logger.info("🔐 初回ログイン処理を開始")
        self.driver.get("https://twitter.com/i/flow/login")
        try:
            email_input = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.NAME, "text"))
            )
            email_input.send_keys(self.twitter_config.get("email"))
            email_input.send_keys(Keys.ENTER)
            time.sleep(2)
        except TimeoutException as e_timeout: # Specifically catch TimeoutException
            screenshot_path = os.path.join(os.path.dirname(__file__), "logs", "login_timeout_error.png")
            self.driver.save_screenshot(screenshot_path)
            self.logger.error(f"❌ ログイン中のメール入力フィールドでタイムアウト。スクリーンショット: {screenshot_path}")
            raise e_timeout # Re-raise the exception after saving screenshot
        except Exception as e_general: # Catch other potential exceptions
            screenshot_path = os.path.join(os.path.dirname(__file__), "logs", "login_general_error.png")
            self.driver.save_screenshot(screenshot_path)
            self.logger.error(f"❌ ログイン中のメール入力で予期せぬエラー。スクリーンショット: {screenshot_path}")
            raise e_general # Re-raise

        try:
            username_input = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.NAME, "text"))
            )
            username_input.send_keys(self.twitter_config.get("username"))
            username_input.send_keys(Keys.ENTER)
            time.sleep(2)
        except TimeoutException: # Specifically catch TimeoutException for username
            self.logger.info("👤 ユーザー名入力フィールドでタイムアウト、スキップします。")
            # Optionally, save a screenshot here too if needed for debugging this step
            # screenshot_path = os.path.join(os.path.dirname(__file__), "logs", "login_username_timeout.png")
            # self.driver.save_screenshot(screenshot_path)
        except Exception:
            self.logger.info("👤 ユーザー名入力スキップ")

        try:
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_input.send_keys(self.twitter_config.get("password"))
            password_input.send_keys(Keys.ENTER)
            time.sleep(6)
        except TimeoutException as e_timeout_pw: # Specifically catch TimeoutException for password
            screenshot_path = os.path.join(os.path.dirname(__file__), "logs", "login_password_timeout.png")
            self.driver.save_screenshot(screenshot_path)
            self.logger.error(f"❌ ログイン中のパスワード入力フィールドでタイムアウト。スクリーンショット: {screenshot_path}")
            raise e_timeout_pw
        except Exception as e_general_pw: # Catch other potential exceptions
            screenshot_path = os.path.join(os.path.dirname(__file__), "logs", "login_password_general_error.png")
            self.driver.save_screenshot(screenshot_path)
            self.logger.error(f"❌ ログイン中のパスワード入力で予期せぬエラー。スクリーンショット: {screenshot_path}")
            raise e_general_pw

        cookies = self.driver.get_cookies()
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        with open(cookies_path, "w") as f:
            json.dump(cookies, f)
        self.logger.info("✅ ログイン成功 → 投稿者ページに遷移")
        self.driver.get(f"https://twitter.com/{target}")

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

    def extract_tweets(self, extract_target, max_tweets, globally_processed_ids, remaining_needed=None):
        """ツイートの抽出"""
        user_profile_url = f"https://twitter.com/{extract_target}"
        self.logger.info(f"\n✨ アクセス中: {user_profile_url}")
        self.driver.get(user_profile_url)
        time.sleep(3)

        url_collection_limit = None
        if remaining_needed is not None and remaining_needed > 0:
            url_collection_limit = min(remaining_needed * 2, 50) if remaining_needed <= 25 else 50
            self.logger.info(f"ℹ️ 残り必要数: {remaining_needed}件、URL取得上限: {url_collection_limit}件に調整")
        else:
            url_collection_limit = min(max_tweets * 2, 50) if max_tweets <= 25 else 50
            self.logger.info(f"ℹ️ 初回取得: max_tweets={max_tweets}件、URL取得上限: {url_collection_limit}件に設定")

        tweet_urls = []
        seen_urls_in_current_call = set()
        scroll_count = 0
        max_scrolls = self.scraping_config.get("max_scrolls_extract_tweets", 20)
        pause_threshold = self.scraping_config.get("pause_threshold_extract_tweets", 6)
        scroll_pause_time = self.scraping_config.get("scroll_pause_time", 2.5)
        pause_counter = 0

        while len(tweet_urls) < url_collection_limit and scroll_count < max_scrolls:
            articles = self.driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
            
            for article in articles:
                tweet_id = None
                try:
                    tweet_id = self.extract_tweet_id(article)
                    if not tweet_id or tweet_id in globally_processed_ids or tweet_id in seen_urls_in_current_call:
                        continue

                    text = ""
                    text_xpath = ".//div[@data-testid='tweetText']"
                    try:
                        text_elem = article.find_element(By.XPATH, text_xpath)
                        text = text_elem.text
                        self.logger.info(f"取得した本文 ({tweet_id}): {text}")
                    except NoSuchElementException:
                        article_html = article.get_attribute('innerHTML')
                        log_path = self._save_dom_error_log(article_html, f"tweet_text_{tweet_id or 'unknown'}")
                        self.logger.error(f"本文取得失敗 ({tweet_id or 'unknown'}): XPathが見つかりません - {text_xpath}. HTMLログ: {log_path}")
                    except Exception as e:
                        self.logger.error(f"本文取得中に予期せぬエラー ({tweet_id or 'unknown'}): {e}")

                    username = ""
                    # Attempt to get username (@handle) first
                    user_id_xpath = ".//div[@data-testid='User-Name']/following-sibling::div//a[starts-with(@href, '/')]//span[starts-with(text(), '@')]"
                    display_name_xpath = ".//div[@data-testid='User-Name']//span[contains(@class, 'css-1jxf684')]/span[contains(@class, 'css-1jxf684')]"
                    user_profile_link_xpath = ".//div[@data-testid='User-Name']//a[starts-with(@href, '/') and .//span[contains(@class, 'css-1jxf684')]]"

                    try:
                        # Try to get the @username from the link's href near display name
                        # WebDriverWait for the user profile link within the article context
                        user_profile_link_element = WebDriverWait(article, 2).until(
                            EC.presence_of_element_located((By.XPATH, user_profile_link_xpath))
                        )
                        href_value = user_profile_link_element.get_attribute("href")
                        if href_value:
                            username = href_value.split('/')[-1]
                            self.logger.info(f"取得した投稿者 (from href): {username}")
                        else:
                            # Fallback to display name if href is not found or empty
                            display_name_element = WebDriverWait(article, 1).until(
                                EC.presence_of_element_located((By.XPATH, display_name_xpath))
                            )
                            username = display_name_element.text
                            self.logger.info(f"取得した投稿者 (display name): {username}")
                    except Exception: # Changed from NoSuchElementException to broader Exception for timeout
                        article_html = article.get_attribute('innerHTML')
                        log_path = self._save_dom_error_log(article_html, f"tweet_username_{tweet_id or 'unknown'}")
                        self.logger.error(f"投稿者取得失敗 ({tweet_id or 'unknown'}): User-Name XPath (href or display name) が見つかりません. Searched XPaths: [{user_profile_link_xpath}, {display_name_xpath}]. HTMLログ: {log_path}")
                    except Exception as e:
                        self.logger.error(f"投稿者取得中に予期せぬエラー ({tweet_id or 'unknown'}): {e}")
                        
                    media_urls = []
                    # 画像URLの抽出とデバッグログの追加
                    image_xpath_patterns = [
                        # 通常の画像ツイート（imgタグ、mediaまたはcard_img）
                        ".//div[@data-testid='tweetPhoto']//img[contains(@src, 'pbs.twimg.com/media') or contains(@src, 'pbs.twimg.com/card_img')]",
                        # style属性のbackground-image（articleタグ直下、mediaまたはcard_img）
                        ".//article[@data-testid='tweet']//div[contains(@style, \"background-image: url('https://pbs.twimg.com/media')\")]",
                        ".//article[@data-testid='tweet']//div[contains(@style, \"background-image: url('https://pbs.twimg.com/card_img')\")]",
                        # カード型ツイートのimgタグ（card_img）
                        ".//div[contains(@data-testid, 'card.layoutLarge.media')]//img[contains(@src, 'pbs.twimg.com/card_img')]",
                        # カード型ツイートのstyle属性background-image（card_img）
                        ".//div[contains(@data-testid, 'card.layoutLarge.media')]//div[contains(@style, \"background-image: url('https://pbs.twimg.com/card_img')\")]"
                    ]

                    all_image_elements = []
                    for pattern in image_xpath_patterns:
                        try:
                            elements = article.find_elements(By.XPATH, pattern)
                            all_image_elements.extend(elements)
                        except Exception as e_xpath:
                            self.logger.debug(f"XPath検索中にエラー ({tweet_id or 'unknown'}): {pattern}, Error: {e_xpath}")
                            # ここではエラーがあっても続行し、他のパターンで試行する

                    try:
                        if not all_image_elements:
                            pass # 画像なしツイートの場合はログ出力しない

                        # 重複する可能性のある要素をsrcやstyle属性で一意にする
                        processed_image_sources = set()

                        for img_element in all_image_elements:
                            src = None
                            try:
                                if img_element.tag_name == 'img':
                                    src = img_element.get_attribute("src")
                                elif img_element.tag_name == 'div':
                                    style = img_element.get_attribute("style")
                                    match = re.search(r'background-image: url\([\'\"](.+?)[\'\"]\)', style) # シングルまたはダブルクォートに対応
                                    if match:
                                        src = match.group(1)
                            except StaleElementReferenceException:
                                self.logger.warning(f"画像要素が古くなりました ({tweet_id or 'unknown'})。スキップします。")
                                continue # 次の要素へ
                            except Exception as e_attr:
                                self.logger.warning(f"画像属性取得中にエラー ({tweet_id or 'unknown'}) 要素: {img_element.tag_name}, Error: {e_attr}")
                                continue

                            if src and src not in processed_image_sources:
                                processed_image_sources.add(src) # 処理済みソースとして追加
                                # Ensure we get the full URL if there are query parameters like format=jpg&name=small
                                if "?" in src:
                                    src_to_add = src.split("?")[0] + "?format=jpg&name=orig"
                                else:
                                    src_to_add = src

                                # 動画のサムネイル(poster)と重複する可能性のあるcard_imgを避ける
                                if "video_thumb" not in src_to_add and "amplify_video_thumb" not in src_to_add:
                                    if src_to_add not in media_urls:
                                        media_urls.append(src_to_add)
                                    
                    except Exception as e_proc:
                        self.logger.error(f"画像処理中に予期せぬエラー ({tweet_id or 'unknown'}): {e_proc}", exc_info=True)

                    # 動画URLの抽出とデバッグログの追加
                    videos_xpath = ".//div[@data-testid='videoPlayer']//video | .//div[@data-testid='tweetAttachments']//video[contains(@src, 'video.twimg.com')]"
                    try:
                        video_elements = article.find_elements(By.XPATH, videos_xpath)
                        if not video_elements:
                            # self.logger.debug(f"動画要素が見つかりませんでした ({tweet_id})。 XPath: {videos_xpath}")
                            pass
                        for video in video_elements:
                            src = video.get_attribute("src")
                            poster = video.get_attribute("poster") # ポスター画像も候補として追加
                            if src and src not in media_urls:
                                media_urls.append(src)
                            elif poster and poster.startswith("https://pbs.twimg.com/media/") and poster not in media_urls:
                                 media_urls.append(poster) # videoタグのsrcがない場合、poster画像も試す
                    except NoSuchElementException:
                        article_html = article.get_attribute('innerHTML')
                        log_path = self._save_dom_error_log(article_html, f"tweet_videos_{tweet_id or 'unknown'}")
                        self.logger.warning(f"動画要素の検索で予期せぬエラー ({tweet_id or 'unknown'})。XPath: {videos_xpath}. HTMLログ: {log_path}")

                    self.logger.info(f"取得したmedia_urls ({tweet_id}): {media_urls}")

                    # Process media and upload to Google Drive if enabled
                    final_media_links_for_notion = []
                    if self.drive_service and self.google_drive_config.get("enabled", False) and media_urls:
                        self.logger.info(f"[Drive] Processing {len(media_urls)} media items for tweet {tweet_id}")
                        for original_media_url in media_urls:
                            local_path = self._download_media(original_media_url, tweet_id)
                            if local_path:
                                drive_link = self._upload_to_drive_and_get_link(local_path, tweet_id)
                                if drive_link:
                                    final_media_links_for_notion.append(drive_link)
                                else:
                                    # Upload failed, keep original URL as fallback or handle error
                                    self.logger.warning(f"[Drive] Upload failed for {original_media_url}, keeping original link.")
                                    final_media_links_for_notion.append(original_media_url) # Fallback
                            else:
                                # Download failed
                                self.logger.warning(f"[Drive] Download failed for {original_media_url}, keeping original link.")
                                final_media_links_for_notion.append(original_media_url) # Fallback
                    else:
                        # Drive not enabled or no media, use original X media URLs
                        final_media_links_for_notion = media_urls

                    tweet_urls.append({
                        "id": tweet_id,
                        "url": f"https://twitter.com/{extract_target}/status/{tweet_id}",
                        "text": text,
                        "username": username,
                        "media_urls": final_media_links_for_notion # Use Drive links if available
                    })
                    seen_urls_in_current_call.add(tweet_id)

                    if len(tweet_urls) >= url_collection_limit:
                        break

                except Exception as e:
                    self.logger.error(f"⚠️ ツイート抽出処理中に予期せぬエラー ({tweet_id or 'unknown'}): {str(e)}", exc_info=True)
                    continue

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            scroll_count += 1

            if len(seen_urls_in_current_call) == len(tweet_urls):
                pause_counter += 1
                if pause_counter >= pause_threshold:
                    self.logger.info(f"⚠️ {pause_threshold}回連続で新規ツイートが見つからないため、スクロールを停止")
                    break
            else:
                pause_counter = 0
            
        return tweet_urls

    def is_ad_post(self, text):
        """広告投稿の判定"""
        lowered = text.lower()
        return any(k.lower() in lowered for k in AD_KEYWORDS)

    def cleanup(self):
        """リソースのクリーンアップ"""
        if self.driver:
            self.driver.quit()
            self.logger.info("WebDriverをクリーンアップしました。")

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