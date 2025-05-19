import os
import re
import cv2
import time
import json
import shutil
import argparse
import traceback
import requests
import subprocess
import shutil
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
)
from notion_client import Client
from datetime import datetime

# ✅ 広告除外、RT/引用RTルール、投稿ID補完付き
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


def normalize_text(text):
    return text.strip()


def login(driver, target=None):
    if os.path.exists("twitter_cookies.json"):
        print("✅ Cookieセッション検出 → ログインスキップ")
        print("🌐 https://twitter.com にアクセスしてクッキー読み込み中…")
        driver.get("https://twitter.com/")
        driver.delete_all_cookies()
        with open("twitter_cookies.json", "r") as f:
            cookies = json.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
        driver.get(f"https://twitter.com/{target or TWITTER_USERNAME}")
        return

    print("🔐 初回ログイン処理を開始")
    driver.get("https://twitter.com/i/flow/login")
    email_input = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.NAME, "text"))
    )
    email_input.send_keys(TWITTER_EMAIL)
    email_input.send_keys(Keys.ENTER)
    time.sleep(2)

    try:
        username_input = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.NAME, "text"))
        )
        username_input.send_keys(TWITTER_USERNAME)
        username_input.send_keys(Keys.ENTER)
        time.sleep(2)
    except Exception:
        print("👤 ユーザー名入力スキップ")

    password_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.NAME, "password"))
    )
    password_input.send_keys(TWITTER_PASSWORD)
    password_input.send_keys(Keys.ENTER)
    time.sleep(6)

    cookies = driver.get_cookies()
    with open("twitter_cookies.json", "w") as f:
        json.dump(cookies, f)
    print("✅ ログイン成功 → 投稿者ページに遷移")
    driver.get(f"https://twitter.com/{EXTRACT_TARGET}")


def setup_driver():
    options = Options()
    # options.add_argument("--headless=new")  ← この行をコメントアウト
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=ja-JP")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(options=options)


def extract_tweet_id(article):
    href_els = article.find_elements(By.XPATH, ".//a[contains(@href, '/status/')]")
    for el in href_els:
        h = el.get_attribute("href")
        m = re.search(r"/status/(\d+)", h or "")
        if m:
            return m.group(1)
    return None


def ocr_image(image_path):
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
        print(f"📝 OCR画像({image_path})結果:\n{text.strip()}")
        if not text.strip() or sum(c.isalnum() for c in text) < 3:
            print(f"⚠️ OCR画像({image_path})で文字化けまたは認識失敗の可能性")
        return text.strip()
    except Exception as e:
        print(f"OCR失敗({image_path}): {e}")
        return "[OCRエラー]"


def extract_self_replies(driver, username):
    replies = []
    cell_divs = driver.find_elements(By.XPATH, "//div[@data-testid='cellInnerDiv']")

    def get_transform_y(cell):
        style = cell.get_attribute("style") or ""
        m = re.search(r"translateY\(([\d\.]+)px\)", style)
        return float(m.group(1)) if m else 0

    cell_divs = sorted(cell_divs, key=get_transform_y)

    for cell in cell_divs:
        texts = []
        for tag in ["span", "h2"]:
            for el in cell.find_elements(By.XPATH, f".//{tag}"):
                t = (
                    el.text.strip()
                    .replace("\u200b", "")
                    .replace("\n", "")
                    .replace(" ", "")
                )
                if t:
                    texts.append(t)
        if any("もっと見つける" in t for t in texts):
            print("🔝 extract_self_replies: もっと見つける以降のリプライを除外")
            break

        articles = cell.find_elements(By.XPATH, ".//article[@data-testid='tweet']")

        def is_quote_reply(article):
            quote_els = article.find_elements(
                By.XPATH,
                ".//*[contains(text(), '引用')] | .//*[contains(text(), 'Quote')]",
            )
            quote_struct = article.find_elements(
                By.XPATH, ".//div[contains(@aria-label, '引用')]"
            )
            return bool(quote_els or quote_struct)

        for article in articles:
            try:
                handle_el = article.find_element(
                    By.XPATH,
                    ".//div[@data-testid='User-Name']//span[contains(text(), '@')]",
                )
                handle = handle_el.text.strip()
                if handle.replace("@", "") != username:
                    continue

                if is_quote_reply(article):
                    print("⚠️ extract_self_replies: 引用RT形式のためスキップ")
                    continue

                text_el = article.find_element(
                    By.XPATH, ".//div[@data-testid='tweetText']"
                )
                reply_text = text_el.text.strip() if text_el and text_el.text else ""

                tweet_id = extract_tweet_id(article)
                if not tweet_id:
                    print("⚠️ extract_self_replies: tweet_idが取得できないためスキップ")
                    continue

                # 画像・動画情報も取得
                images = [
                    img.get_attribute("src")
                    for img in article.find_elements(
                        By.XPATH,
                        ".//img[contains(@src, 'twimg.com/media') or contains(@src, 'twimg.com/card_img')]",
                    )
                    if img.get_attribute("src")
                ]
                video_posters = [
                    v.get_attribute("poster")
                    for v in article.find_elements(By.XPATH, ".//video")
                    if v.get_attribute("poster")
                ]

                if reply_text:
                    replies.append(
                        {
                            "id": tweet_id,
                            "text": reply_text,
                            "images": images,
                            "video_posters": video_posters,
                        }
                    )
            except Exception as e:
                print(f"⚠️ リプライ抽出エラー: {e}")
                continue
    return replies


def is_ad_post(text):
    lowered = text.lower()
    return any(k.lower() in lowered for k in AD_KEYWORDS)


