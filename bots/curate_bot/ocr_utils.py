# curate_bot/ocr_utils.py

import google.generativeai as genai
import requests
from PIL import Image
import io
import os
from typing import Union
import yaml # For config loading in test block
import random
import logging # ログ出力用
import time # time モジュールをインポート

# User-Agentリストを保持するグローバル変数 (ocr_utils 単体テスト時も考慮)
_user_agents = []
try:
    # このパスは ocr_utils.py から見た相対パス (bots/curate_bot/ocr_utils.py -> ../../config/config.yml)
    config_path_for_ua = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'config.yml')
    if not os.path.exists(config_path_for_ua):
         print(f"⚠️ User-Agent設定ファイルが見つかりません: {config_path_for_ua}。デフォルトのUser-Agentを使用します。")
         _user_agents = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"]
    else:
        with open(config_path_for_ua, 'r', encoding='utf-8') as f: # encoding追加
            config_data_ua = yaml.safe_load(f)
        _user_agents = config_data_ua.get("common", {}).get("default_user_agents", [])
        if not _user_agents:
            print(f"⚠️ (ocr_utils): config.yml に default_user_agents が見つかりません。デフォルトのUser-Agentを使用します。")
            _user_agents = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"]
except Exception as e:
    print(f"⚠️ User-Agent設定の読み込み中にエラーが発生しました（デフォルト値を使用）: {e}")
    _user_agents = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"]


def ocr_with_gemini_vision(api_key: str, image_url: str, logger: logging.Logger = None) -> str: # Union[str, None] から str に変更
    """
    指定された画像URLからGemini Visionモデルを使ってテキストを抽出する。
    エラーが発生した場合は、エラー種別を示す文字列を返す。
    """
    log = logger if logger else logging.getLogger("ocr_with_gemini_vision")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        user_agent = random.choice(_user_agents) if _user_agents else "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        headers = {'User-Agent': user_agent}

        log.info(f"画像をダウンロード中: {image_url} (User-Agent: {user_agent})")
        response = requests.get(image_url, stream=True, headers=headers, timeout=20)
        response.raise_for_status()

        img = Image.open(io.BytesIO(response.content))

        generation_config = genai.types.GenerationConfig(temperature=0)
        api_response = model.generate_content(
            ["この画像からテキストを読み取ってください。", img],
            generation_config=generation_config,
            stream=False
        )
        time.sleep(2) # API呼び出し後に待機

        if api_response.candidates and api_response.candidates[0].content.parts:
            extracted_text = "".join(part.text for part in api_response.candidates[0].content.parts if hasattr(part, 'text'))
            log.info(f"  OCR成功 ({image_url}): \"{extracted_text[:100].strip()}...\"")
            return extracted_text.strip()
        else:
            log.warning(f"Geminiからのレスポンスにテキストが含まれていませんでした ({image_url})。画像にテキストがない可能性があります。")
            return "" # テキストがない場合は空文字を返す
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            log.error(f"画像が見つかりません (404エラー): {image_url}, {e}")
            return "DOWNLOAD_FAILED_404"
        else:
            log.error(f"画像のダウンロード中にHTTPエラーが発生しました (コード: {e.response.status_code}): {image_url}, {e}")
            return f"DOWNLOAD_FAILED_HTTP_{e.response.status_code}"
    except requests.exceptions.Timeout:
        log.error(f"画像のダウンロード中にタイムアウトしました: {image_url}")
        return "DOWNLOAD_FAILED_TIMEOUT"
    except requests.exceptions.ConnectionError:
        log.error(f"画像のダウンロード中に接続エラーが発生しました: {image_url}")
        return "DOWNLOAD_FAILED_CONNECTION"
    except requests.exceptions.RequestException as e: # その他のrequests由来のエラー
        log.error(f"画像のダウンロード中に予期せぬリクエストエラーが発生しました: {image_url}, {e}")
        return "DOWNLOAD_FAILED_OTHER_REQUEST"
    except Exception as e: # Gemini API処理中またはPillow処理中のエラー
        log.error(f"Gemini Vision APIでのOCR処理中または画像処理中にエラーが発生しました ({image_url}): {e}", exc_info=True)
        return "OCR_PROCESSING_ERROR"

