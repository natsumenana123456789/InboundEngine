import os
import sys
import re
# import cv2 # ocr_image 内で import numpy as np, cv2 されているので不要かも
import time
import json
# import shutil # 不要になる可能性
import requests # メディアダウンロードに使う場合は残す
# import pytesseract # ocr_utils に移管済み
# import logging # logger をコンストラクタで受け取るので不要
from datetime import datetime, timedelta, timezone # snscrape の日付処理で利用
from PIL import Image, ImageFilter, ImageEnhance # ocr_utils に移管済み
# from selenium import webdriver # 不要
# from selenium.webdriver.common.by import By # 不要
# from selenium.webdriver.common.keys import Keys # 不要
# from selenium.webdriver.chrome.options import Options # 不要
# from selenium.webdriver.support.ui import WebDriverWait # 不要
# from selenium.webdriver.support import expected_conditions as EC # 不要
# from selenium.common.exceptions import ( # 不要
# StaleElementReferenceException,
# NoSuchElementException,
# TimeoutException,
# ElementClickInterceptedException,
# WebDriverException
# )
# from googleapiclient.discovery import build # compile_bot へ
# from googleapiclient.http import MediaFileUpload # compile_bot へ
from typing import List, Dict, Optional, Tuple, Any

import snscrape.modules.twitter as sntwitter # snscrapeをインポート
from utils.webdriver_utils import get_driver, quit_driver

# プロジェクトルートをsys.pathに追加
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# from utils.webdriver_utils import get_driver, quit_driver # 不要
from utils.logger import setup_logger
# import random # 不要になる可能性
# from notion_client import Client # compile_bot へ
# from bs4 import BeautifulSoup # 不要
from config import config_loader
from bots.compile_bot.notion_compiler import NotionCompiler

# 広告除外キーワード (snscrapeでは直接使わないが、後処理で使う可能性があれば残す)
# AD_KEYWORDS = [
# "r10.to",
# "ふるさと納税",
#     # ... (その他キーワード)
# ]