def extract_thread_from_detail_page(driver, tweet_url):
    """
    スレッド詳細ページからすべての投稿を抽出する
    引数のtweet_urlから各投稿のURLも設定する
    """
    print(f"\n🕵️ 投稿アクセス中: {tweet_url}")
    driver.get(tweet_url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//article[@data-testid='tweet']")
            )
        )
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//article[@data-testid='tweet']//time[@datetime]")
            )
        )
    except Exception as e:
        print(f"⚠️ 投稿記事またはタイムスタンプの取得に失敗: {e}")
        return []

    if (
        "Something went wrong" in driver.page_source
        or "このページは存在しません" in driver.page_source
    ):
        print(f"❌ 投稿ページが読み込めませんでした: {tweet_url}")
        return []

    def get_transform_y(cell):
        style = cell.get_attribute("style") or ""
        m = re.search(r"translateY\(([\d\.]+)px\)", style)
        return float(m.group(1)) if m else 0

    tweet_blocks = []
    current_id_from_url = re.sub(r"\D", "", tweet_url.split("/")[-1])

    cell_divs = driver.find_elements(By.XPATH, "//div[@data-testid='cellInnerDiv']")
    print(f"cellInnerDiv数: {len(cell_divs)}")
    cell_divs = sorted(cell_divs, key=get_transform_y)

    found_other_user_reply_in_thread = False
    found_show_more_separator = False
    for cell_idx, cell in enumerate(cell_divs):
        if found_other_user_reply_in_thread:
            print(
                f"DEBUG extract_thread_from_detail_page: 他ユーザーのリプライを検出したため、以降のcell処理を中断。"
            )
            break
        if found_show_more_separator:
            print(
                f"DEBUG extract_thread_from_detail_page: 'もっと見つける' セパレータが検出されたため、以降のcell処理を中断。"
            )
            break

        try:
            show_more_elements = cell.find_elements(
                By.XPATH, ".//h2//span[text()='もっと見つける']"
            )
            is_show_more_cell = False
            if show_more_elements:
                for el in show_more_elements:
                    if el.is_displayed():
                        is_show_more_cell = True
                        break

            if is_show_more_cell:
                print(
                    f"DEBUG extract_thread_from_detail_page: 'もっと見つける' cell を検出 (cell {cell_idx})。このcellをスキップし、次回以降のcell処理を中断します。"
                )
                found_show_more_separator = True
                continue
        except Exception:
            pass

        articles_in_cell = cell.find_elements(
            By.XPATH, ".//article[@data-testid='tweet']"
        )
        if not articles_in_cell:
            continue

        for article_idx, article in enumerate(articles_in_cell):
            if found_other_user_reply_in_thread:
                break

            tweet_id = None
            username = ""
            try:
                time_links = article.find_elements(
                    By.XPATH, ".//a[.//time[@datetime] and contains(@href, '/status/')]"
                )
                if time_links:
                    href = time_links[0].get_attribute("href")
                    match = re.search(r"/status/(\d{10,})", href)
                    if match:
                        tweet_id = match.group(1)

                if not tweet_id:  # フォールバック
                    all_status_links = article.find_elements(
                        By.XPATH, ".//a[contains(@href, '/status/')]"
                    )
                    if all_status_links:
                        for link_el in all_status_links:
                            href = link_el.get_attribute("href")
                            if href:
                                match = re.search(r"/status/(\d{10,})", href)
                                if match:
                                    tweet_id = match.group(1)
                                    break
                    if not tweet_id:
                        # print(f"DEBUG: tweet_id が見つからないため、このarticleをスキップ (cell {cell_idx}, article {article_idx})")
                        continue

                try:
                    username_el = article.find_element(
                        By.XPATH,
                        ".//div[@data-testid='User-Name']//span[contains(text(), '@')]",
                    )
                    username = username_el.text.replace("@", "").strip()
                except NoSuchElementException:
                    # print(f"DEBUG: username が見つからないため、このarticleをスキップ (ID: {tweet_id})")
                    continue

                if not username:
                    # print(f"DEBUG: username が空のため、このarticleをスキップ (ID: {tweet_id})")
                    continue

                if username.lower() != EXTRACT_TARGET.lower():
                    if tweet_id != current_id_from_url:
                        found_other_user_reply_in_thread = True
                        break

                text = ""
                try:
                    tweet_text_element = article.find_element(
                        By.XPATH, ".//div[@data-testid='tweetText']"
                    )
                    text_content = driver.execute_script(
                        "return arguments[0].innerText;", tweet_text_element
                    )
                    text = text_content.strip() if text_content else ""
                except NoSuchElementException:
                    text = ""
                except Exception as e_text:
                    print(
                        f"⚠️ 本文抽出エラー (ID: {tweet_id}): {type(e_text).__name__} - {e_text}"
                    )
                    text = ""

                is_quote_tweet = False
                active_xpath_for_log = "N/A"

                possible_quote_xpaths_for_wait = [
                    ".//div[@data-testid='tweetQuote']",
                    ".//div[contains(@class, 'r-9aw3ui') and .//div[@role='link']]",  # articleネストなしも考慮
                    ".//div[@aria-labelledby and ./div[@role='link']]",  # articleネストなしも考慮
                ]
                found_by_wait = False
                wait_time_for_quote = 0.75
                for idx_wait, pq_xpath_wait in enumerate(
                    possible_quote_xpaths_for_wait
                ):
                    try:
                        WebDriverWait(article, wait_time_for_quote).until(
                            EC.presence_of_element_located((By.XPATH, pq_xpath_wait))
                        )
                        found_by_wait = True
                        break
                    except:
                        pass

                try:
                    # 優先度1: data-testid="tweetQuote"
                    xpath_testid = ".//div[@data-testid='tweetQuote']"
                    quote_elements_testid = article.find_elements(
                        By.XPATH, xpath_testid
                    )
                    if quote_elements_testid:
                        is_quote_tweet = True
                        # ネストされたarticleがあるかどうかもログには残す
                        if quote_elements_testid[0].find_elements(
                            By.XPATH, ".//article[@data-testid='tweet']"
                        ):
                            active_xpath_for_log = (
                                xpath_testid + " (with nested article)"
                            )
                            print(
                                f"DEBUG is_quote_tweet check (ID: {tweet_id}): Found quote by testid (with nested article): '{active_xpath_for_log}'"
                            )
                        else:
                            active_xpath_for_log = xpath_testid + " (container only)"
                            print(
                                f"DEBUG is_quote_tweet check (ID: {tweet_id}): Found quote by testid (container only): '{active_xpath_for_log}'"
                            )
                    else:
                        print(
                            f"DEBUG is_quote_tweet check (ID: {tweet_id}): No elements found for XPath (testid): '{xpath_testid}'."
                        )

                    # 優先度1.6: 特定のクラスパターンと構造 (ID非依存)
                    if not is_quote_tweet:
                        # クラス 'r-9aw3ui' および 'r-1s2bzr4' を持ち、aria-labelledby 属性を持ち、
                        # かつ子要素に role='link' を持つ (その中にarticleがあるかは問わない)
                        xpath_class_aria_child_link = ".//div[contains(@class, 'r-9aw3ui') and contains(@class, 'r-1s2bzr4') and @aria-labelledby and ./div[@role='link']]"
                        quote_elements_class_aria_child_link = article.find_elements(
                            By.XPATH, xpath_class_aria_child_link
                        )
                        if quote_elements_class_aria_child_link:
                            is_quote_tweet = True
                            active_xpath_for_log = xpath_class_aria_child_link
                            print(
                                f"DEBUG is_quote_tweet check (ID: {tweet_id}): Found quote by class 'r-9aw3ui', 'r-1s2bzr4', aria-labelledby and child div[@role='link']: '{active_xpath_for_log}'"
                            )
                        else:
                            print(
                                f"DEBUG is_quote_tweet check (ID: {tweet_id}): No elements for XPath (class 'r-9aw3ui', 'r-1s2bzr4', aria, child div[@role='link']): '{xpath_class_aria_child_link}'"
                            )

                            # フォールバック: 元のネストされたarticleを期待するロジック
                            xpath_class_aria_structure = ".//div[contains(@class, 'r-9aw3ui') and contains(@class, 'r-1s2bzr4') and @aria-labelledby and ./div[@role='link' and .//article[@data-testid='tweet']]]"
                            quote_elements_class_aria = article.find_elements(
                                By.XPATH, xpath_class_aria_structure
                            )
                            if quote_elements_class_aria:
                                is_quote_tweet = True
                                active_xpath_for_log = xpath_class_aria_structure
                                print(
                                    f"DEBUG is_quote_tweet check (ID: {tweet_id}): Found quote by class 'r-9aw3ui', 'r-1s2bzr4', aria-labelledby and structure (nested article): '{active_xpath_for_log}'"
                                )
                            else:
                                print(
                                    f"DEBUG is_quote_tweet check (ID: {tweet_id}): No elements for XPath (class 'r-9aw3ui', aria, structure with nested article): '{xpath_class_aria_structure}'"
                                )

                                # フォールバック1: aria-labelledby の条件を除いたクラスと子div[@role='link']
                                xpath_class_child_link_only = ".//div[contains(@class, 'r-9aw3ui') and contains(@class, 'r-1s2bzr4') and ./div[@role='link']]"
                                quote_elements_class_child_link = article.find_elements(
                                    By.XPATH, xpath_class_child_link_only
                                )
                                if quote_elements_class_child_link:
                                    is_quote_tweet = True
                                    active_xpath_for_log = xpath_class_child_link_only
                                    print(
                                        f"DEBUG is_quote_tweet check (ID: {tweet_id}): Found quote by class 'r-9aw3ui', 'r-1s2bzr4' and child div[@role='link'] (no aria check): '{active_xpath_for_log}'"
                                    )
                                else:
                                    print(
                                        f"DEBUG is_quote_tweet check (ID: {tweet_id}): No elements for XPath (class 'r-9aw3ui', child div[@role='link'], no aria): '{xpath_class_child_link_only}'"
                                    )

                                    # フォールバック2: 主要クラス 'r-9aw3ui' と子div[@role='link']
                                    xpath_main_class_child_link = ".//div[contains(@class, 'r-9aw3ui') and ./div[@role='link']]"
                                    quote_elements_main_class_child_link = (
                                        article.find_elements(
                                            By.XPATH, xpath_main_class_child_link
                                        )
                                    )
                                    if quote_elements_main_class_child_link:
                                        is_quote_tweet = True
                                        active_xpath_for_log = (
                                            xpath_main_class_child_link
                                        )
                                        print(
                                            f"DEBUG is_quote_tweet check (ID: {tweet_id}): Found quote by main class 'r-9aw3ui' and child div[@role='link']: '{active_xpath_for_log}'"
                                        )
                                    else:
                                        print(
                                            f"DEBUG is_quote_tweet check (ID: {tweet_id}): No elements for XPath (main class 'r-9aw3ui' and child div[@role='link']): '{xpath_main_class_child_link}'"
                                        )

                    # 優先度2: aria-labelledby を持つ要素 (ID非依存のまま)
                    if not is_quote_tweet:
                        # 修正: ./div[@role='link'] の中の article の存在を必須としない
                        xpath_aria_child_link = "./descendant::div[@aria-labelledby and ./div[@role='link']]"
                        quote_elements_aria_child_link = article.find_elements(
                            By.XPATH, xpath_aria_child_link
                        )
                        if quote_elements_aria_child_link:
                            is_quote_tweet = True
                            active_xpath_for_log = xpath_aria_child_link
                            print(
                                f"DEBUG is_quote_tweet check (ID: {tweet_id}): Found quote by aria-labelledby and child div[@role='link']: '{active_xpath_for_log}'"
                            )
                        else:
                            print(
                                f"DEBUG is_quote_tweet check (ID: {tweet_id}): No elements for XPath (aria-labelledby and child div[@role='link']): '{xpath_aria_child_link}'"
                            )
                            # 元のネストされたarticleを期待するロジックもフォールバックとして試す
                            xpath_aria_original_nested_article = "./descendant::div[@aria-labelledby][.//article[@data-testid='tweet']]"
                            quote_elements_aria_original_nested = article.find_elements(
                                By.XPATH, xpath_aria_original_nested_article
                            )
                            if quote_elements_aria_original_nested:
                                is_quote_tweet = True
                                active_xpath_for_log = (
                                    xpath_aria_original_nested_article
                                    + " (original logic with nested article)"
                                )
                                print(
                                    f"DEBUG is_quote_tweet check (ID: {tweet_id}): Found quote by original aria-labelledby logic (with nested article): '{active_xpath_for_log}'"
                                )
                            else:
                                print(
                                    f"DEBUG is_quote_tweet check (ID: {tweet_id}): No elements found for XPath (aria-labelledby with nested article): '{xpath_aria_original_nested_article}'"
                                )

                    # 優先度3: 構造ベースのフォールバック (引用テキストとリンク構造)
                    if not is_quote_tweet:
                        # 引用テキストの存在と、リンク構造（中にarticleがなくても良い）
                        xpath_structural_text_and_link = "./descendant::div[(div[normalize-space(text())='引用' or normalize-space(text())='Quote' or .//span[normalize-space(text())='引用' or normalize-space(text())='Quote']]) and div[@role='link']]"
                        quote_elements_structural_text_link = article.find_elements(
                            By.XPATH, xpath_structural_text_and_link
                        )
                        if quote_elements_structural_text_link:
                            is_quote_tweet = True
                            active_xpath_for_log = xpath_structural_text_and_link
                            print(
                                f"DEBUG is_quote_tweet check (ID: {tweet_id}): Found quote by structural fallback (text and link): '{active_xpath_for_log}'"
                            )
                        else:
                            print(
                                f"DEBUG is_quote_tweet check (ID: {tweet_id}): No elements found for XPath (structural fallback text and link): '{xpath_structural_text_and_link}'"
                            )
                            # 元のネストされたarticleを期待する構造ベースのフォールバック
                            xpath_structural_nested_article = "./descendant::div[div[normalize-space(text())='引用' or normalize-space(text())='Quote' or .//span[normalize-space(text())='引用' or normalize-space(text())='Quote']] and div[@role='link' and .//article[@data-testid='tweet']]]"
                            quote_elements_structural_nested = article.find_elements(
                                By.XPATH, xpath_structural_nested_article
                            )
                            if quote_elements_structural_nested:
                                is_quote_tweet = True
                                active_xpath_for_log = xpath_structural_nested_article
                                print(
                                    f"DEBUG is_quote_tweet check (ID: {tweet_id}): Found quote by structural fallback (with nested article): '{active_xpath_for_log}'"
                                )
                            else:
                                print(
                                    f"DEBUG is_quote_tweet check (ID: {tweet_id}): No elements found for XPath (structural fallback with nested article): '{xpath_structural_nested_article}'"
                                )

                    # Specific ID debug logging
                    # if (
                    #     tweet_id == "SPECIFIC_ID_TO_DEBUG"
                    # ) and not is_quote_tweet:
                    #     print(
                    #         f"DEBUG Article innerHTML for {tweet_id} (is_quote_tweet is False after all checks):"
                    #     )
                    #     try:
                    #         inner_html_debug = article.get_attribute("innerHTML")
                    #         print(
                    #             inner_html_debug[:1000] + "..."
                    #             if len(inner_html_debug) > 1000
                    #             else inner_html_debug
                    #         )
                    #     except Exception as e_html_debug_inner:
                    #         print(
                    #             f"DEBUG: Error getting innerHTML for {tweet_id}: {e_html_debug_inner}"
                    #         )

                    print(
                        f"DEBUG is_quote_tweet check (ID: {tweet_id}): Final decision. is_quote_tweet set to {is_quote_tweet} using XPath: '{active_xpath_for_log}'"
                    )

                except NoSuchElementException:
                    print(
                        f"DEBUG is_quote_tweet check (ID: {tweet_id}): NoSuchElementException during quote check."
                    )
                except Exception as e_quote_check_outer:
                    print(
                        f"⚠️ is_quote_tweet check outer error (ID: {tweet_id}): {type(e_quote_check_outer).__name__} - {e_quote_check_outer}"
                    )

                images = []
                video_posters = []

                all_possible_image_elements = article.find_elements(
                    By.XPATH,
                    ".//div[@data-testid='tweetPhoto']//img[contains(@src, 'twimg.com/media')] | .//div[contains(@data-testid, 'card.layout')]//img[contains(@src, 'twimg.com/card_img')]",
                )
                all_possible_video_elements = article.find_elements(
                    By.XPATH,
                    ".//div[(@data-testid='videoPlayer' or @data-testid='videoComponent' or @data-testid='communitynotesVideo')]//video[@poster]",
                )

                quote_container_element_for_media_check = None
                if is_quote_tweet and active_xpath_for_log != "N/A":
                    try:
                        found_qc = article.find_elements(By.XPATH, active_xpath_for_log)
                        if found_qc:
                            quote_container_element_for_media_check = found_qc[0]
                        else:  # active_xpath_for_log で見つからなかった場合のフォールバック
                            quote_container_xpaths_fallback_media = [
                                ".//div[@data-testid='tweetQuote']",
                                ".//div[contains(@class, 'r-9aw3ui') and @aria-labelledby and ./div[@role='link']]",
                                ".//div[@aria-labelledby and ./div[@role='link']]",
                            ]
                            for (
                                qc_xpath_fb_media
                            ) in quote_container_xpaths_fallback_media:
                                found_qc_fb_media = article.find_elements(
                                    By.XPATH, qc_xpath_fb_media
                                )
                                if found_qc_fb_media:
                                    quote_container_element_for_media_check = (
                                        found_qc_fb_media[0]
                                    )
                                    print(
                                        f"DEBUG Media Check: Used fallback XPath '{qc_xpath_fb_media}' to find quote container for media exclusion."
                                    )
                                    break
                        if not quote_container_element_for_media_check:
                            print(
                                f"DEBUG Media Check: Could not find quote container using active_xpath_for_log ('{active_xpath_for_log}') or fallbacks for media exclusion."
                            )

                    except Exception as e_qc_find:
                        print(
                            f"DEBUG Media Check: Error finding quote container for exclusion using '{active_xpath_for_log}': {e_qc_find}"
                        )

                for img_el in all_possible_image_elements:
                    try:
                        src = img_el.get_attribute("src")
                        if not src:
                            continue

                        is_inside_quote = False
                        if quote_container_element_for_media_check:
                            try:
                                # img_el が quote_container_element_for_media_check の子孫要素であるかを確認
                                # XPathで直接の子孫を探す
                                if quote_container_element_for_media_check.find_elements(
                                    By.XPATH, f".//img[@src='{src}']"
                                ):
                                    is_inside_quote = True
                            except NoSuchElementException:
                                pass
                            except StaleElementReferenceException:
                                print(
                                    f"DEBUG Media Check: Stale quote_container_element_for_media_check for image {src}"
                                )
                                pass

                        if not is_inside_quote:
                            if src not in images:
                                images.append(src)
                    except StaleElementReferenceException:
                        continue
                    except Exception:
                        continue

                for v_el in all_possible_video_elements:
                    try:
                        poster_url = v_el.get_attribute("poster")
                        if not poster_url:
                            continue

                        is_inside_quote_video = False
                        if quote_container_element_for_media_check:
                            try:
                                if quote_container_element_for_media_check.find_elements(
                                    By.XPATH, f".//video[@poster='{poster_url}']"
                                ):
                                    is_inside_quote_video = True
                            except NoSuchElementException:
                                pass
                            except StaleElementReferenceException:
                                print(
                                    f"DEBUG Media Check: Stale quote_container_element_for_media_check for video {poster_url}"
                                )
                                pass

                        if not is_inside_quote_video:
                            if not any(
                                vp.endswith(poster_url.split("/")[-1].split("?")[0])
                                for vp in video_posters
                            ):
                                poster_filename = f"video_poster_{tweet_id}_{len(video_posters)}_{poster_url.split('/')[-1].split('?')[0]}"
                                temp_poster_dir = "temp_posters"
                                if not os.path.exists(temp_poster_dir):
                                    os.makedirs(temp_poster_dir)
                                poster_path = os.path.join(
                                    temp_poster_dir, poster_filename
                                )
                                try:
                                    resp = requests.get(
                                        poster_url, stream=True, timeout=10
                                    )
                                    resp.raise_for_status()
                                    with open(poster_path, "wb") as f_poster:
                                        for chunk in resp.iter_content(1024):
                                            f_poster.write(chunk)
                                    video_posters.append(poster_path)
                                except (
                                    requests.exceptions.RequestException
                                ) as e_poster_dl:
                                    print(
                                        f"❌ poster画像ダウンロード失敗 (ID: {tweet_id}, URL: {poster_url}): {e_poster_dl}"
                                    )
                                except Exception as e_poster_save:
                                    print(
                                        f"❌ poster画像保存失敗 (ID: {tweet_id}): {e_poster_save}"
                                    )
                    except StaleElementReferenceException:
                        continue
                    except Exception:
                        continue

                time_els = article.find_elements(By.XPATH, ".//time[@datetime]")
                date_str = time_els[0].get_attribute("datetime") if time_els else None
                if not date_str:
                    time_links_for_date = article.find_elements(
                        By.XPATH, ".//a[.//time[@datetime]]"
                    )
                    if time_links_for_date:
                        try:
                            date_str = (
                                time_links_for_date[0]
                                .find_element(By.XPATH, ".//time")
                                .get_attribute("datetime")
                            )
                        except:
                            pass

                text_length = len(text)
                has_media = bool(images or video_posters)
                print(
                    f"DEBUG has_media check: ID {tweet_id}, user: {username}, images: {len(images)}, posters: {len(video_posters)}, has_media: {has_media}, is_quote: {is_quote_tweet}"
                )

                tweet_blocks.append(
                    {
                        "article_element": article,
                        "text": text,
                        "date": date_str,
                        "id": tweet_id,
                        "username": username,
                        "images": images,
                        "video_posters": video_posters,
                        "is_quote_tweet": is_quote_tweet,
                        "text_length": text_length,
                        "has_media": has_media,
                    }
                )

            except StaleElementReferenceException:
                print(
                    f"⚠️ StaleElementReferenceException発生、このarticle処理をスキップ (cell {cell_idx}, article {article_idx})"
                )
                break
            except Exception as e_article_process:
                print(
                    f"⚠️ 詳細ページ内記事処理中エラー: {type(e_article_process).__name__} - {e_article_process} (ID: {tweet_id if 'tweet_id' in locals() and tweet_id else '不明'})"
                )
                continue

        if found_other_user_reply_in_thread:
            break

    def remove_temp_posters_from_list(blocks_to_clean):
        for block in blocks_to_clean:
            for poster_p in block.get("video_posters", []):
                if (
                    isinstance(poster_p, str)
                    and os.path.exists(poster_p)
                    and "temp_posters" in poster_p
                ):
                    try:
                        os.remove(poster_p)
                    except Exception as e_remove:
                        print(
                            f"⚠️ (cleanup) 一時ポスター削除失敗: {poster_p}, error: {e_remove}"
                        )

    if not tweet_blocks:
        print(f"⚠️ 有効な投稿ブロックが抽出されませんでした。 (URL: {tweet_url})")
        return []

    initial_post_data = None
    for block in tweet_blocks:
        if block["id"] == current_id_from_url:
            initial_post_data = block
            break

    if not initial_post_data:
        print(
            f"⚠️ URL指定の投稿({current_id_from_url})が抽出ブロック内に見つかりません。"
        )
        remove_temp_posters_from_list(tweet_blocks)
        return []

    if initial_post_data["username"].lower() != EXTRACT_TARGET.lower():
        print(
            f"ℹ️ URL指定の投稿({current_id_from_url})のユーザー(@{initial_post_data['username']})が対象({EXTRACT_TARGET})と異なりますが、起点なので処理は継続します。"
        )

    final_results = []
    for block_item in tweet_blocks:
        if (
            block_item["username"].lower() != EXTRACT_TARGET.lower()
            and block_item["id"] != current_id_from_url
        ):
            remove_temp_posters_from_list([block_item])
            continue

        if is_ad_post(block_item["text"]):
            print(f"🚫 広告投稿（ID: {block_item['id']}）のためスキップ。")
            remove_temp_posters_from_list([block_item])
            continue

        try:
            impressions, retweets, likes, bookmarks, replies_count = extract_metrics(
                block_item["article_element"]
            )
        except StaleElementReferenceException:
            print(
                f"⚠️ メトリクス抽出中にStaleElement (ID: {block_item['id']})。メトリクスは0になります。"
            )
            impressions, retweets, likes, bookmarks, replies_count = None, 0, 0, 0, 0
        except Exception as e_metrics:
            print(
                f"⚠️ メトリクス抽出エラー (ID: {block_item['id']}): {e_metrics}。メトリクスは0になります。"
            )
            impressions, retweets, likes, bookmarks, replies_count = None, 0, 0, 0, 0

        final_block = block_item.copy()
        final_block.pop("article_element", None)

        # 投稿URLはページURLから取得する（実際のツイートのURLを確保するため）
        tweet_url_for_post = tweet_url
        if current_id_from_url != block_item["id"]:
            # もし現在のツイートが詳細ページの投稿と異なる場合、
            # 詳細ページURLをベースにIDのみを置き換えて新しいURLを構築
            tweet_url_for_post = tweet_url.replace(
                current_id_from_url, block_item["id"]
            )

        final_block.update(
            {
                "url": tweet_url_for_post,
                "impressions": impressions,
                "retweets": retweets,
                "likes": likes,
                "bookmarks": bookmarks,
                "replies": replies_count,
            }
        )
        final_results.append(final_block)

    if not final_results:
        print("⚠️ フィルタリングの結果、有効な投稿が残りませんでした。")
        all_blocks_for_cleanup = list(tweet_blocks)
        remove_temp_posters_from_list(all_blocks_for_cleanup)
        return []

    final_results.sort(key=lambda x: int(x["id"]))
    final_ids_in_results = {item["id"] for item in final_results}
    blocks_not_in_final = [
        block for block in tweet_blocks if block["id"] not in final_ids_in_results
    ]
    remove_temp_posters_from_list(blocks_not_in_final)

    return final_results


