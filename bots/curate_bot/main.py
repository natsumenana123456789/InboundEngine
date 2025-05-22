import argparse
import json # このjsonインポートは不要になる可能性あり
import logging
import os # os.path を使うために追加
from .tweet_scraper import TweetScraper
from .tweet_processor import TweetProcessor
# config_loaderをインポート (パスを修正)
from ...config import config_loader # ルートのconfigディレクトリからインポート (bots/ の分、ドットを1つ増やす)

# ログ設定
# Dockerのログパスを考慮しつつ、ローカル実行も考慮してパスを調整
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
LOG_FILE_PATH = os.path.join(LOG_DIR, 'app.log')

logging.basicConfig(
    filename=LOG_FILE_PATH,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# 設定ファイルのパス指定は不要になる
# CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.json')

def main():
    # config_loaderから設定を読み込む
    config = config_loader.load_config()
    if not config: # config_loaderが空の辞書を返す場合も考慮
        logging.error("❌ 設定の読み込みに失敗しました。処理を終了します。")
        return

    # scraping設定がない場合のフォールバックまたはエラー処理
    scraping_config = config.get("scraping", {})
    default_max_tweets = scraping_config.get("max_tweets", 30) # 設定ファイルになければデフォルト30

    parser = argparse.ArgumentParser(description="Twitter投稿の収集と保存")
    # --config 引数は削除
    parser.add_argument("--target", required=True, help="収集対象のユーザー名")
    parser.add_argument("--max-tweets", type=int, default=default_max_tweets, help="収集する最大ツイート数")
    args = parser.parse_args()

    # TweetScraper と TweetProcessor には全体の設定を渡す
    # 各クラス内で必要な設定（例: config['scraping'], config['notion']）を参照するように後で修正が必要
    scraper = TweetScraper(config) 
    processor = TweetProcessor(config)

    try:
        scraper.setup_driver()
        # ログイン情報は設定ファイルから取得するように変更 (scraper側で対応)
        scraper.login(args.target) # Twitterへのログイン処理を有効化
        
        # Notionの設定 (processor側で対応)
        processor.setup_notion() # Notionのセットアップ処理を有効化

        tweets = scraper.extract_tweets(
            args.target,
            args.max_tweets, # コマンドライン引数で指定された値を使用
            set() # globally_processed_ids に空のセットを渡す
            # args.max_tweets # この引数は scraper 側で管理されるべき
        )

        results = processor.process_tweets(tweets, args.max_tweets)

        logging.info("=== 処理結果 ===")
        logging.info(f"成功: {results['success']}")
        logging.info(f"失敗: {results['failed']}")
        logging.info(f"スキップ: {results['skipped']}")
        logging.info(f"重複: {results['duplicated']}")

    except Exception as e:
        logging.error(f"❌ エラーが発生しました: {str(e)}", exc_info=True) # スタックトレースも記録
    finally:
        scraper.cleanup()
        # processor.cleanup() # TweetProcessorにcleanupメソッドがあるか確認

if __name__ == "__main__":
    main() 