class TweetExtractor:
    def __init__(self, bot_config: Dict[str, Any], parent_logger=None):
        self.config = bot_config
        # ログディレクトリ名を bots/extract_tweets_bot/logs/ のように変更することを推奨
        self.log_dir_name = self.config.get('log_dir_name', os.path.join('bots', 'extract_tweets_bot', 'logs')) 
        self.log_dir = os.path.join(PROJECT_ROOT, self.log_dir_name)
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.logger = parent_logger if parent_logger else setup_logger(log_dir_name=self.log_dir_name, logger_name='TweetExtractor_snscrape')
        self.logger.info("TweetExtractor (snscrape mode) initialized.")
        # Selenium関連の初期化はすべて削除
        # WebDriver設定なども不要

        # NotionCompilerの初期化
        self.notion_compiler = NotionCompiler(bot_config=self.config, parent_logger=self.logger)

    # login メソッドは不要
    # def login(self, target_username):
    #     """
    #     (このメソッドはAPI移行のためコメントアウトされています)
    #     if not self.driver:
    #         self.logger.error("❌ WebDriverが初期化されていません。ログインできません。")
    #         self._setup_driver()
    #         if not self.driver:
    #              raise RuntimeError("WebDriverのセットアップに失敗しました。")
    #     # ... (中略) ...
    #     """
    #     self.logger.warning(f"TweetExtractor.login はAPI移行のため呼び出されましたが、処理は実行されません。target_username: {target_username}")
    #     # APIクライアントは自身で認証をハンドリングするため、ここでのWebDriverを使ったログインは不要
    #     return

    # _setup_driver メソッドは不要
    # def _setup_driver(self):
    #     if self.driver:
    #         self.logger.info("WebDriverは既に初期化されています。")
    #         return
    #     try:
    #         self.driver = get_driver(user_agent=self.user_agent, profile_path=self.profile_path)
    #         self.logger.info("✅ WebDriverのセットアップが完了しました。")
    #     except Exception as e:
    #         self.logger.error(f"❌ WebDriverのセットアップ中にエラーが発生しました: {e}", exc_info=True)
    #         raise

    # cleanup メソッド (Selenium WebDriver 関連) は不要
    # def cleanup(self):
    #     if self.driver:
    #         quit_driver(self.driver)
    #         self.driver = None
    #         self.logger.info("WebDriverをクリーンアップしました。")

    def _save_dom_error_log(self, driver, error_identifier="error"):
        try:
            dom_path = os.path.join(self.log_dir, f"dom_{error_identifier}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(dom_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            self.logger.info(f"DOMを保存しました: {dom_path}")
        except Exception as e:
            self.logger.error(f"DOM保存中にエラー: {e}")

    # extract_tweet_id (Selenium要素から) は不要
    # def extract_tweet_id(self, article_element):
    #     # ... (中略) ...
    #     return None

    # ocr_image は ocr_utils に移管済み
    # def ocr_image(self, image_path):
    #     # ... (中略) ...
    #     return None

    # is_ad_post は必要ならテキストベースで判定ロジックを再実装。一旦コメントアウト。
    # def is_ad_post(self, text):
    #     text_lower = text.lower()
    #     for keyword in AD_KEYWORDS:
    #         if keyword.lower() in text_lower:
    #             return True
    #     return False

    # _download_media は main.py などで別途実装するか、このクラスの責務として残すか後で判断。一旦コメントアウト。
    # def _download_media(self, media_url, tweet_id, media_type="photo"):
    #     # ... (中略) ...
    #     return None

    # _upload_to_drive_and_get_link は compile_bot へ移管または削除。一旦コメントアウト。
    # def _upload_to_drive_and_get_link(self, local_filepath, tweet_id):
    #     self.logger.warning("_upload_to_drive_and_get_link は compile_bot または NotionWriter での実装を検討してください。現在は使われていません。")
    #     return None

    def extract_tweets(self, username: str, max_tweets: int, globally_processed_ids: set) -> List[Dict[str, Any]]:
        self.logger.info(f"ユーザー @{username} のツイート収集を開始します (snscrape, 最大 {max_tweets} 件)。")
        extracted_tweets_data = []
        
        try:
            # snscrapeの設定を調整
            scraper = sntwitter.TwitterUserScraper(
                username,
                proxies=None  # プロキシは使用しない
            )
            tweets_collected_count = 0
            
            # ツイート取得を試みる
            try:
                for i, tweet in enumerate(scraper.get_items()):
                    if max_tweets > 0 and tweets_collected_count >= max_tweets:
                        self.logger.info(f"指定された最大収集数 {max_tweets} 件に達しました。")
                        break

                    tweet_id = str(tweet.id)
                    if tweet_id in globally_processed_ids:
                        self.logger.debug(f"ツイート {tweet_id} は既に処理済みのためスキップします。")
                        continue

                    media_files_info = []
                    if tweet.media:
                        for medium in tweet.media:
                            media_info = {}
                            if isinstance(medium, sntwitter.Photo):
                                media_info['type'] = 'photo'
                                media_info['url'] = medium.fullUrl
                            elif isinstance(medium, sntwitter.Video):
                                media_info['type'] = 'video'
                                if medium.variants:
                                    media_info['url'] = medium.variants[0].url 
                                else:
                                    media_info['url'] = None
                            elif isinstance(medium, sntwitter.Gif):
                                media_info['type'] = 'gif'
                                if medium.variants:
                                    media_info['url'] = medium.variants[0].url
                                else:
                                    media_info['url'] = None
                            
                            if media_info and media_info.get('url'):
                                media_files_info.append(media_info)
                    
                    author_name = tweet.user.displayname if tweet.user else "Unknown Author"
                    author_username = tweet.user.username if tweet.user else "unknownuser"

                    tweet_data = {
                        "id": tweet_id,
                        "text": tweet.rawContent,
                        "timestamp": tweet.date.isoformat(),
                        "author_name": author_name,
                        "author_username": author_username,
                        "media_files": media_files_info,
                        "url": tweet.url,
                        "reply_count": tweet.replyCount,
                        "retweet_count": tweet.retweetCount,
                        "like_count": tweet.likeCount,
                        "quote_count": tweet.quoteCount,
                        "language": tweet.lang
                    }
                    extracted_tweets_data.append(tweet_data)
                    tweets_collected_count += 1
                    globally_processed_ids.add(tweet_id)
                    
                    if i % 50 == 0 and i > 0:
                        self.logger.info(f"{tweets_collected_count}件のツイート候補を処理しました...")
                        # 50件ごとに少し待機して、レート制限を回避
                        time.sleep(2)

            except Exception as e:
                self.logger.error(f"ツイート取得中にエラーが発生しました: {str(e)}", exc_info=True)
                # エラーが発生しても、これまでに取得したツイートは返す
                if extracted_tweets_data:
                    self.logger.info(f"エラーが発生しましたが、{len(extracted_tweets_data)}件のツイートを取得できました。")
                    return extracted_tweets_data
                raise  # ツイートが1件も取得できていない場合は例外を再送出

            self.logger.info(f"ユーザー @{username} から {tweets_collected_count} 件のツイート情報を収集完了。")

        except Exception as e:
            self.logger.error(f"❌ snscrapeでのツイート収集中にエラーが発生しました ({username}): {e}", exc_info=True)
            return []

        return extracted_tweets_data

    def extract_tweets_selenium(self, username: str, max_tweets: int, globally_processed_ids: set) -> List[Dict[str, Any]]:
        """
        Seleniumを使って指定ユーザーのツイートを取得する（安定性テスト用）
        """
        self.logger.info(f"[Selenium] ユーザー @{username} のツイート収集を開始します (最大 {max_tweets} 件)。")
        tweets_data = []
        driver = None
        try:
            # WebDriver初期化
            driver = get_driver()
            # Twitterログインページへ
            login_url = "https://twitter.com/i/flow/login"
            self.logger.info(f"ログインページにアクセス: {login_url}")
            driver.get(login_url)
            time.sleep(10)
            
            self.logger.info(f"現在のURL: {driver.current_url}")
            self.logger.info(f"ページタイトル: {driver.title}")
            screenshot_path = os.path.join(self.log_dir, f"login_page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            driver.save_screenshot(screenshot_path)
            self.logger.info(f"ログインページのスクリーンショットを保存: {screenshot_path}")
            
            twitter_config = self.config.get("twitter_account", {})
            username_val = twitter_config.get("username")
            password_val = twitter_config.get("password")
            email_val = twitter_config.get("email")
            phone_val = twitter_config.get("phone")
            
            if not username_val or not password_val:
                raise ValueError("Twitterアカウント情報が設定されていません。")
            
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.common.exceptions import TimeoutException, NoSuchElementException
                
                # ユーザー名入力欄を待機して取得
                username_selectors = [
                    "input[autocomplete='username']",
                    "input[name='text']",
                    "input[type='text']",
                    "input[data-testid='login-username']"
                ]
                username_input = None
                for selector in username_selectors:
                    try:
                        username_input = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if username_input.is_displayed() and username_input.is_enabled():
                            break
                    except:
                        continue
                if not username_input:
                    raise NoSuchElementException("ユーザー名入力欄が見つかりません")
                username_input.clear()
                username_input.send_keys(username_val)
                time.sleep(3)
                
                # 「次へ」ボタンを待機して取得
                next_button_selectors = [
                    "//button[.//span[contains(text(),'次へ') or contains(text(),'Next')]]",
                    "//div[@role='button'][.//span[contains(text(),'次へ') or contains(text(),'Next')]]",
                    "//button[@type='submit']",
                    "//div[@data-testid='login-next-button']"
                ]
                next_button = None
                for selector in next_button_selectors:
                    try:
                        next_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if next_button.is_displayed() and next_button.is_enabled():
                            break
                    except:
                        continue
                if not next_button:
                    raise NoSuchElementException("次へボタンが見つかりません")
                next_button.click()
                time.sleep(5)
                
                # 追加認証やパスワード入力の分岐処理
                for step in range(3):  # 最大3回まで追加入力を試みる
                    # まずパスワード欄を探す
                    password_input = None
                    password_selectors = [
                        "input[type='password']",
                        "input[name='password']",
                        "input[data-testid='login-password']"
                    ]
                    for selector in password_selectors:
                        try:
                            password_input = driver.find_element(By.CSS_SELECTOR, selector)
                            if password_input.is_displayed() and password_input.is_enabled():
                                break
                        except:
                            continue
                    if password_input:
                        break  # パスワード欄が見つかったらループを抜ける
                    # 追加認証（メール・電話番号等）
                    try:
                        add_input = driver.find_element(By.CSS_SELECTOR, "input[name='text']")
                        page_source = driver.page_source
                        if "電話番号またはメールアドレスを入力してください" in page_source or "Enter your phone number or email address" in page_source:
                            add_val = email_val or phone_val or username_val
                            self.logger.info(f"追加認証画面: email/phoneを入力します: {add_val}")
                            add_input.clear()
                            add_input.send_keys(add_val)
                        else:
                            add_input.clear()
                            add_input.send_keys(username_val)
                        time.sleep(1)
                        add_next_btn = None
                        for selector in next_button_selectors:
                            try:
                                add_next_btn = driver.find_element(By.XPATH, selector)
                                if add_next_btn.is_displayed() and add_next_btn.is_enabled():
                                    break
                            except:
                                continue
                        if add_next_btn:
                            add_next_btn.click()
                            time.sleep(3)
                            self.logger.info("追加認証情報を入力し、次へをクリックしました。")
                            self._save_dom_error_log(driver, f"add_auth_step{step+1}")
                        else:
                            self.logger.info("追加認証の次へボタンが見つかりませんでした。")
                            self._save_dom_error_log(driver, f"no_add_auth_next_btn_{step+1}")
                            break
                    except Exception:
                        self.logger.info("追加認証入力欄は見つかりませんでした。")
                        self._save_dom_error_log(driver, f"no_add_auth_step{step+1}")
                        break
                if not password_input:
                    raise NoSuchElementException("パスワード入力欄が見つかりません")
                password_input.clear()
                password_input.send_keys(password_val)
                time.sleep(3)
                # ログインボタンをクリック
                login_button_selectors = [
                    "//button[.//span[contains(text(),'ログイン') or contains(text(),'Log in')]]",
                    "//div[@role='button'][.//span[contains(text(),'ログイン') or contains(text(),'Log in')]]",
                    "//button[@type='submit']",
                    "//div[@data-testid='login-button']"
                ]
                login_button = None
                for selector in login_button_selectors:
                    try:
                        login_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if login_button.is_displayed() and login_button.is_enabled():
                            break
                    except:
                        continue
                if not login_button:
                    raise NoSuchElementException("ログインボタンが見つかりません")
                login_button.click()
                time.sleep(8)
                # ログイン成功確認
                success = False
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='primaryColumn']"))
                    )
                    success = True
                except TimeoutException:
                    try:
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='SideNav_AccountSwitcher_Button']"))
                        )
                        success = True
                    except TimeoutException:
                        pass
                if success:
                    self.logger.info("✅ ログインに成功しました")
                else:
                    self.logger.error("ログイン確認に失敗しました")
                    self._save_dom_error_log(driver, "login_failed")
                    raise TimeoutException("ログインの確認に失敗しました")
            except Exception as e:
                self.logger.error(f"ログイン処理中にエラー: {str(e)}")
                self._save_dom_error_log(driver, "login_error")
                raise
            profile_url = f"https://twitter.com/{username}"
            driver.get(profile_url)
            time.sleep(8)
            tweet_selector = "article[data-testid='tweet']"
            tweets = []
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, tweet_selector))
                )
                tweets = driver.find_elements(By.CSS_SELECTOR, tweet_selector)
            except TimeoutException:
                self.logger.error("ツイート要素の取得に失敗しました。")
                return []
            count = 0
            for tweet_elem in tweets:
                if count >= max_tweets:
                    break
                try:
                    tweet_id = tweet_elem.get_attribute("data-tweet-id") or ""
                    if tweet_id and tweet_id in globally_processed_ids:
                        continue
                    text_elem = tweet_elem.find_element(By.CSS_SELECTOR, "div[lang]")
                    tweet_text = text_elem.text
                    tweet_url = tweet_elem.find_element(By.CSS_SELECTOR, "a[href*='/status/']").get_attribute("href")
                    notion_data = {
                        "ツイートID": tweet_id or tweet_url.split("/")[-1],
                        "本文": tweet_text,
                        "ツイートURL": tweet_url,
                        "投稿者": username,
                        "投稿日時": datetime.now().isoformat(),
                        "ステータス": "新規"
                    }
                    if self.notion_compiler.is_client_initialized():
                        self.notion_compiler.add_compiled_item(notion_data)
                        self.logger.info(f"[Notion] ツイート {tweet_id} を保存しました。")
                    tweets_data.append({
                        "id": tweet_id or tweet_url.split("/")[-1],
                        "text": tweet_text,
                        "url": tweet_url
                    })
                    count += 1
                except Exception as e:
                    self.logger.warning(f"ツイート要素のパース中にエラー: {e}")
            self.logger.info(f"[Selenium] {len(tweets_data)}件のツイートを取得しました。")
        except Exception as e:
            self.logger.error(f"[Selenium] ツイート取得中にエラー: {e}", exc_info=True)
        finally:
            if driver:
                quit_driver(driver)
        return tweets_data