def extract_and_merge_tweets(
    driver,
    tweet_urls_data,
    max_tweets_to_register,  # 目標登録数
    notion_client,
    config,
    registered_ids_map,
    current_success_count=0,  # 現在の登録成功数を追加
):
    final_tweets_for_notion = []
    # この関数サイクル内でのみ処理済みとするID (主にマージされたリプライや、条件未達でスキップされた親候補など)
    processed_ids_in_current_cycle = set()
    # 全てのDBから取得した、グローバルに処理済みのIDセット
    globally_processed_ids = registered_ids_map.get("all_processed", set())

    # この関数内で収集する「候補」の数をカウントする変数
    collected_candidates_count = 0

    # 目標登録数に対する倍率を設定
    max_candidates_multiplier = config.get("max_candidates_multiplier", 1.2)

    # 残り必要な登録件数を計算
    remaining_needed = max(0, max_tweets_to_register - current_success_count)

    # 残り必要数に対する候補収集上限の計算
    internal_candidate_collection_limit = min(
        len(tweet_urls_data),
        max(
            int(remaining_needed * max_candidates_multiplier),
            min(15, remaining_needed * 2),  # 残り少ない場合は最低値も調整
        ),
    )

    # URLリストをIDの降順（新しいものから）でソート
    tweet_urls_data.sort(
        key=lambda x: (
            int(x["id"])
            if isinstance(x, dict) and x.get("id") and str(x["id"]).isdigit()
            else float("-inf")
        ),
        reverse=True,
    )

    print(
        f"ℹ️ extract_and_merge_tweets: 開始。処理対象URL候補数: {len(tweet_urls_data)}, "
        f"目標登録数: {max_tweets_to_register}, "
        f"この関数内での候補収集上限: {internal_candidate_collection_limit}"
    )

    # 事前にURLからIDを抽出して重複チェック
    filtered_urls = []
    print(f"DEBUG: tweet_urls_data first 3 items: {tweet_urls_data[:3]}")
    print(
        f"DEBUG: registered_ids_map['all_processed'] size: {len(registered_ids_map.get('all_processed', set()))}"
    )

    for item in tweet_urls_data:
        # 辞書型かどうかチェックし、適切にURLを取得
        url_str = item["url"] if isinstance(item, dict) else item
        print(f"DEBUG: Processing URL: {url_str}")

        tweet_id_match = re.search(r"/status/(\d+)", url_str)
        if tweet_id_match:
            tweet_id = tweet_id_match.group(1)
            print(f"DEBUG: Extracted ID: {tweet_id}")
            if tweet_id not in registered_ids_map.get("all_processed", set()):
                filtered_urls.append(item)  # 元のアイテム（辞書または文字列）を維持
                print(f"DEBUG: ID {tweet_id} not in processed list, keeping.")
            else:
                print(f"🚫 詳細ページアクセス前に重複排除: {tweet_id}")
        else:
            print(f"DEBUG: Failed to extract ID from URL: {url_str}")
            filtered_urls.append(item)  # IDが抽出できない場合も追加

    # フィルタリング済みURLリストを使って処理を続行
    tweet_urls_data = filtered_urls

    for i, meta in enumerate(tweet_urls_data):
        if collected_candidates_count >= internal_candidate_collection_limit:
            print(
                f"🎯 内部候補収集数が上限 ({internal_candidate_collection_limit}) に達したためURL処理ループを終了"
            )
            break

        tweet_url = meta["url"] if isinstance(meta, dict) else meta
        current_potential_parent_id = meta.get("id") if isinstance(meta, dict) else None

        # まず、渡されたURLのIDがグローバル処理済みセットに含まれていれば、詳細ページアクセス自体をスキップ
        if (
            current_potential_parent_id
            and current_potential_parent_id in globally_processed_ids
        ):
            print(
                f"ℹ️ URL {tweet_url} (ID: {current_potential_parent_id}) は既にグローバル処理済みのため、詳細ページアクセスをスキップします。"
            )
            # このIDは既にグローバル処理済みなので、この関数の processed_ids_in_current_cycle には追加不要
            continue

        try:
            # 詳細ページからスレッド内の全投稿ブロックを取得 (新しい順にソート済み)
            thread_posts = extract_thread_from_detail_page(driver, tweet_url)
            if not thread_posts:
                print(
                    f"ℹ️ URL {tweet_url} からスレッド投稿が取得できませんでした。スキップします。"
                )
                # このURL自体は処理試行したが結果なし、としてマークすることも検討できる
                if current_potential_parent_id:
                    processed_ids_in_current_cycle.add(current_potential_parent_id)
                continue

            parent_post_candidate = None
            # このスレッドで現在の親候補にマージされたリプライIDを一時的に保持するセット
            current_thread_merged_reply_ids = set()

            for post_idx, post_in_thread in enumerate(thread_posts):
                if collected_candidates_count >= internal_candidate_collection_limit:
                    break  # 内部ループも上限に達したら抜ける

                current_post_id = post_in_thread.get("id")
                if not current_post_id:
                    print(
                        "⚠️ IDがない投稿データはスキップ (in extract_and_merge_tweets)"
                    )
                    continue

                # グローバル処理済みIDセットに含まれていれば、この投稿は完全にスキップ
                if current_post_id in globally_processed_ids:
                    print(
                        f"DEBUG: Post ID {current_post_id} is globally processed. Skipping."
                    )
                    continue

                # この関数サイクル内で既に処理済み（例：前の親候補にマージされた、または登録候補として確定した）
                # かつ、現在の親候補そのものでない場合もスキップ
                if current_post_id in processed_ids_in_current_cycle and (
                    not parent_post_candidate
                    or current_post_id != parent_post_candidate.get("id")
                ):
                    print(
                        f"DEBUG: Post ID {current_post_id} is processed in current cycle and not current parent. Skipping."
                    )
                    continue

                # 既に final_tweets_for_notion に追加されているIDもスキップ (念のため)
                if any(
                    ftn_item["id"] == current_post_id
                    for ftn_item in final_tweets_for_notion
                ):
                    print(
                        f"DEBUG: Post ID {current_post_id} is already in final_tweets_for_notion. Skipping."
                    )
                    continue

                is_current_post_quote = post_in_thread.get("is_quote_tweet", False)
                current_text_len = post_in_thread.get("text_length", 0)
                current_has_media = post_in_thread.get("has_media", False)

                # --- 親候補がまだない場合 ---
                if parent_post_candidate is None:
                    # この投稿が条件未達の引用RTなら、処理済みとしてマークしてスキップ
                    if is_current_post_quote and not (
                        current_text_len >= 50 and current_has_media
                    ):
                        print(
                            f"DEBUG: Initial post {current_post_id} is a non-qualifying quote. Marking as processed."
                        )
                        processed_ids_in_current_cycle.add(current_post_id)
                    else:
                        # それ以外は親候補とする
                        parent_post_candidate = post_in_thread.copy()
                        current_thread_merged_reply_ids = (
                            set()
                        )  # 新しい親候補なのでマージ済みIDをリセット
                        print(
                            f"DEBUG: New parent candidate set: {parent_post_candidate.get('id')}"
                        )
                    continue  # 次の投稿へ

                # --- 親候補がある場合 ---
                # 現在の投稿が親候補自身ならスキップ (通常は起こらないはずだが念のため)
                if current_post_id == parent_post_candidate.get("id"):
                    continue

                # リプライ判定: 同じユーザーで、IDが親候補より小さい（古い）
                is_reply_to_parent = post_in_thread.get(
                    "username"
                ) == parent_post_candidate.get("username") and int(
                    post_in_thread.get("id", 0)
                ) > int(
                    parent_post_candidate.get("id", 0)
                )

                # --- リプライではない場合 (新しい親候補の開始) ---
                if not is_reply_to_parent:
                    print(
                        f"DEBUG: Post {current_post_id} is not a reply to current parent {parent_post_candidate.get('id')}. Finalizing current parent."
                    )
                    # 現在の親候補を登録リストに追加する (条件を満たせば)
                    if parent_post_candidate:
                        # 親候補がグローバル処理済みでないことを再度確認
                        if (
                            parent_post_candidate.get("id")
                            not in globally_processed_ids
                        ):
                            temp_is_quote = parent_post_candidate.get(
                                "is_quote_tweet", False
                            )
                            temp_text_len = parent_post_candidate.get("text_length", 0)
                            temp_has_media = parent_post_candidate.get(
                                "has_media", False
                            )
                            # 条件を満たす親候補か (条件未達の引用RTでない)
                            if not (
                                temp_is_quote
                                and not (temp_text_len >= 50 and temp_has_media)
                            ):
                                if (
                                    collected_candidates_count
                                    < internal_candidate_collection_limit
                                ):
                                    if not any(
                                        ftn_item["id"]
                                        == parent_post_candidate.get("id")
                                        for ftn_item in final_tweets_for_notion
                                    ):
                                        parent_post_candidate["merged_reply_ids"] = (
                                            list(current_thread_merged_reply_ids)
                                        )
                                        final_tweets_for_notion.append(
                                            parent_post_candidate
                                        )
                                        collected_candidates_count += 1
                                        processed_ids_in_current_cycle.add(
                                            parent_post_candidate.get("id")
                                        )
                                        print(
                                            f"DEBUG: Added parent {parent_post_candidate.get('id')} to final list. Count: {collected_candidates_count}"
                                        )
                                else:  # 上限
                                    break
                            else:  # 条件未達の引用RTだった親候補
                                processed_ids_in_current_cycle.add(
                                    parent_post_candidate.get("id")
                                )
                                print(
                                    f"DEBUG: Previous parent {parent_post_candidate.get('id')} was non-qualifying quote. Marked as processed."
                                )
                        else:  # 親候補がグローバル処理済みだった場合
                            print(
                                f"DEBUG: Previous parent {parent_post_candidate.get('id')} was globally processed. Not adding to final list."
                            )

                    # 新しい投稿を親候補として設定
                    if is_current_post_quote and not (
                        current_text_len >= 50 and current_has_media
                    ):
                        parent_post_candidate = None  # 条件未達の引用RTは親候補にしない
                        processed_ids_in_current_cycle.add(current_post_id)
                        print(
                            f"DEBUG: New post {current_post_id} is non-qualifying quote. Parent set to None. Marked as processed."
                        )
                    else:
                        parent_post_candidate = post_in_thread.copy()
                        current_thread_merged_reply_ids = (
                            set()
                        )  # 新しい親候補なのでリセット
                        print(
                            f"DEBUG: New parent candidate set: {parent_post_candidate.get('id')}"
                        )
                    continue  # 次の投稿へ

                # --- 親へのリプライである場合の処理 ---
                print(
                    f"DEBUG: Post {current_post_id} is a reply to parent {parent_post_candidate.get('id')}."
                )
                # このリプライが条件を満たす引用RTか、またはメディア付きリプライか
                if (
                    is_current_post_quote
                    and current_text_len >= 50
                    and current_has_media
                ) or (not is_current_post_quote and current_has_media):
                    print(
                        f"DEBUG: Reply {current_post_id} is a qualifying quote or media reply. Finalizing current parent."
                    )
                    # 現在の親候補を登録リストに追加 (条件を満たせば)
                    if (
                        parent_post_candidate
                        and parent_post_candidate.get("id")
                        not in globally_processed_ids
                    ):
                        temp_is_quote_parent = parent_post_candidate.get(
                            "is_quote_tweet", False
                        )
                        temp_text_len_parent = parent_post_candidate.get(
                            "text_length", 0
                        )
                        temp_has_media_parent = parent_post_candidate.get(
                            "has_media", False
                        )
                        if not (
                            temp_is_quote_parent
                            and not (
                                temp_text_len_parent >= 50 and temp_has_media_parent
                            )
                        ):
                            if (
                                collected_candidates_count
                                < internal_candidate_collection_limit
                            ):
                                if not any(
                                    ftn_item["id"] == parent_post_candidate.get("id")
                                    for ftn_item in final_tweets_for_notion
                                ):
                                    parent_post_candidate["merged_reply_ids"] = list(
                                        current_thread_merged_reply_ids
                                    )
                                    final_tweets_for_notion.append(
                                        parent_post_candidate
                                    )
                                    collected_candidates_count += 1
                                    processed_ids_in_current_cycle.add(
                                        parent_post_candidate.get("id")
                                    )
                                    print(
                                        f"DEBUG: Added parent {parent_post_candidate.get('id')} to final list due to qualifying reply. Count: {collected_candidates_count}"
                                    )
                            else:  # 上限
                                break
                        else:  # 条件未達の引用RTだった親候補
                            processed_ids_in_current_cycle.add(
                                parent_post_candidate.get("id")
                            )
                            print(
                                f"DEBUG: Previous parent {parent_post_candidate.get('id')} was non-qualifying quote. Marked as processed."
                            )

                    # このリプライ自体を新しい親候補として設定
                    parent_post_candidate = post_in_thread.copy()
                    current_thread_merged_reply_ids = (
                        set()
                    )  # 新しい親候補なのでリセット
                    print(
                        f"DEBUG: Qualifying reply {current_post_id} becomes new parent candidate."
                    )

                elif is_current_post_quote:  # 条件未達の引用リプライ
                    processed_ids_in_current_cycle.add(current_post_id)
                    print(
                        f"DEBUG: Reply {current_post_id} is non-qualifying quote reply. Marked as processed."
                    )
                else:  # テキストのみのリプライ (マージ対象)
                    if parent_post_candidate:
                        parent_text_before_merge = parent_post_candidate.get("text", "")
                        reply_text_to_merge = post_in_thread.get("text", "")
                        # スレッドは新しい順に処理しているので、古いリプライ(IDが小さい)のテキストを「前」に結合
                        parent_post_candidate["text"] = (
                            parent_text_before_merge + "\n\n" + reply_text_to_merge
                        ).strip()
                        parent_post_candidate["text_length"] = len(
                            parent_post_candidate["text"]
                        )

                        current_thread_merged_reply_ids.add(
                            current_post_id
                        )  # マージされたリプライIDを記録
                        processed_ids_in_current_cycle.add(
                            current_post_id
                        )  # このサイクルでは処理済み
                        print(
                            f"DEBUG: Merged text-only reply {current_post_id} into parent {parent_post_candidate.get('id')}. Merged IDs: {current_thread_merged_reply_ids}"
                        )

                if collected_candidates_count >= internal_candidate_collection_limit:
                    break  # 内部ループも上限に達したら抜ける

            # --- スレッド内の全投稿処理後、最後の親候補が残っていれば処理 ---
            if (
                parent_post_candidate
                and parent_post_candidate.get("id") not in globally_processed_ids
                and not any(
                    ftn_item["id"] == parent_post_candidate.get("id")
                    for ftn_item in final_tweets_for_notion
                )
                and parent_post_candidate.get("id")
                not in processed_ids_in_current_cycle  # このサイクルで既に処理済みでないことも確認
            ):
                print(
                    f"DEBUG: Processing final parent candidate {parent_post_candidate.get('id')} after loop."
                )
                is_final_quote = parent_post_candidate.get("is_quote_tweet", False)
                final_text_len = parent_post_candidate.get("text_length", 0)
                final_has_media = parent_post_candidate.get("has_media", False)

                # 条件を満たす親候補か (条件未達の引用RTでない)
                if not (
                    is_final_quote and not (final_text_len >= 50 and final_has_media)
                ):
                    if collected_candidates_count < internal_candidate_collection_limit:
                        parent_post_candidate["merged_reply_ids"] = list(
                            current_thread_merged_reply_ids
                        )
                        final_tweets_for_notion.append(parent_post_candidate)
                        collected_candidates_count += 1
                        processed_ids_in_current_cycle.add(
                            parent_post_candidate.get("id")
                        )
                        print(
                            f"DEBUG: Added final parent {parent_post_candidate.get('id')} to list. Count: {collected_candidates_count}"
                        )
                else:  # 条件未達の引用RTだった最後の親候補
                    processed_ids_in_current_cycle.add(parent_post_candidate.get("id"))
                    print(
                        f"DEBUG: Final parent {parent_post_candidate.get('id')} was non-qualifying quote. Marked as processed."
                    )
            elif (
                parent_post_candidate
            ):  # 最後の親候補が残っていたが、上記の条件で追加されなかった場合
                # 既にグローバル処理済み、またはfinal_tweets_for_notionに存在、またはこのサイクルで処理済みの場合
                # このIDは processed_ids_in_current_cycle に追加する必要があるか検討
                # (通常は上記のif条件のいずれかで既にマークされているはず)
                if (
                    parent_post_candidate.get("id")
                    not in processed_ids_in_current_cycle
                    and parent_post_candidate.get("id") not in globally_processed_ids
                    and not any(
                        ftn_item["id"] == parent_post_candidate.get("id")
                        for ftn_item in final_tweets_for_notion
                    )
                ):
                    # このケースは稀だが、もし発生したらログで確認
                    print(
                        f"DEBUG: Final parent candidate {parent_post_candidate.get('id')} was not added and not explicitly marked processed. This might be an edge case."
                    )
                else:
                    print(
                        f"DEBUG: Final parent candidate {parent_post_candidate.get('id')} was skipped (globally processed, already in final list, or processed in cycle)."
                    )

            if collected_candidates_count >= internal_candidate_collection_limit:
                break  # URL処理ループを抜ける
        except Exception as e:
            print(
                f"⚠️ スレッド処理全体でエラー ({tweet_url}): {type(e).__name__} - {e}\n{traceback.format_exc()}"
            )
            # エラーが発生した場合でも、一時保存されたポスター画像をクリーンアップする試み
            if "thread_posts" in locals() and thread_posts:
                for post_data_item in thread_posts:
                    for poster_p in post_data_item.get("video_posters", []):
                        if (
                            isinstance(poster_p, str)
                            and os.path.exists(poster_p)
                            and "temp_posters" in poster_p
                        ):
                            try:
                                os.remove(poster_p)
                            except Exception:
                                pass
            # このURLの処理でエラーが起きた場合、そのURLのIDを処理済みとしてマークする
            if current_potential_parent_id:
                processed_ids_in_current_cycle.add(current_potential_parent_id)
            continue  # 次のURLへ

    print(
        f"\n📈 extract_and_merge_tweets: 収集した候補投稿数: {len(final_tweets_for_notion)} 件"
    )
    # 最終的なリストはIDの降順（新しいものが先頭）で返す
    final_tweets_for_notion.sort(
        key=lambda x: (
            int(x["id"]) if x.get("id") and str(x["id"]).isdigit() else float("-inf")
        ),
        reverse=True,
    )
    return final_tweets_for_notion, processed_ids_in_current_cycle


