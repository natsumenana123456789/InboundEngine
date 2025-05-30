import os
import sys
import logging
from datetime import datetime

# プロジェクトルートをsys.pathに追加
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils.logger import setup_logger
from bots.curate_bot.ocr_utils import ocr_with_gemini_vision, correct_ocr_text_with_gemini
from config.config_loader import get_full_config

def test_ocr_pipeline():
    # ロガーの設定
    logger = setup_logger(
        log_dir_name='logs/test_curate_bot_logs',
        logger_name='TestCurateBotPipeline',
        level=logging.DEBUG
    )
    
    # 設定の読み込み
    config = get_full_config()
    if not config:
        logger.error("設定ファイルの読み込みに失敗しました。")
        return
    
    gemini_api_key = config.get("gemini_api", {}).get("api_key")
    if not gemini_api_key:
        logger.error("Gemini APIキーが設定されていません。")
        return
    
    # テスト用の画像URL
    test_images = [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png",  # Wikipediaロゴ
        "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png",  # Googleロゴ
        "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/Google_2015_logo.svg/1200px-Google_2015_logo.svg.png"  # Googleロゴ（別バージョン）
    ]
    
    logger.info("=== OCRパイプラインテスト開始 ===")
    
    for i, image_url in enumerate(test_images, 1):
        logger.info(f"\n--- テスト画像 {i}/{len(test_images)} ---")
        logger.info(f"画像URL: {image_url}")
        
        # 1. OCR処理
        logger.info("1. OCR処理を開始...")
        ocr_result = ocr_with_gemini_vision(
            api_key=gemini_api_key,
            image_path_or_url=image_url,
            logger=logger,
            is_url=True
        )
        
        if ocr_result and not any(err_code in ocr_result for err_code in ["DOWNLOAD_FAILED", "OCR_PROCESSING_ERROR"]):
            logger.info("OCR成功！")
            logger.info(f"抽出テキスト:\n{ocr_result}")
            
            # 2. LLM補正
            logger.info("\n2. LLMによるテキスト補正を開始...")
            corrected_text = correct_ocr_text_with_gemini(
                api_key=gemini_api_key,
                ocr_text=ocr_result,
                logger=logger
            )
            
            if corrected_text:
                logger.info("補正成功！")
                logger.info(f"補正後テキスト:\n{corrected_text}")
                
                # 3. 差分の表示
                if corrected_text != ocr_result:
                    logger.info("\n3. 補正の差分:")
                    logger.info("変更前:")
                    logger.info(ocr_result)
                    logger.info("\n変更後:")
                    logger.info(corrected_text)
                else:
                    logger.info("\n3. 補正による変更はありませんでした。")
            else:
                logger.warning("LLM補正に失敗しました。")
        else:
            logger.error(f"OCR処理に失敗しました: {ocr_result}")
        
        logger.info("\n" + "="*50)
    
    logger.info("\n=== OCRパイプラインテスト完了 ===")

if __name__ == "__main__":
    test_ocr_pipeline() 