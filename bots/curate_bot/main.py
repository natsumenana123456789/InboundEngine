import argparse
# import json # 設定ファイル読み込みはconfig_loaderに集約
import logging # setup_loggerがloggingを返すので、logging経由で利用
import os
from .tweet_scraper import TweetScraper
from .tweet_processor import TweetProcessor
from ...config import config_loader # config_loader をインポート
from ...utils.logger import setup_logger # ログ設定ユーティリティをインポート

# ロガーのセットアップ (モジュールレベルで実行)
# ログファイルは bots/curate_bot/logs/curate.log のようにしたいので調整
CURATE_BOT_LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
# logger = setup_logger(log_dir_name=CURATE_BOT_LOG_DIR, log_file_name='curate.log', logger_name='CurateBot')
# ↓ utils.logger側の project_root の解決方法を修正したので、ディレクトリ名だけでOK
logger = setup_logger(log_dir_name='bots/curate_bot/logs', log_file_name='curate.log', logger_name='CurateBot')


def main():
    # ボット固有の設定を取得
    bot_config = config_loader.get_bot_config("curate_bot")
    if not bot_config:
        logger.error("❌ curate_bot の設定が読み込めませんでした。処理を終了します。")
        return

    # scraping設定は bot_config 内の scraping セクションから取得
    scraping_settings = bot_config.get("scraping", {})
    default_max_tweets = scraping_settings.get("max_tweets", 30)

    parser = argparse.ArgumentParser(description="Twitter投稿の収集と保存")
    parser.add_argument("--target", required=True, help="収集対象のユーザー名")
    parser.add_argument("--max-tweets", type=int, default=default_max_tweets, help="収集する最大ツイート数")
    args = parser.parse_args()

    # TweetScraper と TweetProcessor に bot_config と logger を渡す
    # 各クラスは bot_config から必要な情報を取得する
    scraper = TweetScraper(bot_config, logger)
    processor = TweetProcessor(bot_config, logger)

    try:
        scraper.login(args.target) # ログイン処理
        processor.setup_notion()   # Notionクライアントのセットアップ

        tweets = scraper.extract_tweets(
            args.target,
            args.max_tweets,
            set() # globally_processed_ids は初回は空セット
        )

        results = processor.process_tweets(tweets, args.max_tweets)

        logger.info("=== 処理結果 ===")
        logger.info(f"成功: {results['success']}")
        logger.info(f"失敗: {results['failed']}")
        logger.info(f"スキップ: {results['skipped']}")
        logger.info(f"重複: {results['duplicated']}")

    except Exception as e:
        logger.error(f"❌ エラーが発生しました: {str(e)}", exc_info=True)
    finally:
        scraper.cleanup()
        # processor.cleanup() # 必要なら追加

if __name__ == "__main__":
    main() 