def extract_metrics(article):
    """
    いいね数・リポスト数・インプレッション数・ブックマーク数・リプライ数を抽出
    取得できないものは0（インプレッションのみNone）で返す
    """
    impressions_str = retweets_str = likes_str = bookmarks_str = replies_str = None
    try:
        # 優先的に div[role="group"] の aria-label から取得を試みる
        # これが最も情報がまとまっていることが多い
        group_divs = article.find_elements(
            By.XPATH, ".//div[@role='group' and @aria-label]"
        )

        primary_label_processed = False
        if group_divs:
            for group_div in group_divs:
                label = group_div.get_attribute("aria-label")
                if not label:
                    continue

                print(f"🟦 metrics group aria-label内容: {label}")
                primary_label_processed = True  # このラベルを処理したことをマーク

                # 各指標を個別に抽出する (順番に依存しないように)
                m_replies = re.search(r"(\d[\d,\.万]*)\s*件の返信", label)
                if m_replies:
                    replies_str = m_replies.group(1)

                m_retweets = re.search(r"(\d[\d,\.万]*)\s*件のリポスト", label)
                if m_retweets:
                    retweets_str = m_retweets.group(1)

                m_likes = re.search(r"(\d[\d,\.万]*)\s*件のいいね", label)
                if m_likes:
                    likes_str = m_likes.group(1)

                m_bookmarks = re.search(r"(\d[\d,\.万]*)\s*件のブックマーク", label)
                if m_bookmarks:
                    bookmarks_str = m_bookmarks.group(1)

                m_impressions = re.search(r"(\d[\d,\.万]*)\s*件の表示", label)
                if m_impressions:
                    impressions_str = m_impressions.group(1)

                # 一つのラベルから全て取れたら抜けることが多いが、稀に分割されている可能性も考慮し、
                # 基本的には最初の group_div のラベルを主とする。
                # もし、複数の group_div が異なる情報を持つケースが確認されれば、ここのロジック再考。
                break

        if not primary_label_processed:
            # group_div が見つからないか、aria-label がない場合、以前のフォールバックも試す
            # ただし、このパスはXのUIが大きく変わった場合は機能しない可能性が高い
            other_divs = article.find_elements(
                By.XPATH,
                ".//div[contains(@aria-label, '件の表示') and not(@role='group')]",
            )
            for div in other_divs:
                label = div.get_attribute("aria-label")
                if not label:
                    continue
                print(f"🟦 other metrics div aria-label内容: {label}")
                # ここでも同様に個別抽出を試みる (上記と同じロジック)
                if replies_str is None:
                    m_replies = re.search(r"(\d[\d,\.万]*)\s*件の返信", label)
                    if m_replies:
                        replies_str = m_replies.group(1)
                if retweets_str is None:
                    m_retweets = re.search(r"(\d[\d,\.万]*)\s*件のリポスト", label)
                    if m_retweets:
                        retweets_str = m_retweets.group(1)
                if likes_str is None:
                    m_likes = re.search(r"(\d[\d,\.万]*)\s*件のいいね", label)
                    if m_likes:
                        likes_str = m_likes.group(1)
                if bookmarks_str is None:
                    m_bookmarks = re.search(r"(\d[\d,\.万]*)\s*件のブックマーク", label)
                    if m_bookmarks:
                        bookmarks_str = m_bookmarks.group(1)
                if impressions_str is None:
                    m_impressions = re.search(r"(\d[\d,\.万]*)\s*件の表示", label)
                    if m_impressions:
                        impressions_str = m_impressions.group(1)
                break  # 最初に見つかったもので処理

        # 個別ボタンからのフォールバック取得
        if replies_str is None:
            try:
                reply_btns = article.find_elements(
                    By.XPATH, ".//button[@data-testid='reply']"
                )
                for btn in reply_btns:
                    label = btn.get_attribute("aria-label")
                    m = re.search(r"(\d[\d,\.万]*)\s*件の返信", label or "")
                    if m:
                        replies_str = m.group(1)
                        print(f"🟦 ボタンからリプライ数取得: {replies_str}")
                        break
            except Exception as e:
                print(f"⚠️ リプライ数ボタン抽出エラー: {e}")

        if retweets_str is None:
            try:
                rt_btns = article.find_elements(
                    By.XPATH, ".//button[@data-testid='retweet']"
                )
                for btn in rt_btns:
                    label = btn.get_attribute("aria-label")
                    m = re.search(r"(\d[\d,\.万]*)\s*件のリポスト", label or "")
                    if m:
                        retweets_str = m.group(1)
                        print(f"🟦 ボタンからリポスト数取得: {retweets_str}")
                        break
            except Exception as e:
                print(f"⚠️ リポスト数ボタン抽出エラー: {e}")

        if likes_str is None:
            try:
                like_btns = article.find_elements(
                    By.XPATH, ".//button[@data-testid='like']"
                )
                for btn in like_btns:
                    label = btn.get_attribute("aria-label")
                    m = re.search(r"(\d[\d,\.万]*)\s*件のいいね", label or "")
                    if m:
                        likes_str = m.group(1)
                        print(f"🟦 ボタンからいいね数取得: {likes_str}")
                        break
            except Exception as e:
                print(f"⚠️ いいね数ボタン抽出エラー: {e}")

        if bookmarks_str is None:
            try:
                bm_btns = article.find_elements(
                    By.XPATH, ".//button[@data-testid='bookmark']"
                )
                for btn in bm_btns:
                    label = btn.get_attribute("aria-label")
                    m = re.search(r"(\d[\d,\.万]*)\s*件のブックマーク", label or "")
                    if m:
                        bookmarks_str = m.group(1)
                        print(f"🟦 ボタンからブックマーク数取得: {bookmarks_str}")
                        break
            except Exception as e:
                print(f"⚠️ ブックマーク数ボタン抽出エラー: {e}")

        # インプレッションはボタンからは通常取れないので、aria-label頼み
        # もし impressions_str が None で、他の指標が取れている場合、
        # かつての「インプレッションのみ」のパターンで取れていた可能性を考慮し、
        # likes/retweets/bookmarks/replies が全て0なら、impressions_str を採用し他を0にする。
        # ただし、このロジックは複雑なので、一旦は上記で取得できたものをそのまま使う。
        # もしインプレッションだけが取れて他が0になるべきケースが多発するなら再検討。

        def parse_num(s):
            if not s:
                return 0  # None や空文字の場合は0として扱う (インプレッション以外)
            s_cleaned = str(s).replace(",", "")
            if "万" in s_cleaned:
                try:
                    return int(float(s_cleaned.replace("万", "")) * 10000)
                except ValueError:
                    return 0  # "万" があっても数値変換できない場合
            try:
                return int(s_cleaned)
            except ValueError:  # "K" や "M" などの英語圏の略称は現状非対応
                return 0  # 数値変換できない場合は0

        # インプレッションのみ None を許容し、他は0をデフォルトとする
        impressions = (
            parse_num(impressions_str) if impressions_str is not None else None
        )
        retweets = parse_num(retweets_str)
        likes = parse_num(likes_str)
        bookmarks = parse_num(bookmarks_str)
        replies = parse_num(replies_str)

        # デバッグ用に最終的な値を表示
        print(
            f"🔢 抽出結果: 表示={impressions}, RT={retweets}, いいね={likes}, BM={bookmarks}, リプライ={replies}"
        )

    except Exception as e:
        print(f"⚠️ extract_metrics全体エラー: {e}\n{traceback.format_exc()}")
        # エラー時は全てデフォルト値 (impressions=None, 他=0)
        impressions = None
        retweets = 0
        likes = 0
        bookmarks = 0
        replies = 0

    return impressions, retweets, likes, bookmarks, replies


def is_reply_structure(
    article,
    tweet_id=None,
    text="",
    image_urls=None,
    video_poster_urls=None,
):
    try:
        id_display = f"（ID={tweet_id}）" if tweet_id else ""

        try:
            if not article.is_displayed():
                print(
                    f"DEBUG is_reply_structure: Article element not displayed {id_display} -> Assuming reply structure (True)."
                )
                return True
        except StaleElementReferenceException:
            print(
                f"DEBUG is_reply_structure: StaleElementReferenceException on article.is_displayed() {id_display} -> Assuming reply structure (True)."
            )
            return True  # Safety measure

        # 引用RT構造の判定
        is_quote_tweet_structure = False
        try:
            # 優先度1: data-testid="tweetQuote" を持つ要素があるか
            quote_testid_elements = article.find_elements(
                By.XPATH, ".//div[@data-testid='tweetQuote']"
            )
            if quote_testid_elements:
                if any(el.is_displayed() for el in quote_testid_elements):
                    is_quote_tweet_structure = True
                    print(
                        f"DEBUG is_reply_structure: 引用判定 -> data-testid='tweetQuote' を検出 (表示確認済み) {id_display}"
                    )
                # else:
                #     print(
                #         f"DEBUG is_reply_structure: 引用判定 -> data-testid='tweetQuote' を検出したが非表示 {id_display}"
                #     )

            # 優先度2: 従来の構造ベースの判定 (is_quote_tweet_structure がまだ False の場合)
            if not is_quote_tweet_structure:
                # 修正: 引用RTのコンテナは必ずしも内部にarticleを持つとは限らない。
                # role='link' を持ち、その中に何らかのツイート内容を示唆する要素があるか、
                # または特定のクラス構造を持つものを探す。
                # よりシンプルなのは、"引用"というテキストや、特定のaria-labelを持つ要素を探すこと。

                # 構造的XPath: role='link' を持ち、その中にタイムスタンプを持つ要素があるか
                # (タイムスタンプは引用されたツイートの存在を示唆する)
                structural_quote_elements = article.find_elements(
                    By.XPATH, "./descendant::div[@role='link' and .//time[@datetime]]"
                )
                if structural_quote_elements:
                    if any(el.is_displayed() for el in structural_quote_elements):
                        # これが本当に引用RTのコンテナか、さらに絞り込む必要があるかもしれない
                        # 例えば、このdiv[@role='link']の直前に「引用」テキストがあるかなど
                        # 今回は、表示されているrole='link' with timeがあれば引用構造とみなす
                        is_quote_tweet_structure = True
                        print(
                            f"DEBUG is_reply_structure: 引用判定 -> 構造的XPath (role='link' with time) が {len(structural_quote_elements)} 件マッチ (表示確認済み) {id_display}"
                        )
                    # else:
                    #     print(
                    #         f"DEBUG is_reply_structure: 引用判定 -> 構造的XPath (role='link' with time) が {len(structural_quote_elements)} 件マッチしたが非表示 {id_display}"
                    #     )

            # 優先度3: フォールバック (引用テキストインジケータ)
            if not is_quote_tweet_structure:
                # "引用" というテキストが、ツイート本文(@data-testid='tweetText')の外側にあるか
                # かつ、それが表示されているか
                quote_indicators = article.find_elements(
                    By.XPATH,
                    ".//div[not(ancestor-or-self::div[@data-testid='tweetText'])]//span[text()='引用']",
                )
                if any(el.is_displayed() for el in quote_indicators):
                    is_quote_tweet_structure = True
                    print(
                        f"DEBUG is_reply_structure: 引用判定 -> 引用テキストインジケータ（'引用' span）を検出 {id_display}"
                    )

            # if not is_quote_tweet_structure:
            #     print(
            #         f"DEBUG is_reply_structure: 引用判定 -> 引用RT構造は見つかりませんでした {id_display}"
            #     )

        except StaleElementReferenceException as e_quote_staleness:
            print(
                f"DEBUG is_reply_structure: 引用判定中にStaleElement {id_display} -> {e_quote_staleness}"
            )
            is_quote_tweet_structure = (
                False  # Stale時は引用でないと判断して進む方が安全か、エラーにするか
            )
        except Exception as e_quote_check:
            print(
                f"⚠️ is_reply_structure: 引用判定中のエラー {id_display} → {type(e_quote_check).__name__}: {e_quote_check}"
            )
            is_quote_tweet_structure = False

        # --- 引用RT構造の場合の処理 ---
        if is_quote_tweet_structure:
            text_length = len(text.strip()) if text else 0
            # image_urls と video_poster_urls は、呼び出し元(extract_tweets)で
            # 「引用RTの本体ツイートのメディアのみ」にフィルタリングされている前提。
            has_direct_media = bool(image_urls or video_poster_urls)

            if text_length >= 50 and has_direct_media:
                print(
                    f"✅ is_reply_structure: 引用RT（条件達成: 50文字以上かつ本体メディア付き）→ 親投稿として許可 (False) {id_display} | 長さ={text_length}, 本体メディア={has_direct_media}"
                )
                return False  # 収集対象の引用RT (False = リプライ構造ではない)
            else:
                print(
                    f"🛑 is_reply_structure: 引用RT（条件未達: 50文字以上かつ本体メディア付きではない）→ 除外 (True) {id_display} | 長さ={text_length}, 本体メディア={has_direct_media}"
                )
                return True  # 収集対象外の引用RT (True = リプライ構造である、または収集対象外)

        # --- 引用RTでない場合の通常リプライ判定 ---

        # 1. メディアカードや直接メディアの存在チェック
        try:
            # data-testid="card.wrapper" を持つ要素があるか (引用RT内部は除外)
            card_wrapper_elements = article.find_elements(
                By.XPATH,
                ".//div[@data-testid='card.wrapper'][not(ancestor::div[@data-testid='tweetQuote'])]",
            )
            if card_wrapper_elements:
                if any(el.is_displayed() for el in card_wrapper_elements):
                    print(
                        f"✅ is_reply_structure: card.wrapper を検出 (表示確認済み) → 親投稿として許可 (False) {id_display}"
                    )
                    return False
                # else:
                #     print(
                #         f"DEBUG is_reply_structure: card.wrapper を検出したが非表示 {id_display}"
                #     )

            # 呼び出し元から渡された「本体メディア」が存在する場合
            if image_urls or video_poster_urls:
                print(
                    f"✅ is_reply_structure: 引数による直接メディア検出 (images: {bool(image_urls)}, videos: {bool(video_poster_urls)}) → 親投稿として許可 (False) {id_display}"
                )
                return False

        except StaleElementReferenceException:
            print(
                f"DEBUG is_reply_structure: StaleElementReferenceException during card/media check {id_display}."
            )
        except Exception as e_media_check:
            print(
                f"⚠️ is_reply_structure: card/media チェック中のエラー {id_display} → {type(e_media_check).__name__}: {e_media_check}"
            )

        # 2. socialContext (返信先、固定ツイートなど) のチェック
        is_pinned_tweet = False
        try:
            social_context_elements = article.find_elements(
                By.XPATH, ".//div[@data-testid='socialContext']"
            )
            # if not social_context_elements:
            #     print(
            #         f"DEBUG is_reply_structure: ID {tweet_id}, socialContext要素が見つかりません。"
            #     )

            for sc_el in social_context_elements:
                if sc_el.is_displayed():
                    sc_text_content = sc_el.text
                    sc_text_lower = sc_text_content.lower()
                    # print(
                    #     f"DEBUG is_reply_structure: ID {tweet_id}, socialContext表示テキスト: '{sc_text_content}'"
                    # )
                    if "固定" in sc_text_content or "pinned" in sc_text_lower:
                        is_pinned_tweet = True
                        # print(
                        #     f"DEBUG is_reply_structure: ID {tweet_id}, socialContextにより固定ツイートと判定。"
                        # )

                    reply_keywords = ["replying to", "返信先:", "replied to"]
                    if any(
                        keyword in sc_text_lower for keyword in reply_keywords
                    ) or re.search(r"@\w+\s*に返信", sc_text_content, re.IGNORECASE):
                        try:
                            # socialContextが引用RTの一部であるかを確認
                            sc_el.find_element(
                                By.XPATH,
                                "ancestor::div[@data-testid='tweetQuote'] | ancestor::div[@role='link' and .//time[@datetime]]",  # 引用RTコンテナの判定を少し広げる
                            )
                            # print(
                            #     f"DEBUG is_reply_structure (socialContext): ID {tweet_id}, socialContextは引用RT内のためスキップ: '{sc_text_content[:30]}...'"
                            # )
                            continue  # 引用RT内ならこのsocialContextは無視
                        except NoSuchElementException:
                            # 引用RT内でなければ、リプライと判定
                            print(
                                f"💬 is_reply_structure (socialContext): ID {tweet_id} → 通常リプライ判定 (True) (テキスト一致: '{sc_text_content[:30]}...')"
                            )
                            return True
        except StaleElementReferenceException:
            print(
                f"DEBUG is_reply_structure: StaleElementReferenceException during socialContext check {id_display}."
            )
        except NoSuchElementException:
            # print(
            #     f"DEBUG is_reply_structure: ID {tweet_id}, socialContext要素の検索で予期せぬNoSuchElement。"
            # )
            pass
        except Exception as e_sc_check:
            print(
                f"⚠️ is_reply_structure: socialContext確認中のエラー {id_display} → {type(e_sc_check).__name__}: {e_sc_check}"
            )

        # 3. 構造的なリプライインジケータ（リプライ線など）のチェック
        #    XのUI変更でリプライ線のクラス名は非常に不安定なため、このチェックは限定的にするか、
        #    より堅牢な方法が見つかるまでコメントアウトも検討。
        #    現状は、特定のクラス名に依存しない、より一般的な構造を探す方が良いかもしれない。
        #    例えば、「特定の要素の直前に縦線のようなdivがある」など。
        #    ここでは一旦、以前のロジックはコメントアウトし、より安全な判定に倒す。
        #
        # try:
        #     # ... (リプライ線チェックロジック) ...
        # except Exception as e_reply_line_check:
        #     # ...
        #     pass

        # 4. "返信先: @" や "Replying to @" のテキストがツイート本文や引用RTの外側にあるか
        try:
            base_condition = "starts-with(normalize-space(.), 'Replying to @') or starts-with(normalize-space(.), '返信先: @') or starts-with(normalize-space(.), 'In reply to @')"
            not_in_quote_condition = "not(ancestor::div[@data-testid='tweetQuote']) and not(ancestor::div[@role='link' and .//time[@datetime]])"
            not_in_text_div_condition = (
                "not(ancestor-or-self::div[@data-testid='tweetText'])"
            )

            xpath_for_reply_text_indicator = f".//*[(self::div or self::span) and ({base_condition}) and ({not_in_quote_condition}) and ({not_in_text_div_condition})]"

            reply_to_user_text_elements = article.find_elements(
                By.XPATH, xpath_for_reply_text_indicator
            )

            # if not reply_to_user_text_elements:
            #     print(
            #         f"DEBUG is_reply_structure: ID {tweet_id}, 返信先テキスト要素が見つかりません (XPath: {xpath_for_reply_text_indicator})"
            #     )

            for el in reply_to_user_text_elements:
                if el.is_displayed():
                    el_text_content = el.text
                    # print(
                    #     f"DEBUG is_reply_structure: ID {tweet_id}, 返信先テキスト候補: '{el_text_content}'"
                    # )
                    if "@" in el_text_content:
                        print(
                            f"💬 is_reply_structure (reply_to_user_text): ID {tweet_id} → 通常リプライ判定 (True) (テキスト一致: '{el_text_content[:30]}...')"
                        )
                        return True
        except StaleElementReferenceException:
            print(
                f"DEBUG is_reply_structure: StaleElementReferenceException during reply text check {id_display}."
            )
        except Exception as e_indicator:
            print(
                f"⚠️ is_reply_structure: 返信先テキスト確認中のエラー {id_display} → {type(e_indicator).__name__}: {e_indicator}"
            )

        # 5. ボタンの数による判定 (フォールバック)
        try:
            # 引用RTコンテナ内部のボタンは除外
            action_buttons_group = article.find_elements(
                By.XPATH,
                ".//div[@role='group' and count(.//button[@data-testid]) > 0 and not(ancestor::div[@data-testid='tweetQuote'])]",
            )
            if action_buttons_group:
                visible_group = None
                for group in action_buttons_group:
                    if group.is_displayed():
                        visible_group = group
                        break

                if visible_group:
                    buttons_in_group = visible_group.find_elements(
                        By.XPATH, ".//button[@data-testid]"
                    )
                    visible_buttons_count = sum(
                        1 for btn in buttons_in_group if btn.is_displayed()
                    )

                    # 通常ツイートは4つ(リプライ、RT、いいね、ブックマーク/アナリティクス)
                    # リプライは3つ以下(ブックマーク/アナリティクスがないことが多い)
                    # ただし、自分のツイートへのリプライなど、状況によってボタン数は変動しうるので注意
                    if 0 < visible_buttons_count <= 3:
                        # これが本当にリプライであるか、もう少し確証がほしい場合がある。
                        # 例えば、socialContext や 返信先テキスト がない場合に限り、ボタン数で判断するなど。
                        # ここでは、ボタン数が少ない場合はリプライの可能性が高いと判断する。
                        print(
                            f"💬 is_reply_structure (button_count): ID {tweet_id}, Visible Button Count: {visible_buttons_count} (<=3) → 通常リプライ判定の可能性 (True)"
                        )
                        return True
        except StaleElementReferenceException:
            print(
                f"DEBUG is_reply_structure: StaleElementReferenceException during button count check {id_display}."
            )
        except Exception as e_button_count:
            print(
                f"⚠️ is_reply_structure: ボタン数確認中のエラー {id_display} → {type(e_button_count).__name__}: {e_button_count}"
            )

        # 上記のいずれにも該当しない場合は、収集対象の親投稿とみなす
        print(
            f"✅ is_reply_structure: 構造上問題なし（非引用RT、非リプライ、メディアチェック済）→ 親投稿と判定 (False) {id_display}"
        )
        return False  # False = リプライ構造ではない (収集対象)

    except StaleElementReferenceException:
        print(
            f"⚠️ is_reply_structure: StaleElementReferenceException発生 {id_display} → 親投稿として扱う（False）（安全策）"
        )
        return False
    except Exception as e:
        print(
            f"⚠️ is_reply_structure: 判定エラー {id_display} → {type(e).__name__}: {e}\n{traceback.format_exc()} → 親投稿として扱う（False）（安全策）"
        )
        return False