def correct_ocr_text_with_gemini(api_key: str, ocr_text: str, logger: logging.Logger = None, instruction: str = None) -> str: # Union[str, None] から str に変更
    """
    Geminiモデルを使用してOCRテキストを補正する。
    補正に失敗した場合は元のテキストを返す。
    """
    log = logger if logger else logging.getLogger("correct_ocr_text_with_gemini")
    if not ocr_text or ocr_text.strip() == "":
        log.info("補正対象のOCRテキストが空または空白のみです。処理をスキップします。")
        return ocr_text

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        base_prompt = f"""以下のOCRによって抽出されたテキストを、可能な限り簡潔に、最も主要な情報のみを残す形で補正してください。
特に、誤字脱字の修正、不自然な改行の調整、句読点の適切な挿入に加えて、文末の「です」「ます」調や、説明的な言葉、冗長な表現は完全に削除してください。
ただし、元のテキストに含まれる固有名詞や重要なキーワードの意味やニュアンスを大きく変えないように注意してください。
補正後のテキストのみを、他の言葉を一切付けずに出力してください。

OCRテキスト:
---
{ocr_text}
---
"""
        if instruction:
            prompt = f"{base_prompt}\n追加指示: {instruction}\n\n補正後のテキスト:"
        else:
            prompt = f"{base_prompt}\n補正後のテキスト:"

        log.info(f"Gemini ({model._model_name}) でOCRテキスト補正を開始します。入力テキスト（一部）: \"{ocr_text[:100]}...\"")

        generation_config = genai.types.GenerationConfig(
            temperature=0.2,
        )

        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        time.sleep(2) # API呼び出し後に待機

        if response.candidates and response.candidates[0].content.parts:
            corrected_text = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
            log.info(f"  補正成功。補正後テキスト（一部）: \"{corrected_text[:100]}...\"")
            return corrected_text.strip()
        else:
            log.warning(f"Geminiからのレスポンスに補正済みテキストが含まれていませんでした。")
            return ocr_text
    except Exception as e:
        log.error(f"Gemini API ({model._model_name if 'model' in locals() else 'N/A'}) でのOCRテキスト補正中にエラーが発生しました: {e}", exc_info=True)
        return ocr_text

if __name__ == '__main__':
    # --- Test Logger Setup ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_logger = logging.getLogger("Gemini_OCRUtil_Test")
    # --- End Test Logger Setup ---

    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'config.yml')
    test_api_key = None
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f: # encoding追加
            config_data = yaml.safe_load(f)
        test_api_key = config_data.get("gemini_api", {}).get("api_key")
    except Exception as e:
        main_logger.error(f"config.yml の読み込み中にエラー: {e}")

    if not test_api_key:
        main_logger.error("テスト用のGemini APIキーが config.yml から取得できませんでした。テストを中止します。")
    else:
        main_logger.info(f"Gemini APIキーを config.yml から読み込みました。")

        google_logo_url = "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"

        main_logger.info(f"--- テスト画像URL: {google_logo_url} ---")
        ocr_result = ocr_with_gemini_vision(test_api_key, google_logo_url, logger=main_logger)

        # ocr_with_gemini_vision は None を返さなくなったので、 is not None のチェックは実質不要だが残しておく
        if ocr_result is not None:
            # f-string をシングルクォートで囲み、内部のダブルクォートはそのまま表示
            main_logger.info(f'OCR結果 (ocr_with_gemini_vision raw output):\n"{ocr_result}"')

            error_keywords_check = ["DOWNLOAD_FAILED", "OCR_PROCESSING_ERROR"]
            is_error_ocr_result = any(keyword in ocr_result for keyword in error_keywords_check) # ocr_resultが空文字の場合も考慮

            if not is_error_ocr_result and ocr_result.strip():
                main_logger.info("\n--- LLMによるOCR補正テスト (correct_ocr_text_with_gemini) ---")
                corrected_text = correct_ocr_text_with_gemini(
                    test_api_key,
                    ocr_result,
                    logger=main_logger
                )
                if corrected_text != ocr_result:
                    # f-string をシングルクォートで囲み、内部のダブルクォートはそのまま表示
                    main_logger.info(f'LLMによる補正後テキスト:\n"{corrected_text}"')
                else:
                    main_logger.info("LLMによる補正結果は元のテキストと同じか、補正に失敗/スキップされました。")
            elif is_error_ocr_result:
                # f-string をダブルクォートで囲み、内部のシングルクォートはそのまま表示
                main_logger.info(f"OCR結果がエラーコード ('{ocr_result}') のため、LLMによる補正はスキップします。")
            else: # OCR結果が空だがエラーではない場合
                main_logger.info("OCR結果が空のため、LLMによる補正はスキップします。")
        else:
            # 通常ここには到達しないはず
            main_logger.error("OCR処理で致命的なエラーが発生しました (結果がNone)。")

        main_logger.info("\n--- テスト完了 ---")