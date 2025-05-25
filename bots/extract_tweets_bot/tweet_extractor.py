import os
import sys
import re
# import cv2 # ocr_image 内で import numpy as np, cv2 されているので不要かも
import time
import json
import shutil
import requests
import pytesseract
# import logging # logger をコンストラクタで受け取るので不要
from datetime import datetime, timedelta, timezone
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
    TimeoutException,
    ElementClickInterceptedException,
    WebDriverException
)
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from typing import List, Dict, Optional, Tuple, Any

# プロジェクトルートをsys.pathに追加
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# from utils.oauth_handler import OAuthHandler # TODO: OAuthHandler の必要性を確認し、必要であれば正しいパスからインポートする
from utils.webdriver_utils import get_driver, quit_driver
from utils.logger import setup_logger
import random
from notion_client import Client
from bs4 import BeautifulSoup
from config import config_loader

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

class TweetExtractor:
    def __init__(self, bot_config: Dict[str, Any], parent_logger=None):
        self.config = bot_config # bot_config は curate_bot の設定全体を想定
        # ログ関連のディレクトリ設定
        # bots/extract_tweets_bot/logs/
        # bots/extract_tweets_bot/logs/dom_errors/
        # bots/extract_tweets_bot/logs/screenshots/
        self.log_dir_name = self.config.get('log_dir_name', 'bots/extract_tweets_bot/logs')
        self.log_dir = os.path.join(PROJECT_ROOT, self.log_dir_name)
        self.error_log_dir = os.path.join(self.log_dir, 'dom_errors') # DOMスナップショット用
        self.screenshots_dir = os.path.join(self.log_dir, 'screenshots') # スクリーンショット用
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.error_log_dir, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)

        self.logger = parent_logger if parent_logger else setup_logger(log_dir_name=self.log_dir_name, logger_name='TweetExtractor_default')
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.logged_in_user: Optional[str] = None

        # ログイン情報: bot_config (curate_botの設定) から直接取得する
        active_account_id = self.config.get("active_curation_account_id")
        twitter_accounts_list = self.config.get("twitter_accounts", [])
        
        selected_account_info = None
        if active_account_id and twitter_accounts_list:
            for acc in twitter_accounts_list:
                if acc.get("account_id") == active_account_id:
                    selected_account_info = acc
                    break
        elif twitter_accounts_list: # active_id がない場合、最初のアカウントを利用
            self.logger.warning(f"active_curation_account_id が見つからないため、twitter_accounts の最初のアカウントを使用します。")
            selected_account_info = twitter_accounts_list[0]

        if selected_account_info:
            self.username = selected_account_info.get("username")
            self.password = selected_account_info.get("password")
            # 必要であれば email も取得: self.email = selected_account_info.get("email")
        else:
            self.username = None
            self.password = None
            self.logger.error("有効なTwitterアカウント情報が curate_bot の設定から見つかりませんでした。")

        if not self.username or not self.password:
            self.logger.error("Twitterのユーザー名またはパスワードが設定されていません。処理を続行できません。")
            raise ValueError("Twitterの認証情報が curate_bot の設定に見つかりません。")

        self.logger.info(f"読み込まれたユーザー名: {self.username}")
        if self.password:
            self.logger.info(f"読み込まれたパスワードの長さ: {len(self.password)}")
        else:
            self.logger.warning("パスワードが設定されていません。")

        # WebDriver設定
        self.user_agent = self.config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.logger.info(f"🤖 使用するUser-Agent: {self.user_agent}")
        # プロファイルパスを bots/extract_tweets_bot/.cache/chrome_profile_extract に変更
        self.profile_path = self.config.get("chrome_profile_path", os.path.join(PROJECT_ROOT, "bots", "extract_tweets_bot", ".cache", "chrome_profile_extract"))
        self.logger.info(f"Chromeプロファイルパス: {self.profile_path}")
        os.makedirs(os.path.dirname(self.profile_path), exist_ok=True) # プロファイルディレクトリがなければ作成

        self._setup_driver()

    def _setup_driver(self):
        if self.driver:
            self.logger.info("WebDriverは既に初期化されています。")
            return
        try:
            self.driver = get_driver(user_agent=self.user_agent, profile_path=self.profile_path)
            self.logger.info("✅ WebDriverのセットアップが完了しました。")
        except Exception as e:
            self.logger.error(f"❌ WebDriverのセットアップ中にエラーが発生しました: {e}", exc_info=True)
            raise

    def login(self, target_username):
        if not self.driver:
            self.logger.error("❌ WebDriverが初期化されていません。ログインできません。")
            self._setup_driver()
            if not self.driver:
                 raise RuntimeError("WebDriverのセットアップに失敗しました。")

        # 既にログイン済みか確認 (例: URLに /home が含まれるか)
        # より確実なのは、ログイン後に表示されるべき特定の要素の存在確認
        try:
            if "/home" in self.driver.current_url.lower():
                self.logger.info("既にTwitterにログイン済みです。ログイン処理をスキップします。")
                # ログインユーザー名を特定できれば self.logged_in_user にセットすることも検討
                return
            # または、特定の要素が存在するかで判断する (例)
            # WebDriverWait(self.driver, 5).until(
            #     EC.presence_of_element_located((By.XPATH, "//a[@data-testid='AppTabBar_Home_Link']"))
            # )
            # self.logger.info("既にTwitterにログイン済みです（ホームタブ確認）。ログイン処理をスキップします。")
            # return
        except TimeoutException:
            self.logger.info("ログインしていないようです。ログイン処理を開始します。")
        except WebDriverException as e:
            self.logger.warning(f"ログイン状態の確認中にWebDriverエラーが発生しました: {e}。ログイン処理を試みます。")

        if not self.username or not self.password:
            self.logger.error("❌ Twitterのユーザー名またはパスワードが設定されていません。")
            raise ValueError("Twitterの認証情報が不足しています。")

        self.logger.info(f"Twitterへのログインを開始します: {self.username}")
        self.driver.get("https://twitter.com/login")
        time.sleep(random.uniform(2, 4)) # ページ読み込み待ち

        # ログインページ表示直後のスクリーンショットを保存
        screenshot_path = os.path.join(self.screenshots_dir, f"login_page_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        try:
            self.driver.save_screenshot(screenshot_path)
            self.logger.info(f"ログインページのスクリーンショットを保存しました: {screenshot_path}")
        except Exception as e:
            self.logger.error(f"スクリーンショットの保存に失敗しました: {e}")

        try:
            username_input = WebDriverWait(self.driver, 20).until( # 待機時間を10秒から20秒に延長
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='text']"))
            )
            username_input.send_keys(self.username)
            self.logger.info(f"ユーザー名 {self.username} を入力しました。")

            next_button_xpath = "//span[contains(text(),'Next') or contains(text(),'次へ')]"
            next_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, next_button_xpath))
            )
            next_button.click()
            self.logger.info("「次へ」ボタンをクリックしました。")
            time.sleep(random.uniform(1.5, 3))

            password_input = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
            )
            password_input.send_keys(self.password)
            self.logger.info("パスワードを入力しました。")

            login_button_xpath = "//span[contains(text(),'Log in') or contains(text(),'ログイン')]"
            login_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, login_button_xpath))
            )
            login_button.click()
            self.logger.info("「ログイン」ボタンをクリックしました。")
            time.sleep(random.uniform(3, 5))

            if "home" in self.driver.current_url.lower():
                self.logger.info("✅ Twitterへのログインに成功しました！")
            else:
                self.logger.warning(f"⚠️ ログイン後のURLが予期したものではありません: {self.driver.current_url}")
                if self.email: 
                    try:
                        email_confirm_input_xpath = "//input[@name='text' and @type='text']"
                        email_confirm_input = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, email_confirm_input_xpath))
                        )
                        if email_confirm_input.is_displayed():
                            self.logger.info(f"追加の確認としてメールアドレス {self.email} の入力を試みます。")
                            email_confirm_input.send_keys(self.email)
                            next_button_after_email = WebDriverWait(self.driver, 20).until(
                                EC.element_to_be_clickable((By.XPATH, next_button_xpath))
                            )
                            next_button_after_email.click()
                            self.logger.info("メールアドレス入力後の「次へ」ボタンをクリックしました。")
                            time.sleep(random.uniform(3,5))
                            if "home" in self.driver.current_url.lower():
                                self.logger.info("✅ メールアドレスによる追加確認後、ログインに成功しました！")
                            else:
                                self.logger.error(f"❌ メールアドレス入力後もログインに失敗しました。現在のURL: {self.driver.current_url}")
                                raise Exception("ログインシーケンスの追加確認に失敗しました。")
                        else: # is_displayed が False の場合
                            self.logger.error("❌ メール確認入力フィールドが見つかりましたが、表示されていません。")
                            raise Exception("ログインシーケンスの追加確認(メール)要素非表示。")
                    except TimeoutException:
                        self.logger.error("❌ メール確認入力フィールドが見つかりませんでした（タイムアウト）。")
                        raise Exception("ログインシーケンスの追加確認(メール)要素タイムアウト。")
                    except Exception as e_confirm:
                        self.logger.error(f"❌ ログイン中のメール確認処理で予期せぬエラー: {e_confirm}")
                        raise # 元の例外を再送出
                else: # self.email がない場合
                    self.logger.error("❌ ログインに失敗しました（メールアドレス情報なし）。")
                    raise Exception("ログインシーケンス失敗、メール情報なし。")

        except TimeoutException as te:
            self.logger.error(f"❌ ログイン処理中にタイムアウトが発生しました: {te}", exc_info=True)
            self._save_dom_error_log(self.driver.page_source, "login_timeout")
            raise
        except Exception as e:
            self.logger.error(f"❌ ログイン処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
            self._save_dom_error_log(self.driver.page_source, "login_general_error")
            raise

    def extract_tweets(self, username, max_tweets, globally_processed_ids):
        if not self.driver:
            self.logger.error("❌ WebDriverが初期化されていません。ツイートを収集できません。")
            return []
        
        self.logger.info(f"ユーザー @{username} のツイート収集を開始します (最大 {max_tweets} 件)。")
        # 例: if self.bot_config.get('extraction_method') == 'api': 
        #    # (self.api_client が初期化されているか等のチェックも必要)
        #    return self.api_client.fetch_tweets_by_username_app_context(username, max_tweets)

        target_url = f"https://twitter.com/{username}"
        self.driver.get(target_url)
        self.logger.info(f"ページ {target_url} にアクセスしました。")
        time.sleep(random.uniform(4, 6)) # ページの読み込みを待つ時間を少し延長

        # プロフィールページ表示直後のスクリーンショットを保存
        profile_page_screenshot_path = os.path.join(self.screenshots_dir, f"profile_page_snapshot_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        try:
            self.driver.save_screenshot(profile_page_screenshot_path)
            self.logger.info(f"プロフィールページのスクリーンショットを保存しました: {profile_page_screenshot_path}")
        except Exception as e:
            self.logger.error(f"プロフィールページのスクリーンショットの保存に失敗しました: {e}")

        tweets_data = []
        tweet_ids_on_page = set()
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        consecutive_scroll_fails = 0

        self.temp_media_dir = os.path.join(os.path.dirname(__file__), "temp_media", datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(self.temp_media_dir, exist_ok=True)
        self.logger.info(f"一時メディア保存ディレクトリを作成: {self.temp_media_dir}")

        try:
            while len(tweets_data) < max_tweets:
                articles = self.driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
                if not articles:
                    self.logger.info("ツイート要素が見つかりません。ページの終端か、構造が変わった可能性があります。")
                    # DOMスナップショットを保存
                    self._save_dom_error_log(self.driver.page_source, f"no_tweets_found_{username}")
                    if self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Retry')]"): 
                        self.logger.warning("「再試行」ボタンが見つかりました。リフレッシュを試みます。")
                        self.driver.refresh()
                        time.sleep(random.uniform(3,5))
                        continue 
                    break 

                new_tweets_found_on_this_scroll = False
                for article in articles:
                    if len(tweets_data) >= max_tweets:
                        break
                    
                    try:
                        tweet_id = self.extract_tweet_id(article)
                        if not tweet_id:
                            self.logger.warning("ツイートIDが取得できませんでした。この要素をスキップします。")
                            continue

                        if tweet_id in tweet_ids_on_page or tweet_id in globally_processed_ids:
                            continue
                        
                        tweet_ids_on_page.add(tweet_id)
                        new_tweets_found_on_this_scroll = True

                        tweet_text_element = article.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
                        tweet_text = tweet_text_element.text if tweet_text_element else ""
                        
                        if self.is_ad_post(tweet_text):
                            self.logger.info(f"広告と思われるツイートをスキップ: {tweet_text[:50]}...")
                            continue

                        timestamp_element = article.find_element(By.XPATH, ".//time")
                        timestamp_str = timestamp_element.get_attribute("datetime") if timestamp_element else ""
                        
                        author_name = ""
                        author_username = ""
                        try: 
                            author_elements = article.find_elements(By.XPATH, ".//div[@data-testid='User-Name']//a")
                            if len(author_elements) >= 2: 
                                author_name = author_elements[0].text
                                author_username = author_elements[1].text.lstrip('@')
                        except Exception as e_author:
                            self.logger.warning(f"ツイート {tweet_id} の著者情報取得に失敗: {e_author}")

                        media_urls = []
                        media_elements = article.find_elements(By.XPATH, ".//div[@data-testid='tweetPhoto']//img | .//div[contains(@data-testid, 'videoPlayer')]")
                        
                        local_media_paths = [] 

                        for media_elem in media_elements:
                            media_type = "unknown"
                            media_src = None
                            if media_elem.tag_name == "img":
                                media_type = "photo"
                                media_src = media_elem.get_attribute("src")
                                if media_src and "format=jpg" in media_src: 
                                    media_src = media_src.split("&name=")[0] + "&name=large" 
                            elif "videoPlayer" in media_elem.get_attribute("data-testid"):
                                media_type = "video"
                                try:
                                    video_poster_img = media_elem.find_element(By.XPATH, ".//video")
                                    media_src = video_poster_img.get_attribute("poster") 
                                    if not media_src: 
                                        source_tag = media_elem.find_element(By.XPATH, ".//video/source")
                                        media_src = source_tag.get_attribute("src") 
                                        self.logger.warning(f"動画ソースがblob URLの可能性があります: {media_src}")
                                except NoSuchElementException:
                                    self.logger.warning(f"ツイート {tweet_id} の動画プレーヤーからメディアソースが見つかりません。")
                                
                            if media_src:
                                media_urls.append({"type": media_type, "url": media_src})
                                downloaded_path = self._download_media(media_src, tweet_id, media_type)
                                if downloaded_path:
                                    local_media_paths.append(downloaded_path)
                        
                        ocr_text_combined = ""
                        if self.bot_config.get("enable_ocr", False) and local_media_paths:
                            for img_path in local_media_paths:
                                if img_path.lower().endswith((".png", ".jpg", ".jpeg")): 
                                    try:
                                        ocr_result = self.ocr_image(img_path)
                                        if ocr_result:
                                            ocr_text_combined += ocr_result + "\n"
                                    except Exception as e_ocr:
                                        self.logger.error(f"画像 {img_path} のOCR処理中にエラー: {e_ocr}")
                            if ocr_text_combined:
                                self.logger.info(f"ツイート {tweet_id} のメディアからOCRテキストを取得: {ocr_text_combined[:50]}...")

                        tweet_data = {
                            "id": tweet_id,
                            "text": tweet_text,
                            "timestamp": timestamp_str,
                            "author_name": author_name,
                            "author_username": author_username,
                            "media_urls": media_urls, 
                            "local_media_paths": local_media_paths, 
                            "ocr_text": ocr_text_combined.strip() if ocr_text_combined else None,
                            "raw_html_element": article.get_attribute('outerHTML') 
                        }
                        tweets_data.append(tweet_data)
                        self.logger.info(f"収集済みツイート数: {len(tweets_data)} / {max_tweets}")

                    except StaleElementReferenceException:
                        self.logger.warning("StaleElementReferenceExceptionが発生。要素が再描画された可能性があります。リトライします。")
                        break 
                    except NoSuchElementException as nse:
                        self.logger.warning(f"ツイート要素の解析中にNoSuchElementException: {nse}。このツイートをスキップします。")
                        continue 
                    except Exception as e_article:
                        self.logger.error(f"記事要素の処理中に予期せぬエラー: {e_article}", exc_info=True)
                        continue 
                
                if not new_tweets_found_on_this_scroll and articles: 
                    self.logger.info("今回のスクロールでは新しいツイートは見つかりませんでした。")
                    consecutive_scroll_fails += 1
                    if consecutive_scroll_fails >= 3: 
                        self.logger.info("新しいツイートが連続して見つからないため、収集を終了します。")
                        break
                else:
                    consecutive_scroll_fails = 0 

                self.logger.debug("ページをスクロールします...")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4)) 

                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height: 
                    self.logger.info("ページの高さが変わりませんでした。これ以上スクロールできないか、コンテンツがありません。")
                    consecutive_scroll_fails +=1 
                    if consecutive_scroll_fails >=3:
                         self.logger.info("ページの高さが連続して変わらないため、収集を終了します。")
                         break
                else:
                    consecutive_scroll_fails = 0 
                last_height = new_height

        except Exception as e:
            self.logger.error(f"ツイート収集のメインループでエラーが発生しました: {e}", exc_info=True)
        finally:
            pass 

        self.logger.info(f"収集完了。合計 {len(tweets_data)} 件のツイートデータを取得しました。")
        return tweets_data

    def cleanup(self):
        if self.driver:
            quit_driver(self.driver)
            self.driver = None
            self.logger.info("WebDriverをクリーンアップしました。")

    def _save_dom_error_log(self, element_html, error_identifier):
        log_dir = os.path.join(os.path.dirname(__file__), "logs", "dom_errors")
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = os.path.join(log_dir, f"error_dom_{error_identifier}_{timestamp}.html")
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(element_html)
            self.logger.info(f"エラー発生時のDOMスナップショットを保存しました: {filename}")
        except Exception as e:
            self.logger.error(f"DOMスナップショットの保存に失敗: {e}")

    def extract_tweet_id(self, article_element):
        """<article>要素からツイートIDを抽出する。
        ツイートIDは通常、ツイートへのパーマリンクURLに含まれる最後の数値部分。
        例: /username/status/1234567890
        """
        try:
            links_with_status = article_element.find_elements(By.XPATH, ".//a[contains(@href, '/status/')]")
            for link_element in links_with_status:
                href = link_element.get_attribute("href")
                if href:
                    match = re.search(r"/status/(\d+)", href)
                    if match:
                        tweet_id = match.group(1)
                        return tweet_id
            self.logger.warning(f"記事要素内からツイートIDを含むリンクが見つかりませんでした。HTML: {article_element.get_attribute('outerHTML')[:500]}")
            return None
        except Exception as e:
            self.logger.error(f"ツイートIDの抽出中にエラー: {e}", exc_info=True)
            return None

    def ocr_image(self, image_path):
        if not os.path.exists(image_path):
            self.logger.error(f"OCR対象の画像ファイルが見つかりません: {image_path}")
            return None
        try:
            img = Image.open(image_path)
            img = img.convert('L')  
            img = img.filter(ImageFilter.MedianFilter()) 
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2) 
            text = pytesseract.image_to_string(img, lang='jpn+eng')
            self.logger.info(f"画像 {image_path} からOCRテキストを取得しました: {text[:50]}...")
            return text
        except FileNotFoundError: 
             self.logger.error("❌ Tesseract OCRエンジンが見つかりません。パスが通っているか確認してください。")
             return None
        except Exception as e:
            self.logger.error(f"画像 {image_path} のOCR処理中にエラー: {e}", exc_info=True)
            return None

    def is_ad_post(self, text):
        text_lower = text.lower()
        for keyword in AD_KEYWORDS:
            if keyword.lower() in text_lower:
                return True
        return False

    def _download_media(self, media_url, tweet_id, media_type="photo"):
        if not media_url:
            return None
        
        try:
            filename_base = f"{tweet_id}_{os.path.basename(media_url).split('?')[0]}"
            response_head = requests.head(media_url, timeout=10, allow_redirects=True)
            content_type = response_head.headers.get('Content-Type')
            extension = ".jpg" 
            if content_type:
                if "image/jpeg" in content_type: extension = ".jpg"
                elif "image/png" in content_type: extension = ".png"
                elif "image/gif" in content_type: extension = ".gif"
                elif "video/mp4" in content_type: extension = ".mp4"
            
            if not content_type or extension == ".jpg": 
                 url_path = media_url.split('?')[0]
                 if url_path.endswith(".png"): extension = ".png"
                 elif url_path.endswith(".gif"): extension = ".gif"
                 elif url_path.endswith(".mp4"): extension = ".mp4"

            filename = filename_base + extension
            local_filepath = os.path.join(self.temp_media_dir, filename)

            self.logger.info(f"メディアをダウンロード中: {media_url} -> {local_filepath}")
            response = requests.get(media_url, stream=True, timeout=20)
            response.raise_for_status()
            with open(local_filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            self.logger.info(f"メディアダウンロード完了: {local_filepath}")
            return local_filepath
        except requests.exceptions.RequestException as e:
            self.logger.error(f"メディアのダウンロードに失敗 ({media_url}): {e}")
            return None
        except Exception as e_dl:
            self.logger.error(f"メディアダウンロードの一般エラー ({media_url}): {e_dl}", exc_info=True)
            return None

    def _upload_to_drive_and_get_link(self, local_filepath, tweet_id):
        self.logger.warning("_upload_to_drive_and_get_link は compile_bot または NotionWriter での実装を検討してください。現在は使われていません。")
        return None