def has_media_in_html(article_html):
    soup = BeautifulSoup(article_html, "html.parser")
    # 画像判定
    if soup.find("img", {"src": lambda x: x and "twimg.com/media" in x}):
        return True
    # 動画判定
    if soup.find("div", {"data-testid": "video-player-mini-ui-"}):
        return True
    if soup.find("button", {"aria-label": "動画を再生"}):
        return True
    if soup.find("video"):
        return True
    return False


def extract_tweets(
    driver,
    extract_target,
    max_tweets,
    globally_processed_ids,
    config,
    remaining_needed=None,
):
    # ユーザープロフィールページに確実にアクセスする
    user_profile_url = f"https://twitter.com/{extract_target}"
    print(f"\n✨ アクセス中: {user_profile_url}")
    driver.get(
        user_profile_url
    )  # この行を追加: 明示的にユーザープロフィールページにアクセス
    time.sleep(3)  # ページ読み込み待機

    print(
        f"DEBUG extract_tweets: globally_processed_ids (type: {type(globally_processed_ids)}, size: {len(globally_processed_ids)}) received. Sample: {list(globally_processed_ids)[:5] if globally_processed_ids else 'empty'}"
    )

    # URLの取得上限を計算
    # イテレーション時は残り必要投稿数を優先的に考慮する
    url_collection_limit = None

    if remaining_needed is not None and remaining_needed > 0:
        # 残り必要投稿数が25以下の場合は残り必要投稿数×2、それ以上の場合は50を上限とする
        url_collection_limit = (
            min(remaining_needed * 2, 50) if remaining_needed <= 25 else 50
        )
        print(
            f"ℹ️ 残り必要数: {remaining_needed}件、URL取得上限: {url_collection_limit}件に調整"
        )
    else:
        # 残り必要投稿数が指定されていない場合はmax_tweetsを使用
        url_collection_limit = min(max_tweets * 2, 50) if max_tweets <= 25 else 50
        print(
            f"ℹ️ 初回取得: max_tweets={max_tweets}件、URL取得上限: {url_collection_limit}件に設定"
        )

    tweet_urls = []
    seen_urls_in_current_call = set()

    scroll_count = 0
    max_scrolls = config.get("max_scrolls_extract_tweets", 20)
    pause_threshold = config.get("pause_threshold_extract_tweets", 6)
    scroll_pause_time = config.get("scroll_pause_time", 2.5)
    pause_counter = 0
    consecutive_stale_errors_article_loop = 0
    MAX_CONSECUTIVE_STALE_ERRORS_IN_SCROLL = 3

    while scroll_count < max_scrolls and len(tweet_urls) < url_collection_limit:
        print(
            f"\n🔍 スクロール {scroll_count + 1}/{max_scrolls} 回目 (収集済み: {len(tweet_urls)}/{url_collection_limit})"
        )

        current_articles_in_dom = []
        try:
            current_articles_in_dom = driver.find_elements(
                By.XPATH, "//article[@data-testid='tweet']"
            )
            print(f"📄 現在のarticle数: {len(current_articles_in_dom)}")
            if not current_articles_in_dom and scroll_count > 0:
                print("⚠️ スクロール後、article要素が見つかりません。")
                time.sleep(5)
                scroll_count += 1
                continue
        except Exception as e_find_articles:
            print(f"⚠️ article要素の検索中にエラー: {e_find_articles}")
            time.sleep(5)
            scroll_count += 1
            continue

        new_tweets_found_in_scroll = 0

        for i, article_element_to_process in enumerate(current_articles_in_dom):
            current_tweet_url_for_log = "不明"
            current_tweet_id_for_log = "不明"

            try:
                try:
                    if not article_element_to_process.is_displayed():
                        continue
                except StaleElementReferenceException:
                    print(
                        f"DEBUG extract_tweets: Article {i} is stale at the beginning of the loop. Breaking inner loop for this scroll."
                    )
                    consecutive_stale_errors_article_loop += 1
                    if (
                        consecutive_stale_errors_article_loop
                        >= MAX_CONSECUTIVE_STALE_ERRORS_IN_SCROLL
                    ):
                        print(
                            f"🚫 1スクロール内でStaleエラーが{MAX_CONSECUTIVE_STALE_ERRORS_IN_SCROLL}回連続。このスクロール処理を中断。"
                        )
                        break
                    continue

                main_link_elements = article_element_to_process.find_elements(
                    By.XPATH,
                    ".//a[.//time[@datetime] and contains(@href, '/status/') and not(ancestor::div[contains(@style, 'display: none')])]",
                )

                tweet_url = ""
                tweet_id = ""

                if main_link_elements:
                    for link_el in main_link_elements:
                        href_attr = link_el.get_attribute("href")
                        if href_attr and "/status/" in href_attr:
                            match = re.search(
                                r"twitter\.com/([^/]+)/status/(\d+)",
                                href_attr,
                                re.IGNORECASE,
                            ) or re.search(
                                r"x\.com/([^/]+)/status/(\d+)", href_attr, re.IGNORECASE
                            )
                            if match:
                                url_user = match.group(1)
                                potential_id = match.group(2)
                                if url_user.lower() == extract_target.lower():
                                    tweet_url = href_attr
                                    tweet_id = potential_id
                                    break
                    if not tweet_url and main_link_elements:
                        first_href = main_link_elements[0].get_attribute("href")
                        if first_href and "/status/" in first_href:
                            match_fb_id = re.search(r"/status/(\d+)", first_href)
                            if match_fb_id and not tweet_id:
                                pass

                if not tweet_id:
                    continue

                if not tweet_url:
                    tweet_url = f"https://x.com/{extract_target}/status/{tweet_id}"

                current_tweet_url_for_log = tweet_url
                current_tweet_id_for_log = tweet_id

                if tweet_url in seen_urls_in_current_call:
                    continue

                if tweet_id in globally_processed_ids:
                    seen_urls_in_current_call.add(tweet_url)
                    continue

                username_in_url_match = re.search(
                    r"x\.com/([^/]+)/status", tweet_url, re.IGNORECASE
                ) or re.search(r"twitter\.com/([^/]+)/status", tweet_url, re.IGNORECASE)
                if (
                    not username_in_url_match
                    or username_in_url_match.group(1).lower() != extract_target.lower()
                ):
                    seen_urls_in_current_call.add(tweet_url)
                    continue

                text_el = None
                text = ""
                try:
                    text_el = article_element_to_process.find_element(
                        By.XPATH, ".//div[@data-testid='tweetText']"
                    )
                    if text_el:
                        text = normalize_text(text_el.text)
                except NoSuchElementException:
                    pass
                except StaleElementReferenceException:
                    print(
                        f"DEBUG extract_tweets: Stale text element for ID {current_tweet_id_for_log}. Breaking inner loop for this scroll."
                    )
                    consecutive_stale_errors_article_loop += 1
                    break

                # --- メディア抽出ロジック ---
                images_for_check = []
                videos_for_check = []

                quote_container_in_this_article = None
                try:
                    quote_elements_by_testid = article_element_to_process.find_elements(
                        By.XPATH, ".//div[@data-testid='tweetQuote']"
                    )
                    for qc_el in quote_elements_by_testid:
                        if qc_el.is_displayed():
                            quote_container_in_this_article = qc_el
                            # print(f"DEBUG extract_tweets: ID {current_tweet_id_for_log}, Found quote container by testid.")
                            break

                    if not quote_container_in_this_article:
                        quote_text_indicator = None
                        qti_elements = article_element_to_process.find_elements(
                            By.XPATH,
                            ".//span[normalize-space(.)='引用' or normalize-space(.)='Quote'][not(ancestor::div[@data-testid='tweetText' or @data-testid='tweetQuote'])] | "
                            ".//div[normalize-space(.)='引用' or normalize-space(.)='Quote'][not(ancestor::div[@data-testid='tweetText' or @data-testid='tweetQuote'])]",
                        )
                        for qti_el in qti_elements:
                            if qti_el.is_displayed():
                                try:
                                    closest_article = qti_el.find_element(
                                        By.XPATH,
                                        "ancestor::article[@data-testid='tweet'][1]",
                                    )
                                    if closest_article == article_element_to_process:
                                        quote_text_indicator = qti_el
                                        # print(f"DEBUG extract_tweets: ID {current_tweet_id_for_log}, Found quote_text_indicator: '{quote_text_indicator.text}'")
                                        break
                                except (
                                    NoSuchElementException,
                                    StaleElementReferenceException,
                                ):
                                    pass

                        if quote_text_indicator:
                            potential_qlcs = article_element_to_process.find_elements(
                                By.XPATH,
                                ".//div[@role='link' and .//time[@datetime] and not(ancestor::div[@data-testid='tweetText' or @data-testid='tweetQuote'])]",
                            )
                            for qlc_candidate in potential_qlcs:
                                if qlc_candidate.is_displayed():
                                    try:
                                        closest_article_qlc = qlc_candidate.find_element(
                                            By.XPATH,
                                            "ancestor::article[@data-testid='tweet'][1]",
                                        )
                                        if (
                                            closest_article_qlc
                                            != article_element_to_process
                                        ):
                                            continue
                                        position_check = driver.execute_script(
                                            "return arguments[0].compareDocumentPosition(arguments[1])",
                                            quote_text_indicator,
                                            qlc_candidate,
                                        )
                                        if position_check & 4:
                                            quote_container_in_this_article = (
                                                qlc_candidate
                                            )
                                            # print(f"DEBUG extract_tweets: ID {current_tweet_id_for_log}, Found qlc structurally following indicator.")
                                            break
                                    except Exception as e_js_exec:
                                        print(
                                            f"DEBUG extract_tweets: JS exec error or stale element for position check (ID {current_tweet_id_for_log}): {e_js_exec}"
                                        )
                except StaleElementReferenceException:
                    print(
                        f"DEBUG extract_tweets: Stale quote container check for ID {current_tweet_id_for_log}. Breaking inner loop."
                    )
                    consecutive_stale_errors_article_loop += 1
                    break
                except Exception as e_qc_find_extract:
                    print(
                        f"DEBUG extract_tweets: Error finding quote container (ID {current_tweet_id_for_log}): {e_qc_find_extract}"
                    )

                # 画像抽出
                try:
                    # Find all img elements that could be media first
                    all_potential_raw_imgs = article_element_to_process.find_elements(
                        By.XPATH,
                        ".//img[contains(@src, 'twimg.com/media') or contains(@src, 'twimg.com/card_img')]",
                    )
                    # print(f"DEBUG extract_tweets: ID {current_tweet_id_for_log}, Found {len(all_potential_raw_imgs)} potential raw img elements.")

                    for img_el in all_potential_raw_imgs:
                        try:
                            visual_container = None
                            try:  # Check if it's within a tweetPhoto container
                                visual_container = img_el.find_element(
                                    By.XPATH,
                                    "ancestor::div[@data-testid='tweetPhoto'][1]",
                                )
                            except NoSuchElementException:
                                try:  # If not, check if it's within a card.layout container
                                    visual_container = img_el.find_element(
                                        By.XPATH,
                                        "ancestor::div[contains(@data-testid, 'card.layout')][1]",
                                    )
                                except NoSuchElementException:
                                    # print(f"DEBUG extract_tweets: ID {current_tweet_id_for_log}, Img has no 'tweetPhoto' or 'card.layout' ancestor: {img_el.get_attribute('src')}")
                                    continue

                            if not visual_container.is_displayed():
                                # print(f"DEBUG extract_tweets: ID {current_tweet_id_for_log}, Img's visual container not displayed: {img_el.get_attribute('src')}")
                                continue

                            is_inside_quote = False
                            if quote_container_in_this_article:
                                try:
                                    is_inside_quote = driver.execute_script(
                                        "return arguments[0].contains(arguments[1]);",
                                        quote_container_in_this_article,
                                        visual_container,
                                    )
                                except Exception:  # Fallback if JS fails
                                    try:
                                        if quote_container_in_this_article.find_elements(
                                            By.XPATH,
                                            f".//img[@src=\"{img_el.get_attribute('src')}\"]",
                                        ):
                                            is_inside_quote = True
                                    except:
                                        pass  # Ignore StaleElement or other errors in fallback

                            if not is_inside_quote:
                                try:
                                    closest_ancestor_article_for_media = visual_container.find_element(
                                        By.XPATH,
                                        "ancestor::article[@data-testid='tweet'][1]",
                                    )
                                    if (
                                        closest_ancestor_article_for_media
                                        == article_element_to_process
                                    ):
                                        src = img_el.get_attribute("src")
                                        if src and src not in images_for_check:
                                            images_for_check.append(src)
                                            # print(f"DEBUG extract_tweets: ID {current_tweet_id_for_log}, Added image to check: {src}")
                                except (
                                    NoSuchElementException,
                                    StaleElementReferenceException,
                                ):
                                    continue
                        except StaleElementReferenceException:
                            continue
                        except Exception as e_img_inner:
                            print(
                                f"DEBUG extract_tweets: Error processing one image for {current_tweet_id_for_log}: {e_img_inner}"
                            )
                            continue

                except StaleElementReferenceException:
                    print(
                        f"DEBUG extract_tweets: Stale image elements check for ID {current_tweet_id_for_log}. Breaking."
                    )
                    consecutive_stale_errors_article_loop += 1
                    break
                except Exception as e_img_extract_outer_loop:
                    print(
                        f"DEBUG extract_tweets: Error during image extraction for ID {current_tweet_id_for_log}: {e_img_extract_outer_loop}"
                    )

                # 動画ポスター抽出
                try:
                    potential_video_player_containers = article_element_to_process.find_elements(
                        By.XPATH,
                        ".//div[(@data-testid='videoPlayer' or @data-testid='videoComponent' or @data-testid='communitynotesVideo' or contains(@data-testid, 'playerInstance'))]",
                    )
                    for player_container_el in potential_video_player_containers:
                        try:
                            if not player_container_el.is_displayed():
                                continue

                            video_elements_in_container = (
                                player_container_el.find_elements(
                                    By.XPATH, ".//video[@poster]"
                                )
                            )
                            for video_el in video_elements_in_container:
                                is_inside_quote_video = False
                                if quote_container_in_this_article:
                                    try:
                                        is_inside_quote_video = driver.execute_script(
                                            "return arguments[0].contains(arguments[1]);",
                                            quote_container_in_this_article,
                                            player_container_el,
                                        )
                                    except Exception:  # Fallback
                                        try:
                                            if quote_container_in_this_article.find_elements(
                                                By.XPATH,
                                                f".//video[@poster=\"{video_el.get_attribute('poster')}\"]",
                                            ):
                                                is_inside_quote_video = True
                                        except:
                                            pass

                                if not is_inside_quote_video:
                                    try:
                                        closest_ancestor_article_for_media = player_container_el.find_element(
                                            By.XPATH,
                                            "ancestor::article[@data-testid='tweet'][1]",
                                        )
                                        if (
                                            closest_ancestor_article_for_media
                                            == article_element_to_process
                                        ):
                                            poster = video_el.get_attribute("poster")
                                            if poster and not any(
                                                vp_check.endswith(
                                                    poster.split("/")[-1].split("?")[0]
                                                )
                                                for vp_check in videos_for_check
                                            ):
                                                videos_for_check.append(poster)
                                                # print(f"DEBUG extract_tweets: ID {current_tweet_id_for_log}, Added video poster: {poster}")
                                    except (
                                        NoSuchElementException,
                                        StaleElementReferenceException,
                                    ):
                                        continue
                        except StaleElementReferenceException:
                            continue
                        except Exception as e_vid_inner:
                            print(
                                f"DEBUG extract_tweets: Error processing one video container for {current_tweet_id_for_log}: {e_vid_inner}"
                            )
                            continue

                except StaleElementReferenceException:
                    print(
                        f"DEBUG extract_tweets: Stale video elements check for ID {current_tweet_id_for_log}. Breaking."
                    )
                    consecutive_stale_errors_article_loop += 1
                    break
                except Exception as e_vid_extract_outer_loop:
                    print(
                        f"DEBUG extract_tweets: Error during video extraction for ID {current_tweet_id_for_log}: {e_vid_extract_outer_loop}"
                    )

                # print(f"DEBUG extract_tweets: Final media for ID {current_tweet_id_for_log} -> Images: {len(images_for_check)}, Videos: {len(videos_for_check)}")

                if is_ad_post(text):
                    seen_urls_in_current_call.add(tweet_url)
                    continue

                if is_reply_structure(
                    article_element_to_process,
                    tweet_id=current_tweet_id_for_log,
                    text=text,
                    image_urls=images_for_check,
                    video_poster_urls=videos_for_check,
                ):
                    seen_urls_in_current_call.add(tweet_url)
                    continue

                tweet_urls.append({"url": tweet_url, "id": current_tweet_id_for_log})
                seen_urls_in_current_call.add(tweet_url)
                new_tweets_found_in_scroll += 1
                consecutive_stale_errors_article_loop = 0

                print(f"✅ 収集候補に追加: {tweet_url} ({len(tweet_urls)}件目)")
                if len(tweet_urls) >= url_collection_limit:
                    break

            except StaleElementReferenceException:
                print(
                    f"⚠️ StaleElementReferenceException発生 (Article {i}, ID: {current_tweet_id_for_log}, URL: {current_tweet_url_for_log})。このスクロールでの処理を再試行します。"
                )
                consecutive_stale_errors_article_loop += 1
                if (
                    consecutive_stale_errors_article_loop
                    >= MAX_CONSECUTIVE_STALE_ERRORS_IN_SCROLL
                ):
                    print(
                        f"🚫 1スクロール内でStaleエラーが{MAX_CONSECUTIVE_STALE_ERRORS_IN_SCROLL}回連続。このスクロール処理を中断。"
                    )
                break
            except Exception as e_article_loop_main:
                print(
                    f"⚠️ 投稿抽出ループ内エラー (Article {i}, ID: {current_tweet_id_for_log}, URL: {current_tweet_url_for_log}): {type(e_article_loop_main).__name__} - {e_article_loop_main}"
                )
                continue

        if (
            consecutive_stale_errors_article_loop
            >= MAX_CONSECUTIVE_STALE_ERRORS_IN_SCROLL
        ):
            print(
                f"DEBUG extract_tweets: Exiting inner article loop for scroll {scroll_count + 1} due to repeated stale errors."
            )
            consecutive_stale_errors_article_loop = 0

        if len(tweet_urls) >= url_collection_limit:
            print(
                f"🎯 収集候補数が上限 ({url_collection_limit}) に達したため、URL収集を終了。"
            )
            break

        if new_tweets_found_in_scroll == 0 and scroll_count > 0:
            pause_counter += 1
            print(
                f"🧊 このスクロールで新規投稿なし → pause_counter={pause_counter}/{pause_threshold}"
            )
            # 元のロジックに戻す: 一定数以上の投稿URLが集まっている場合のみ中断
            if pause_counter >= pause_threshold and len(tweet_urls) >= (
                url_collection_limit / 2
            ):
                print("🛑 新しい投稿が連続して検出されないためURL収集を中断")
                break
        else:
            pause_counter = 0

        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
        except Exception as e_scroll_exec:
            print(f"⚠️ スクロール実行中にエラー: {e_scroll_exec}")
            break

        scroll_count += 1

    print(f"\n📈 収集候補のURL取得完了 → 合計: {len(tweet_urls)} 件")
    tweet_urls.sort(key=lambda x: int(x.get("id", 0)), reverse=True)

    # URLを収集した後、IDを抽出して既に処理済みのIDをフィルタリング
    collected_urls_filtered = []
    for url in tweet_urls:
        tweet_id = re.search(r"/status/(\d+)", url["url"])
        if tweet_id and tweet_id.group(1) not in globally_processed_ids:
            collected_urls_filtered.append(url)
        else:
            print(
                f"🚫 重複ID検出: {tweet_id.group(1) if tweet_id else 'unknown'} - スキップします"
            )

    return collected_urls_filtered  # フィルタリング済みのURLリストを返す