# 簡易テスト用 (必要に応じて)
if __name__ == '__main__':
    import logging # test_logger 用
    # loggerの設定
    test_logger = setup_logger(log_dir_name='logs/test_extract_tweets_bot_logs', logger_name='TestTweetExtractorSnscrape', level=logging.DEBUG)

    # config_loaderからbot_configを取得（twitter_account情報も含める）
    from config import config_loader
    bot_config = config_loader.get_bot_config("extract_tweets_bot")
    if not bot_config:
        bot_config = config_loader.get_bot_config("curate_bot")
    if not bot_config:
        test_logger.error("extract_tweets_bot/curate_botの設定が見つかりません。テストを中止します。")
        exit(1)

    extractor = TweetExtractor(bot_config=bot_config, parent_logger=test_logger)

    target_user = "pug_pua"
    max_to_extract = 3
    processed_ids = set()

    test_logger.info(f"--- [Selenium] Testing extract_tweets_selenium for @{target_user} (max: {max_to_extract}) ---")
    tweets = extractor.extract_tweets_selenium(target_user, max_to_extract, processed_ids)

    if tweets:
        test_logger.info(f"[Selenium] Successfully extracted {len(tweets)} tweets:")
        for i, tw_data in enumerate(tweets):
            test_logger.info(f"Tweet {i+1}: ID={tw_data.get('id')}, Text='{tw_data.get('text', '')[:50]}...', URL={tw_data.get('url')}")
    else:
        test_logger.info(f"[Selenium] No tweets extracted for @{target_user}.")

    test_logger.info("--- [Selenium] Test complete ---")