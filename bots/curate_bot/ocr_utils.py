# curate_bot/ocr_utils.py

import requests
from PIL import Image
import pytesseract
import io
# import logging # loggerを引数で受け取る

def ocr_image_from_url(image_url, logger):
    """
    画像URLから画像をダウンロードし、OCR処理を実行してテキストを抽出する。
    """
    if not image_url:
        return None
    try:
        logger.info(f" OCR対象画像URL: {image_url}")
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status()

        image_bytes = io.BytesIO(response.content)
        img = Image.open(image_bytes)
        
        text = pytesseract.image_to_string(img, lang='jpn+eng')
        logger.info(f"  OCR結果 ({image_url}): {text[:100].strip()}...")
        return text.strip()
    except requests.exceptions.RequestException as e:
        logger.error(f"画像ダウンロード失敗 ({image_url}): {e}")
        return None
    except pytesseract.TesseractNotFoundError:
        logger.error("❌ Tesseract OCRエンジンが見つかりません。インストールされているか、パスが通っているか確認してください。")
        return None
    except Exception as e:
        logger.error(f"OCR処理中にエラーが発生しました ({image_url}): {e}", exc_info=True)
        return None

def ocr_images_from_urls(image_urls, logger):
    """
    複数の画像URLを受け取り、それぞれOCR処理を行い、抽出されたテキストを結合して返す。
    """
    if not image_urls or not isinstance(image_urls, list):
        return None
    
    all_ocr_texts = []
    logger.info(f"複数画像のOCR処理を開始 (合計{len(image_urls)}件)")
    for i, url in enumerate(image_urls):
        logger.info(f" OCR処理中 ({i+1}/{len(image_urls)}): {url}")
        ocr_text = ocr_image_from_url(url, logger) # loggerを渡す
        if ocr_text:
            all_ocr_texts.append(ocr_text)
        else:
            logger.warning(f" OCR結果なし、またはエラー: {url}")
            
    if not all_ocr_texts:
        logger.info("すべての画像からOCRテキストを抽出できませんでした。")
        return None
    
    logger.info(f"合計 {len(all_ocr_texts)} 件の画像からテキストを抽出しました。")
    return "\n\n---\n\n".join(all_ocr_texts)

if __name__ == '__main__':
    # テスト用ロガーのセットアップ
    import logging
    test_logger = logging.getLogger('OCRUtilTest')
    test_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    if not test_logger.hasHandlers():
        test_logger.addHandler(handler)
    test_logger.propagate = False # 重複ログを防ぐ

    test_urls_with_text = [
        "https://www.bannerbatterien.com/upload/filecache/Banner-Batterien-Logo-jpg_0x0_100_c53520092348a5ce143f9a11da8e1376.jpg",
    ]
    test_urls_no_text = ["https://via.placeholder.com/150"]

    test_logger.info("--- 文字あり画像のテスト ---")
    result_with_text = ocr_images_from_urls(test_urls_with_text, test_logger)
    if result_with_text:
        test_logger.info("抽出されたテキスト:")
        test_logger.info(result_with_text)
    else:
        test_logger.info("テキストは抽出されませんでした。")

    test_logger.info("\n--- 文字なし画像のテスト ---")
    result_no_text = ocr_images_from_urls(test_urls_no_text, test_logger)
    if result_no_text:
        test_logger.info("抽出されたテキスト:")
        test_logger.info(result_no_text)
    else:
        test_logger.info("テキストは抽出されませんでした。")

    test_logger.info("\n--- 単一URLテスト (Banner) ---")
    single_url_text = ocr_image_from_url("https://www.bannerbatterien.com/upload/filecache/Banner-Batterien-Logo-jpg_0x0_100_c53520092348a5ce143f9a11da8e1376.jpg", test_logger)
    if single_url_text:
        test_logger.info(single_url_text)
    else:
        test_logger.info("テキスト抽出失敗") 