def already_registered(tweet_id, database_id_to_check, notion_client_instance):
    if not tweet_id or not str(tweet_id).isdigit() or not database_id_to_check:
        print(
            f"ℹ️ already_registered: 無効な引数 (tweet_id: {tweet_id}, db_id: {database_id_to_check})"
        )
        return False  # 不正なIDの場合は未登録扱いの方が安全か、エラーにするか

    query_filter = {"property": "投稿ID", "rich_text": {"equals": str(tweet_id)}}

    try:
        # print(f"🔍 DB登録確認: Tweet ID {tweet_id} in DB {database_id_to_check}")
        result = notion_client_instance.databases.query(
            database_id=database_id_to_check, filter=query_filter
        )
        num_results = len(result.get("results", []))
        # if num_results > 0:
        #     print(f"Found {num_results} existing entries for Tweet ID {tweet_id} in DB {database_id_to_check}")
        return num_results > 0
    except Exception as e:
        print(
            f"⚠️ Notionクエリ失敗 (DB登録確認): DB {database_id_to_check}, ID {tweet_id}"
        )
        print(f"   エラー詳細: {type(e).__name__} - {e}")
        return False  # クエリ失敗時は未登録として扱う（再試行の機会を与える）


def ocr_and_remove_image(image_path, label=None):
    """
    画像パスを受け取りOCRし、使用後に削除する。
    labelがあれば結果の先頭に付与。
    """
    result = ""
    try:
        ocr_result = ocr_image(image_path)
        if ocr_result:
            cleaned = clean_ocr_text(ocr_result)
            result = f"[{label}]\n{cleaned}" if label else cleaned
    except Exception as e:
        print(f"⚠️ OCR失敗: {e}")
    finally:
        try:
            os.remove(image_path)
            print(f"🗑️ 画像削除: {image_path}")
        except Exception as e:
            print(f"⚠️ 画像削除失敗: {e}")
    return result


def clean_ocr_text(text):
    # 除外したい文言やパターンをここに追加
    EXCLUDE_PATTERNS = [
        "朝質問を「いいね!」 する",
        "この投稿をいいね！",
        # 必要に応じて追加
    ]
    lines = text.splitlines()
    cleaned = [
        line for line in lines if not any(pat in line for pat in EXCLUDE_PATTERNS)
    ]
    return "\n".join(cleaned)


def get_all_registered_ids_from_db(
    database_id, notion_client, db_type_for_log="unknown"
):
    """指定されたNotionデータベースから全ての「投稿ID」を取得する（ページネーション対応）"""
    if not database_id:
        print(
            f"⚠️ get_all_registered_ids_from_db: database_id (type: {db_type_for_log}) が指定されていません。"
        )
        return set()

    all_ids = set()
    has_more = True
    start_cursor = None
    page_count = 0
    print(f"🔄 DB ({db_type_for_log}) から既存の投稿IDを取得開始: {database_id}")

    while has_more:
        try:
            page_count += 1
            print(f"  📄 ページ {page_count} を取得中...")
            response = notion_client.databases.query(
                database_id=database_id,
                filter={
                    "property": "投稿ID",  # "処理済み投稿IDデータベース" の場合はこれが Title プロパティ
                    "rich_text": {"is_not_empty": True},
                },
                page_size=100,
                start_cursor=start_cursor,
            )
            results = response.get("results", [])
            for item in results:
                properties = item.get("properties", {})
                # "処理済み投稿IDデータベース" の場合、Titleプロパティが投稿IDを保持すると想定
                post_id_prop_key = "投稿ID"  # これはTitleプロパティの名前を指す

                post_id_prop = properties.get(post_id_prop_key, {})

                # Titleプロパティの場合の処理
                if post_id_prop.get("type") == "title":
                    title_array = post_id_prop.get("title", [])
                    if title_array:
                        tweet_id_val = title_array[0].get("plain_text")
                        if tweet_id_val and tweet_id_val.isdigit():
                            all_ids.add(tweet_id_val)
                # 従来の rich_text プロパティの場合の処理 (後方互換性のため残す)
                elif post_id_prop.get("type") == "rich_text":
                    rich_text_array = post_id_prop.get("rich_text", [])
                    if rich_text_array:
                        tweet_id_val = rich_text_array[0].get("plain_text")
                        if tweet_id_val and tweet_id_val.isdigit():
                            all_ids.add(tweet_id_val)
                else:
                    # "投稿ID" という名前のプロパティが title でも rich_text でもない場合
                    # または、キーが異なる場合は、ログを出してスキップ
                    # print(f"DEBUG: DB {database_id}, item {item.get('id')}, '投稿ID' property is not title or rich_text, or key is different. Type: {post_id_prop.get('type')}")
                    pass

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")
            if has_more:
                print(f"  ...さらにページあり (取得済みID数: {len(all_ids)})")
                time.sleep(0.5)
        except Exception as e:
            print(
                f"❌ DB ({db_type_for_log}) からのID取得中にエラー (DB: {database_id}, Page: {page_count}): {e}"
            )
            print(
                f"   現在の取得済みID数: {len(all_ids)}。このDBのID取得を中断します。"
            )
            break
    print(
        f"✅ DB ({db_type_for_log}) からのID取得完了: {database_id}, 合計 {len(all_ids)} 件"
    )
    return all_ids


def add_to_processed_ids_db(
    notion_client,
    processed_db_id,
    post_id,
    processing_type,
    parent_post_id=None,
    url=None,
):
    if not processed_db_id:
        print("⚠️ 処理済みID DBのIDが未設定のため、登録をスキップします。")
        return False
    if not post_id:
        print("⚠️ 処理済みとして登録する投稿IDがありません。")
        return False

    props = {
        "投稿ID": {"title": [{"type": "text", "text": {"content": str(post_id)}}]},
        "処理タイプ": {"select": {"name": processing_type}},
        "処理日時": {"date": {"start": datetime.now().isoformat()}},
    }
    if parent_post_id:
        props["親投稿ID"] = {
            "rich_text": [{"type": "text", "text": {"content": str(parent_post_id)}}]
        }
    if url:
        props["URL"] = {"url": url}

    try:
        notion_client.pages.create(
            parent={"database_id": processed_db_id}, properties=props
        )
        print(
            f"✅ 処理済みID DB登録: ID={post_id}, タイプ={processing_type}, 親ID={parent_post_id if parent_post_id else 'N/A'}, URL={url if url else 'N/A'}"
        )
        return True
    except Exception as e:
        print(f"❌ 処理済みID DB登録失敗: ID={post_id}, タイプ={processing_type} - {e}")
        return False


