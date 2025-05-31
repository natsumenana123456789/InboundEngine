import os
import sys
import logging
from datetime import datetime
import yaml
from post_processor import PostProcessor

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/auto_post_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    """設定ファイルを読み込む"""
    try:
        config_path = "config/config.yml"
        if not os.path.exists(config_path):
            logger.error(f"設定ファイルが見つかりません: {config_path}")
            return None

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return config

    except Exception as e:
        logger.error(f"設定ファイルの読み込みに失敗: {str(e)}")
        return None

def main():
    # 設定の読み込み
    config = load_config()
    if not config:
        logger.error("設定の読み込みに失敗しました。")
        return

    try:
        # PostProcessorの初期化と実行
        processor = PostProcessor(config, logger)
        processor.process_posts()
        
    except Exception as e:
        logger.error(f"投稿処理中にエラーが発生: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 