def upload_to_notion(
    tweet, config, notion_client, registered_ids_map, processed_post_ids_db_id
):
    print(f"📤 Notion登録準備開始: {tweet.get('id', 'ID不明')}")

    # 1. GPT処理用の入力ファイルを作成
    ocr_texts_for_gpt = []
    temp_image_paths_for_gpt_ocr = []  # GPT OCR処理後に削除する一時画像パスのリスト

    # tweet辞書内の画像URLから一時画像をダウンロードしてOCR
    for idx, img_url in enumerate(tweet.get("images", [])):
        img_filename = f"temp_ocr_image_for_gpt_{tweet.get('id', 'unknown')}_{idx}.jpg"
        temp_ocr_image_dir = "temp_ocr_images"  # 一時画像保存ディレクトリ
        if not os.path.exists(temp_ocr_image_dir):
            os.makedirs(temp_ocr_image_dir, exist_ok=True)
        img_path_temp = os.path.join(temp_ocr_image_dir, img_filename)
        temp_image_paths_for_gpt_ocr.append(img_path_temp)  # 削除リストに追加

        try:
            print(f"Downloading image for GPT OCR: {img_url} to {img_path_temp}")
            resp = requests.get(
                img_url, stream=True, timeout=20
            )  # タイムアウトを少し長めに
            resp.raise_for_status()
            with open(img_path_temp, "wb") as f:
                for chunk in resp.iter_content(8192):  # チャンクサイズ調整
                    f.write(chunk)
            raw_ocr_text = ocr_image(
                img_path_temp
            )  # ocr_image は内部でエラー処理を持つ想定
            if raw_ocr_text and raw_ocr_text.strip() and raw_ocr_text != "[OCRエラー]":
                ocr_texts_for_gpt.append(f"[画像{idx+1}]\n{raw_ocr_text.strip()}")
            else:
                print(
                    f"ℹ️ 画像{idx+1}のOCR結果が空またはエラーのためスキップ (URL: {img_url})"
                )
        except requests.exceptions.RequestException as e_req:
            print(f"⚠️ 画像ダウンロード失敗 (GPT用): {img_url}, {e_req}")
        except Exception as e_ocr_prep:
            print(f"⚠️ GPT用OCR準備エラー (画像{idx+1}): {e_ocr_prep}")

    # tweet辞書内の動画ポスターパスからOCR (これはローカルパスのはず)
    poster_paths_from_tweet = tweet.get("video_posters", [])
    if isinstance(poster_paths_from_tweet, str):  # 単一パスの場合もリストとして扱う
        poster_paths_from_tweet = [poster_paths_from_tweet]

    for idx, poster_path in enumerate(poster_paths_from_tweet):
        if os.path.exists(poster_path):  # ローカルパスの存在確認
            print(f"Processing video poster for GPT OCR: {poster_path}")
            raw_ocr_text = ocr_image(poster_path)
            if raw_ocr_text and raw_ocr_text.strip() and raw_ocr_text != "[OCRエラー]":
                ocr_texts_for_gpt.append(
                    f"[動画サムネイル{idx+1}]\n{raw_ocr_text.strip()}"
                )
            else:
                print(
                    f"ℹ️ 動画サムネイル{idx+1}のOCR結果が空またはエラーのためスキップ (Path: {poster_path})"
                )
            # 動画ポスターは extract_thread_from_detail_page で一時保存され、
            # その関数または呼び出し元で削除される想定なので、ここでは削除リストに追加しない
        else:
            print(f"⚠️ GPT用動画サムネイルパス見つからず: {poster_path}")

    combined_ocr_for_gpt = "\n\n".join(ocr_texts_for_gpt).strip()
    if not combined_ocr_for_gpt:
        print("ℹ️ GPT用のOCR対象テキストがありませんでした。")

    data_for_gpt_file = {
        "post_text": tweet.get("text", ""),
        "ocr_text": combined_ocr_for_gpt,
    }
    gpt_input_filename = "tweet_for_gpt.json"
    try:
        with open(gpt_input_filename, "w", encoding="utf-8") as f_out_gpt:
            json.dump(data_for_gpt_file, f_out_gpt, ensure_ascii=False, indent=2)
        print(
            f"📝 GPT用データを {gpt_input_filename} に保存しました (ID: {tweet.get('id', 'N/A')})"
        )
    except Exception as e_save_json:
        print(f"❌ GPT用データ {gpt_input_filename} の保存に失敗: {e_save_json}")
        # 一時画像があれば削除
        for temp_path in temp_image_paths_for_gpt_ocr:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        return "FAILED"

    gpt_output_filename = "gpt_output.json"
    gpt_runner_script_path = (
        "gpt_prompt_runner.py"  # config.json から読み込むようにしても良い
    )
    if os.path.exists(gpt_output_filename):
        try:
            os.remove(gpt_output_filename)
        except OSError as e:
            print(f"⚠️ 既存の {gpt_output_filename} の削除に失敗しました: {e}")

    try:
        print(f"🚀 gpt_prompt_runner.py を実行します...")
        python_executable = shutil.which("python3") or shutil.which(
            "python"
        )  # 環境に合わせて
        if not python_executable:
            print("❌ Python実行可能ファイルが見つかりません。")
            for temp_path in temp_image_paths_for_gpt_ocr:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
            return "FAILED"

        process_result = subprocess.run(
            [python_executable, gpt_runner_script_path],
            check=True,  # エラー時に CalledProcessError を発生させる
            capture_output=True,
            text=True,
            encoding="utf-8",  # 明示的にエンコーディング指定
            timeout=300,  # タイムアウト設定 (秒)
        )
        print(f"✅ gpt_prompt_runner.py 実行完了。")
        if process_result.stdout:
            print(f"   Stdout:\n{process_result.stdout.strip()}")
        if process_result.stderr:  # 標準エラーも確認
            print(f"   Stderr:\n{process_result.stderr.strip()}")

    except FileNotFoundError:
        print(f"❌ エラー: {gpt_runner_script_path} が見つかりません。")
        for temp_path in temp_image_paths_for_gpt_ocr:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        return "FAILED"
    except subprocess.CalledProcessError as e:
        print(
            f"❌ gpt_prompt_runner.py の実行中にエラーが発生しました (終了コード: {e.returncode}):"
        )
        if e.stdout:
            print(f"   Stdout: {e.stdout.strip()}")
        if e.stderr:
            print(f"   Stderr: {e.stderr.strip()}")
        for temp_path in temp_image_paths_for_gpt_ocr:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        return "FAILED"
    except subprocess.TimeoutExpired:
        print(f"❌ gpt_prompt_runner.py の実行がタイムアウトしました。")
        for temp_path in temp_image_paths_for_gpt_ocr:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        return "FAILED"
    except Exception as e_subproc:  # その他の予期せぬエラー
        print(f"❌ gpt_prompt_runner.py の実行中に予期せぬエラー: {e_subproc}")
        for temp_path in temp_image_paths_for_gpt_ocr:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        return "FAILED"
    finally:
        # GPT OCR用の一時画像を削除
        for path_to_delete in temp_image_paths_for_gpt_ocr:
            if os.path.exists(path_to_delete):
                try:
                    os.remove(path_to_delete)
                except Exception as e_del_temp:
                    print(f"⚠️ GPT用一時画像削除失敗: {path_to_delete}, {e_del_temp}")
        # 一時画像ディレクトリが空なら削除
        if (
            "temp_ocr_image_dir" in locals()
            and os.path.exists(temp_ocr_image_dir)
            and not os.listdir(temp_ocr_image_dir)
        ):
            try:
                os.rmdir(temp_ocr_image_dir)
            except OSError:  # 他のプロセスが掴んでいる場合など
                pass

    # 2. GPTの出力を読み込み、Notion登録用のプロパティを作成
    gpt_classification = "不明"
    gpt_formatted_ocr = (
        combined_ocr_for_gpt  # GPTが整形テキストを返さなかった場合のフォールバック
    )

    if not os.path.exists(gpt_output_filename):
        print(
            f"⚠️ {gpt_output_filename} が生成されませんでした。GPT処理に失敗した可能性があります。"
        )
    else:
        try:
            with open(gpt_output_filename, "r", encoding="utf-8") as f_gpt_res:
                gpt_result = json.load(f_gpt_res)
                gpt_classification = gpt_result.get("classification", "不明")
                gpt_formatted_ocr_from_gpt = gpt_result.get("formatted_text")
                if gpt_formatted_ocr_from_gpt is not None:  # Noneでない場合のみ上書き
                    gpt_formatted_ocr = gpt_formatted_ocr_from_gpt
                print(
                    f"📊 GPT判定結果: 分類='{gpt_classification}', 整形後OCR提供あり='{gpt_formatted_ocr_from_gpt is not None}'"
                )
        except json.JSONDecodeError:
            print(
                f"⚠️ {gpt_output_filename} のJSON形式が正しくありません。整形前OCRとデフォルト分類を使用します。"
            )
        except Exception as e_load_gpt_out:
            print(
                f"⚠️ {gpt_output_filename} の読み込みエラー: {e_load_gpt_out}。整形前OCRとデフォルト分類を使用します。"
            )

    target_database_id = None
    db_key_for_ids_map = None  # registered_ids_map のどのキーに対応するか
    if gpt_classification == "質問回答":
        target_database_id = config.get("database_id_question")
        db_key_for_ids_map = "question"  # main関数でのキーと合わせる
    elif gpt_classification == "案件投稿":
        target_database_id = config.get("database_id_project")
        db_key_for_ids_map = "project"  # main関数でのキーと合わせる
    else:  # "スルーデータ" や "不明" など、登録対象外の分類
        print(
            f"ℹ️ GPT分類 '{gpt_classification}' は登録対象外です。スキップします。Tweet ID: {tweet.get('id')}"
        )
        # 処理済みDBへの登録もスキップ（分類で除外されたため）
        return "SKIPPED_CLASSIFICATION"

    if (
        not target_database_id
    ):  # "質問回答" or "案件投稿" に分類されたが、configにDB IDがなかった場合
        print(
            f"❌ 設定エラー: 分類 '{gpt_classification}' に対応するDB IDがconfig.jsonに設定されていません。Tweet ID: {tweet.get('id')}"
        )
        return "FAILED_CONFIG"

    current_tweet_id_str = str(tweet.get("id"))

    # 登録済みチェック:
    # まず、対象のDB (質問DB or 案件DB) に既に登録されているかを確認
    # registered_ids_map["question"] や registered_ids_map["project"] を参照
    if db_key_for_ids_map and current_tweet_id_str in registered_ids_map.get(
        db_key_for_ids_map, set()
    ):
        print(
            f"🚫 スキップ (対象DB '{db_key_for_ids_map}' で登録済確認): {current_tweet_id_str}"
        )
        return "SKIPPED_REGISTERED"

    # 次に、グローバルな処理済みIDセット (全DBのIDを統合したもの) でも確認
    # これにより、例えば過去に案件DBに登録されたものが、今回質問DBの候補になった場合などを防ぐ
    if current_tweet_id_str in registered_ids_map.get("all_processed", set()):
        print(f"🚫 スキップ (グローバル処理済みIDリストで確認): {current_tweet_id_str}")
        # この場合も、既にどこかで処理されているので、処理済みDBへの再登録は不要
        return "SKIPPED_REGISTERED"

    # Notionプロパティの準備
    tweet_id_str = str(tweet.get("id", ""))  # 念のため再取得・文字列化
    props = {
        "投稿ID": {
            "rich_text": (
                [{"type": "text", "text": {"content": tweet_id_str}}]
                if tweet_id_str
                else None
            )
        },
        "本文": {
            "rich_text": [{"type": "text", "text": {"content": tweet.get("text", "")}}]
        },
        "URL": {"url": tweet.get("url")},
        "投稿日時": {
            "date": {"start": tweet.get("date")} if tweet.get("date") else None
        },
        "ステータス": {"select": {"name": "未回答"}},  # デフォルトステータス
        "インプレッション数": {
            "number": (
                int(tweet["impressions"])
                if tweet.get("impressions") is not None
                and str(tweet.get("impressions")).isdigit()
                else None
            )
        },
        "リポスト数": {
            "number": (
                int(tweet["retweets"])
                if tweet.get("retweets") is not None
                and str(tweet.get("retweets")).isdigit()
                else 0
            )
        },
        "いいね数": {
            "number": (
                int(tweet["likes"])
                if tweet.get("likes") is not None and str(tweet.get("likes")).isdigit()
                else 0
            )
        },
        "ブックマーク数": {
            "number": (
                int(tweet["bookmarks"])
                if tweet.get("bookmarks") is not None
                and str(tweet.get("bookmarks")).isdigit()
                else 0
            )
        },
        "リプライ数": {
            "number": (
                int(tweet["replies"])
                if tweet.get("replies") is not None
                and str(tweet.get("replies")).isdigit()
                else 0
            )
        },
        "文字起こし": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": gpt_formatted_ocr if gpt_formatted_ocr else ""},
                }
            ]
        },
    }
    # None の値を持つプロパティを除外 (Notion APIがエラーを返すことがあるため)
    props = {k: v for k, v in props.items() if v is not None}
    # "投稿日時" がNoneの場合、dateプロパティ自体を削除
    if props.get("投稿日時") and not props["投稿日時"]["date"]["start"]:
        props.pop("投稿日時")

    children_blocks = []  # 必要であればページコンテンツブロックを追加

    try:
        print(
            f"📤 Notionへ登録実行中... DB ID: {target_database_id}, Tweet ID: {tweet_id_str}"
        )
        new_page = notion_client.pages.create(
            parent={"database_id": target_database_id},
            properties=props,
            children=children_blocks,
        )
        print(f"✅ Notion登録完了 (DB: {target_database_id}): {tweet.get('url')}")

        # 登録成功したら、メモリ上のIDセットも更新
        if db_key_for_ids_map and current_tweet_id_str:
            registered_ids_map.setdefault(db_key_for_ids_map, set()).add(
                current_tweet_id_str
            )
        # グローバル処理済みIDセットも更新
        registered_ids_map.setdefault("all_processed", set()).add(current_tweet_id_str)

        # 「処理済み投稿IDデータベース」にも記録
        # 親投稿の場合
        add_to_processed_ids_db(
            notion_client,
            processed_post_ids_db_id,
            current_tweet_id_str,
            "親投稿",
            url=tweet.get("url"),
        )

        # マージされたリプライIDも処理済みDBに記録
        merged_reply_ids_list = tweet.get("merged_reply_ids", [])
        if isinstance(
            merged_reply_ids_list, str
        ):  # 文字列で渡された場合（カンマ区切りなど）はリストに変換
            merged_reply_ids_list = [
                rid.strip()
                for rid in merged_reply_ids_list.split(",")
                if rid.strip() and rid.strip().isdigit()
            ]

        for reply_id in merged_reply_ids_list:
            if reply_id and str(reply_id).isdigit():  # 数値であることも確認
                # マージされたリプライが既にグローバル処理済みセットになければ追加
                if str(reply_id) not in registered_ids_map.get("all_processed", set()):
                    # 親投稿のURLをベースにリプライ固有のURLを構築
                    parent_url = tweet.get("url", "")
                    reply_url = ""

                    if parent_url:
                        # 親URLからユーザー名部分を抽出
                        username_match = re.search(
                            r"(?:twitter|x)\.com/([^/]+)/status/", parent_url
                        )
                        if username_match:
                            username = username_match.group(1)
                            # リプライ固有のURLを構築
                            reply_url = f"https://x.com/{username}/status/{reply_id}"

                    # 親投稿のURLをマージ済みリプライにも保存
                    add_to_processed_ids_db(
                        notion_client,
                        processed_post_ids_db_id,
                        str(reply_id),
                        "マージ済みリプライ",
                        parent_post_id=current_tweet_id_str,
                        url=reply_url,
                    )
                    registered_ids_map.setdefault("all_processed", set()).add(
                        str(reply_id)
                    )
                else:
                    print(
                        f"ℹ️ マージ対象リプライ {reply_id} は既にグローバル処理済みリストに存在するため、処理済みDBへの重複登録をスキップ。"
                    )

        return "SUCCESS"
    except Exception as e:
        print(f"❌ Notion登録失敗 (DB: {target_database_id}): Tweet ID {tweet_id_str}")
        print(f"   エラー詳細: {type(e).__name__} - {e}")
        # traceback.print_exc() # 詳細なトレースバックが必要な場合
        return "FAILED"


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_recruit_account(name, bio, config):
    return any(
        k in name or k in bio for k in config.get("filter_keywords_name_bio", [])
    )


def is_recruit_post(text, config):
    return any(k in text for k in config.get("filter_keywords_tweet", []))


def search_accounts(driver, keyword_list):
    results = []
    for keyword in keyword_list:
        search_url = f"https://twitter.com/search?q={keyword}&f=user"
        driver.get(search_url)
        time.sleep(3)

        # ⚠ 新UI構造に対応
        users = driver.find_elements(
            By.XPATH, "//a[contains(@href, '/')]//div[@dir='auto']/../../.."
        )
        print(f"🔍 候補ユーザー件数: {len(users)}")

        for user in users:
            try:
                spans = user.find_elements(By.XPATH, ".//span")
                name = ""
                username = ""

                for span in spans:
                    text = span.text.strip()
                    if text.startswith("@"):
                        username = text.replace("@", "")
                    elif not name:
                        name = text

                if username and name:
                    results.append(
                        {
                            "name": name,
                            "username": username,
                            "bio": "",  # この段階ではプロフィール画面に飛んでいない
                        }
                    )
            except Exception as e:
                print(f"⚠️ ユーザー情報抽出失敗: {e}")
                continue

    return results


def merge_replies_with_driver(driver, tweet):
    try:
        driver.get(tweet["url"])
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//article[@data-testid='tweet']")
            )
        )

        replies = extract_self_replies(driver, tweet.get("username", ""))
        if not isinstance(replies, list):
            print(
                f"⚠️ merge_replies_with_driver() で取得したrepliesが不正な型: {type(replies)} → 空リストに置換"
            )
            replies = []

        tweet_text = tweet.get("text") or ""
        replies = sorted(
            [r for r in replies if r.get("id") and r.get("text")],
            key=lambda x: int(x["id"]),
        )

        existing_chunks = set(tweet_text.strip().split("\n\n"))
        reply_texts = []

        for r in replies:
            # 画像・動画・card_img付きリプライは親にマージしない
            if r.get("images") or r.get("video_posters"):
                print(
                    f"🛑 画像・動画・card_img付きリプライは親にマージしません: {r['id']}"
                )
                continue

            reply_id = r["id"]
            reply_body = r["text"].strip()
            clean_body = reply_body[:20].replace("\n", " ")
            print(f"🧵 リプライ統合候補: ID={reply_id} | text先頭: {clean_body}")

            if not reply_body:
                continue
            if reply_body in existing_chunks:
                continue
            if r["id"] == tweet["id"]:
                continue

            reply_texts.append(reply_body)
            existing_chunks.add(reply_body)

        if reply_texts:
            tweet["text"] = tweet_text + "\n\n" + "\n\n".join(reply_texts)

    except Exception as e:
        print(f"⚠️ リプライ統合失敗（{tweet.get('url', '不明URL')}）: {e}")
    return tweet


def extract_from_search(driver, keywords, max_tweets, name_bio_keywords=None):
    tweets = []
    seen_urls = set()
    seen_users = set()

    for keyword in keywords:
        print(f"🔍 話題のツイート検索中: {keyword}")
        search_url = f"https://twitter.com/search?q={keyword}&src=typed_query&f=top"
        driver.get(search_url)
        time.sleep(3)

        scroll_count = 0
        max_scrolls = 10
        pause_counter = 0
        pause_threshold = 3
        last_article_count = 0

        while len(tweets) < max_tweets and scroll_count < max_scrolls:
            articles = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
            article_count = len(articles)
            print(f"📄 表示中のツイート数: {article_count}")
            for article in articles:
                try:
                    # ツイートURLとユーザー名取得
                    time_el = article.find_element(By.XPATH, ".//time")
                    tweet_href = time_el.find_element(By.XPATH, "..").get_attribute(
                        "href"
                    )
                    tweet_url = (
                        tweet_href
                        if tweet_href.startswith("http")
                        else f"https://x.com{tweet_href}"
                    )
                    if tweet_url in seen_urls:
                        continue
                    seen_urls.add(tweet_url)

                    name_block = article.find_element(
                        By.XPATH, ".//div[@data-testid='User-Name']"
                    )
                    spans = name_block.find_elements(By.XPATH, ".//span")
                    display_name = ""
                    username = ""
                    for s in spans:
                        text = s.text.strip()
                        if text.startswith("@"):
                            username = text.replace("@", "")
                        elif not display_name:
                            display_name = text

                    if not username or username in seen_users:
                        continue
                    seen_users.add(username)

                    # bioフィルタがある場合はプロフィールへ先にアクセス
                    if name_bio_keywords:
                        driver.execute_script("window.open('');")
                        driver.switch_to.window(driver.window_handles[-1])
                        driver.get(f"https://twitter.com/{username}")
                        time.sleep(2)
                        try:
                            bio_text = (
                                WebDriverWait(driver, 5)
                                .until(
                                    EC.presence_of_element_located(
                                        (
                                            By.XPATH,
                                            "//div[@data-testid='UserDescription']",
                                        )
                                    )
                                )
                                .text
                            )
                        except:
                            bio_text = ""
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])

                        if not any(
                            k in display_name for k in name_bio_keywords
                        ) and not any(k in bio_text for k in name_bio_keywords):
                            print(f"❌ フィルタ非一致 → スキップ: @{username}")
                            continue

                    # ✅ 条件を通過した場合のみ投稿詳細ページにアクセスして抽出
                    driver.execute_script("window.open('');")
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.get(tweet_url)
                    WebDriverWait(driver, 10).until(EC.url_contains("/status/"))

                    try:
                        full_text_el = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located(
                                (By.XPATH, "//div[@data-testid='tweetText']")
                            )
                        )
                        text = full_text_el.text.strip()
                    except Exception as e:
                        print(f"⚠️ 本文取得失敗: {e}")
                        text = ""

                    # 投稿日時取得（安定化 + スクロール + セレクタ強化）
                    # 投稿日時取得（詳細ページ内、エラー回避・多段構造に対応）
                    date = ""
                    for attempt in range(5):
                        try:
                            driver.execute_script("window.scrollTo(0, 0);")
                            WebDriverWait(driver, 3).until(
                                EC.presence_of_element_located((By.XPATH, "//article"))
                            )
                            time_el = driver.find_element(By.XPATH, "//article//a/time")
                            if time_el:
                                date = time_el.get_attribute("datetime")
                                break
                        except Exception as e:
                            print(f"⚠️ 投稿日時取得試行 {attempt+1}/5 失敗: {e}")
                            time.sleep(1)

                    if not date:
                        print("⚠️ 投稿日時取得に失敗 → 空文字で継続")

                    # 自リプライ取得（省略可）
                    replies = extract_self_replies(driver, username)
                    if replies:
                        reply_texts = [
                            r["text"]
                            for r in replies
                            if "text" in r and r["text"] not in text
                        ]
                        if reply_texts:
                            text += "\n\n" + "\n\n".join(reply_texts)

                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

                    tweet_id = re.sub(r"\D", "", tweet_url.split("/")[-1])
                    if already_registered(tweet_id):
                        print(f"🚫 登録済 → スキップ: {tweet_url}")
                        continue

                    tweets.append(
                        {
                            "url": tweet_url,
                            "text": text,
                            "date": date,
                            "id": tweet_id,
                            "username": username,
                            "display_name": display_name,
                        }
                    )

                    print(f"✅ 収集: {tweet_url} @{username}")
                    if len(tweets) >= max_tweets:
                        break

                except Exception as e:
                    print(f"⚠️ 投稿抽出エラー: {e}")
                    continue

            # スクロール実行
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

            # 読み込み判定
            if article_count == last_article_count:
                pause_counter += 1
                print("🧊 スクロール後に新しい投稿なし")
                if pause_counter >= pause_threshold:
                    print("🛑 投稿が増えないため中断")
                    break
            else:
                pause_counter = 0

            last_article_count = article_count
            scroll_count += 1

    return tweets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json", help="設定ファイル（JSON）")
    parser.add_argument(
        "--accounts", default="accounts.json", help="アカウント情報ファイル（JSON）"
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"❌ 設定ファイル {args.config} が見つかりません。")
        return
    except json.JSONDecodeError:
        print(f"❌ 設定ファイル {args.config} のJSON形式が正しくありません。")
        return
    except Exception as e_conf_load:
        print(
            f"❌ 設定ファイル {args.config} の読み込み中に予期せぬエラー: {e_conf_load}"
        )
        return

    try:
        accounts_info = load_config(args.accounts)
    except FileNotFoundError:
        print(f"❌ アカウント情報ファイル {args.accounts} が見つかりません。")
        return
    except json.JSONDecodeError:
        print(
            f"❌ アカウント情報ファイル {args.accounts} のJSON形式が正しくありません。"
        )
        return
    except Exception as e_acc_load:
        print(
            f"❌ アカウント情報ファイル {args.accounts} の読み込み中に予期せぬエラー: {e_acc_load}"
        )
        return

    global TWITTER_EMAIL, TWITTER_USERNAME, TWITTER_PASSWORD
    global EXTRACT_TARGET

    notion_token = config.get("notion_token")
    TWITTER_EMAIL = accounts_info.get("email")
    TWITTER_USERNAME = accounts_info.get("username")
    TWITTER_PASSWORD = accounts_info.get("password")
    EXTRACT_TARGET = config.get("extract_target")
    max_tweets_to_register = config.get("max_tweets", 10)

    required_configs = {
        "Notion Token": notion_token,
        # EXTRACT_TARGET は mode によっては不要なので、ここでは必須としない
    }
    required_accounts_info = {
        "Twitter Email": TWITTER_EMAIL,
        "Twitter Username": TWITTER_USERNAME,
        "Twitter Password": TWITTER_PASSWORD,
    }

    missing_configs = [key for key, value in required_configs.items() if not value]
    if missing_configs:
        print(
            f"❌ {args.config}に必要な設定が不足しています: {', '.join(missing_configs)}"
        )
        return
    missing_accounts = [
        key for key, value in required_accounts_info.items() if not value
    ]
    if missing_accounts:
        print(
            f"❌ {args.accounts}に必要なアカウント情報が不足しています: {', '.join(missing_accounts)}"
        )
        return

    mode = config.get("mode", "target_only")
    if mode == "target_only" and not EXTRACT_TARGET:
        print(
            f"❌ mode 'target_only' が指定されていますが、{args.config} に 'extract_target' が設定されていません。"
        )
        return

    try:
        notion_client_main = Client(auth=notion_token)
    except Exception as e_notion_client:
        print(f"❌ Notionクライアントの初期化に失敗しました: {e_notion_client}")
        return

    registered_ids_map = {}
    db_id_question = config.get("database_id_question")
    db_id_project = config.get("database_id_project")
    db_id_processed_posts = config.get(
        "database_id_processed_posts"
    )  # 処理済み投稿DBのID

    all_processed_ids_set = set()  # 全てのDBから集めたIDを統合するセット

    if db_id_question:
        question_ids = get_all_registered_ids_from_db(
            db_id_question, notion_client_main, "question"
        )
        all_processed_ids_set.update(question_ids)
        registered_ids_map["question"] = question_ids  # 個別のDBのIDセットも保持
    else:
        print("⚠️ config.jsonに database_id_question が設定されていません。")
        registered_ids_map["question"] = set()

    if db_id_project:
        project_ids = get_all_registered_ids_from_db(
            db_id_project, notion_client_main, "project"
        )
        all_processed_ids_set.update(project_ids)
        registered_ids_map["project"] = project_ids  # 個別のDBのIDセットも保持
    else:
        print("⚠️ config.jsonに database_id_project が設定されていません。")
        registered_ids_map["project"] = set()

    if db_id_processed_posts:
        processed_ids_from_db = get_all_registered_ids_from_db(
            db_id_processed_posts, notion_client_main, "processed_posts"
        )
        all_processed_ids_set.update(processed_ids_from_db)
        # registered_ids_map["processed_posts"] = processed_ids_from_db # 必要ならこれも保持
    else:
        print(
            "⚠️ config.jsonに database_id_processed_posts (処理済み投稿ID DB) が設定されていません。"
        )
        print(
            "   このDBがない場合、過去にマージされたリプライ等の重複チェックが不完全になる可能性があります。"
        )

    registered_ids_map["all_processed"] = (
        all_processed_ids_set  # 統合したIDセットを格納
    )

    if not db_id_question and not db_id_project and not db_id_processed_posts:
        print(
            "❌ config.jsonに主要なデータベースID (question, project, processed_posts のいずれか) が設定されていません。処理を続行できません。"
        )
        return
    print(
        f"ℹ️ 全DBの既存IDリスト準備完了。合計ユニークID数: {len(all_processed_ids_set)}"
    )

    driver = None
    try:
        driver = setup_driver()
        login(driver, EXTRACT_TARGET if mode == "target_only" else None)

        chunk_fetch_size = config.get("chunk_fetch_size", 50)
        max_total_urls_to_process = config.get("max_total_urls_to_process", 300)
        iteration_delay_seconds = config.get("iteration_delay_seconds", 60)
        max_fetch_iterations = config.get("max_fetch_iterations", 5)

        all_collected_potential_tweets = []
        processed_tweet_ids_for_upload_loop = set()
        successfully_registered_count = 0
        total_urls_extracted_in_iterations = 0

        for iteration_num in range(max_fetch_iterations):
            if successfully_registered_count >= max_tweets_to_register:
                print(
                    f"🎯 目標登録数 ({max_tweets_to_register}件) に達したため、全処理を終了します。"
                )
                break

            print(
                f"\n🔄 イテレーション {iteration_num + 1}/{max_fetch_iterations} を開始します。"
            )
            print(
                f"   現在の登録成功数: {successfully_registered_count}/{max_tweets_to_register}"
            )
            print(
                f"   これまでに収集したURL総数: {total_urls_extracted_in_iterations}/{max_total_urls_to_process}"
            )
            print(
                f"   現在のグローバル処理済みID数 (all_processed_ids_set): {len(all_processed_ids_set)}"
            )

            if total_urls_extracted_in_iterations >= max_total_urls_to_process:
                print(
                    f"🚫 総収集試行URL数が上限 ({max_total_urls_to_process}) に達したため、URL収集を停止します。"
                )
                break

            num_urls_to_fetch_this_iteration = min(
                chunk_fetch_size,
                max_total_urls_to_process - total_urls_extracted_in_iterations,
            )

            if num_urls_to_fetch_this_iteration <= 0:
                print(
                    "   今回のイテレーションで収集するURL数が0以下です。URL収集をスキップします。"
                )
                if (
                    iteration_num < max_fetch_iterations - 1
                    and successfully_registered_count < max_tweets_to_register
                ):
                    print(f"   {iteration_delay_seconds}秒待機します...")
                    time.sleep(iteration_delay_seconds)
                continue

            print(
                f"   今回のイテレーションでのURL収集目標: {num_urls_to_fetch_this_iteration}件"
            )

            current_url_chunk_dicts = []
            if mode == "target_only":
                current_url_chunk_dicts = extract_tweets(
                    driver,
                    EXTRACT_TARGET,
                    num_urls_to_fetch_this_iteration,
                    all_processed_ids_set,
                    config,
                    remaining_needed=max_tweets_to_register
                    - successfully_registered_count,  # 残り必要数を渡す
                )
            else:
                print(f"❌ 未知または未対応のmode指定です: {mode}")
                break

            if not current_url_chunk_dicts:
                print(
                    f"   イテレーション {iteration_num + 1}: 新しいURLが収集できませんでした。"
                )
                if (
                    iteration_num < max_fetch_iterations - 1
                    and successfully_registered_count < max_tweets_to_register
                ):
                    print(f"   {iteration_delay_seconds}秒待機します...")
                    time.sleep(iteration_delay_seconds)
                continue

            total_urls_extracted_in_iterations += len(current_url_chunk_dicts)
            # current_url_chunk_dicts.reverse() # extract_tweets が新しい順に返すので、ここでは不要かも

            # ★★★ 変更点: extract_and_merge_tweets の戻り値の受け取り方を変える ★★★
            newly_processed_tweets_chunk, cycle_processed_ids = (
                extract_and_merge_tweets(
                    driver,
                    current_url_chunk_dicts,
                    max_tweets_to_register,
                    notion_client_main,
                    config,
                    registered_ids_map,  # ここに all_processed_ids_set が含まれている
                    current_success_count=successfully_registered_count,  # 現在の登録成功数を追加
                )
            )
            # ★★★ ここまで ★★★

            # ★★★ 修正: extract_and_merge_tweets で処理済みとされたIDをグローバルセットにすぐ追加しない ★★★
            # if cycle_processed_ids: # このブロックをコメントアウトまたは削除
            #     all_processed_ids_set.update(cycle_processed_ids)
            #     # registered_ids_map["all_processed"] も更新 (同一オブジェクトなので自動的に更新されるはずだが念のため)
            #     registered_ids_map["all_processed"] = all_processed_ids_set
            #     print(
            #         f"   DEBUG main: {len(cycle_processed_ids)} IDs from extract_and_merge_tweets added to all_processed_ids_set. New total: {len(all_processed_ids_set)}"
            #     )
            # ★★★ ここまで ★★★

            if newly_processed_tweets_chunk:
                # 既存の all_collected_potential_tweets と重複しないように追加
                # （ただし、IDベースでより厳密な重複排除が望ましい場合もある）
                # 現在は単純に追加しているが、extract_tweetsで収集したURLの時点である程度ユニークになっている想定
                unique_new_tweets = [
                    tweet
                    for tweet in newly_processed_tweets_chunk
                    if tweet.get("id") not in processed_tweet_ids_for_upload_loop
                ]
                all_collected_potential_tweets.extend(unique_new_tweets)
                print(
                    f"   newly_processed_tweets_chunk ({len(newly_processed_tweets_chunk)}件) のうち、unique {len(unique_new_tweets)} 件を処理候補に追加。"
                    f"現在の処理候補総数: {len(all_collected_potential_tweets)}件。"
                )

                # 処理候補リストを新しい順にソートし、長さを目標登録件数までに制限
                all_collected_potential_tweets.sort(
                    key=lambda x: (
                        int(x["id"])
                        if x.get("id") and str(x["id"]).isdigit()
                        else float("-inf")
                    ),
                    reverse=True,  # 新しいもの（IDが大きいもの）が先頭
                )
                if len(all_collected_potential_tweets) > max_tweets_to_register:
                    all_collected_potential_tweets = all_collected_potential_tweets[
                        :max_tweets_to_register
                    ]
                    print(
                        f"   処理候補リストを最新の {len(all_collected_potential_tweets)} 件に制限しました（目標登録数: {max_tweets_to_register}）。"
                    )

            print(
                f"\n📊 現在の処理候補の合計ツイート数: {len(all_collected_potential_tweets)} 件 (うち今回新規詳細化: {len(newly_processed_tweets_chunk) if newly_processed_tweets_chunk else 0}件)"
            )

            processed_this_iteration_for_log = 0
            # all_collected_potential_tweets は既に新しい順になっているはず
            for tweet_data in all_collected_potential_tweets:
                if successfully_registered_count >= max_tweets_to_register:
                    break

                tweet_id_for_check = tweet_data.get("id")
                if tweet_id_for_check in processed_tweet_ids_for_upload_loop:
                    continue  # この main ループの upload 試行済みリストでチェック

                # upload_to_notion に渡す前に、再度グローバル処理済みセットで確認
                # (extract_and_merge_tweets でチェック済みのはずだが、念には念を)
                if tweet_id_for_check in all_processed_ids_set:
                    print(
                        f"   DEBUG main: ID {tweet_id_for_check} is in all_processed_ids_set before upload_to_notion. Skipping upload loop for this ID."
                    )
                    processed_tweet_ids_for_upload_loop.add(
                        tweet_id_for_check
                    )  # uploadループでは処理済みとする
                    continue

                processed_tweet_ids_for_upload_loop.add(tweet_id_for_check)
                processed_this_iteration_for_log += 1

                print(
                    f"\n🌀 Notion登録試行: {len(processed_tweet_ids_for_upload_loop)}/{len(all_collected_potential_tweets)} 件目候補 (ID: {tweet_id_for_check}) (登録成功: {successfully_registered_count}/{max_tweets_to_register})"
                )

                tweet_data_for_upload = tweet_data.copy()
                tweet_data_for_upload.pop("article_element", None)

                upload_status = upload_to_notion(
                    tweet_data_for_upload,
                    config,
                    notion_client_main,
                    registered_ids_map,  # ここに all_processed_ids_set が含まれている
                    db_id_processed_posts,
                )

                # ★★★ upload_status に応じて all_processed_ids_set を更新 ★★★
                current_tweet_id_str_for_set = str(tweet_data.get("id"))
                merged_ids_for_set = tweet_data.get("merged_reply_ids", [])
                if isinstance(merged_ids_for_set, str):  # 文字列ならリストに変換
                    merged_ids_for_set = [
                        m_id.strip()
                        for m_id in merged_ids_for_set.split(",")
                        if m_id.strip().isdigit()
                    ]

                if upload_status == "SUCCESS":
                    successfully_registered_count += 1
                    all_processed_ids_set.add(current_tweet_id_str_for_set)
                    for m_id in merged_ids_for_set:
                        all_processed_ids_set.add(str(m_id))
                elif upload_status == "SKIPPED_REGISTERED":
                    # print(f"ℹ️ Tweet ID {tweet_data.get('id')} は登録済みのためスキップしました。") # upload_to_notion内でログ出力済み
                    all_processed_ids_set.add(
                        current_tweet_id_str_for_set
                    )  # 念のため追加
                    for m_id in merged_ids_for_set:
                        all_processed_ids_set.add(str(m_id))
                elif upload_status == "SKIPPED_CLASSIFICATION":
                    # print(f"ℹ️ Tweet ID {tweet_data.get('id')} は分類により登録対象外のためスキップしました。") # upload_to_notion内でログ出力済み
                    all_processed_ids_set.add(
                        current_tweet_id_str_for_set
                    )  # 分類スキップも処理済みとみなす
                    for m_id in merged_ids_for_set:
                        all_processed_ids_set.add(str(m_id))
                elif upload_status == "FAILED_CONFIG":
                    # print(f"⚠️ Tweet ID {tweet_data.get('id')} はDB設定不備。config.jsonを確認。") # upload_to_notion内でログ出力済み
                    all_processed_ids_set.add(
                        current_tweet_id_str_for_set
                    )  # 設定不備でも再試行しないように処理済みとする
                elif upload_status == "FAILED":
                    # print(f"⚠️ Tweet ID {tweet_data.get('id')} の登録に失敗しました。") # upload_to_notion内でログ出力済み
                    all_processed_ids_set.add(
                        current_tweet_id_str_for_set
                    )  # 失敗した場合も処理済みとする

                # registered_ids_map["all_processed"] も更新
                registered_ids_map["all_processed"] = all_processed_ids_set
                # ★★★ ここまで ★★★

                temp_files_after_upload = ["tweet_for_gpt.json", "gpt_output.json"]
                for temp_file_au in temp_files_after_upload:
                    if os.path.exists(temp_file_au):
                        try:
                            os.remove(temp_file_au)
                        except:
                            pass

            # all_collected_potential_tweets から processed_tweet_ids_for_upload_loop に含まれるものを削除する
            # ただし、Notion登録成功したものだけを削除するか、試行したものは全て削除するかはポリシーによる
            # ここでは、uploadループで試行したものは all_collected_potential_tweets からは一旦削除しないでおく
            # (次のイテレーションで再度詳細化されることはないが、リストに残っていても害は少ない)
            # もしメモリ効率を気にするなら、ここで削除する。
            # all_collected_potential_tweets = [
            #     t for t in all_collected_potential_tweets if t["id"] not in processed_tweet_ids_for_upload_loop
            # ]

            print(
                f"   イテレーション {iteration_num + 1}: Notion登録ループで {processed_this_iteration_for_log} 件の候補を処理しました。"
            )

            if successfully_registered_count >= max_tweets_to_register:
                print(
                    f"🎯 目標登録数 ({max_tweets_to_register}件) に達したため、全処理を終了します。"
                )
                break

            if iteration_num < max_fetch_iterations - 1:
                if total_urls_extracted_in_iterations < max_total_urls_to_process:
                    print(
                        f"\nイテレーション {iteration_num + 1} 終了。{iteration_delay_seconds}秒待機します..."
                    )
                    time.sleep(iteration_delay_seconds)
                else:
                    print(
                        f"\n総収集試行URL数が上限 ({max_total_urls_to_process}) に達したため、これ以上のURL収集は行いません。"
                    )
            else:
                print(
                    f"\n最大イテレーション回数 ({max_fetch_iterations}) に達しました。"
                )

        if successfully_registered_count < max_tweets_to_register:
            print(
                f"\n⚠️ 全ての処理を試みましたが、目標登録数 ({max_tweets_to_register}件) に達しませんでした。"
                f"実際に登録されたのは {successfully_registered_count}件です。"
            )
        else:
            print(
                f"\n✅ 目標の {successfully_registered_count} 件の登録が完了しました。"
            )

    except Exception as e_main:
        print(
            f"❌ main処理中に予期せぬエラーが発生しました: {type(e_main).__name__} - {e_main}"
        )
        print(traceback.format_exc())
    finally:
        if driver:
            driver.quit()
            print("🚪 ブラウザを終了しました。")

        temp_files_to_remove = ["tweet_for_gpt.json", "gpt_output.json"]
        for temp_file in temp_files_to_remove:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    print(f"🗑️ 一時ファイル削除: {temp_file}")
                except Exception as e_remove_temp:
                    print(f"⚠️ 一時ファイル削除失敗 ({temp_file}): {e_remove_temp}")

        temp_dirs_to_remove = ["temp_posters", "temp_ocr_images"]
        for temp_dir in temp_dirs_to_remove:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(
                        temp_dir, ignore_errors=True
                    )  # ignore_errors=True を追加
                    print(f"🗑️ 一時ディレクトリ削除: {temp_dir}")
                except Exception as e_remove_dir:
                    print(f"⚠️ 一時ディレクトリ削除失敗 ({temp_dir}): {e_remove_dir}")

    print("✅ 全投稿の処理完了")


if __name__ == "__main__":
    main()
