import argparse
import os
import sys

# プロジェクトルートをsys.pathに追加 (他のボットモジュールをインポートするため)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from config import config_loader
from utils.logger import setup_logger

# 新しいボットモジュールをインポート
from bots.extract_tweets_bot.tweet_extractor import TweetExtractor
from bots.compile_bot.tweet_compiler import TweetCompiler

# ロガーのセットアップ
# curate_bot はパイプラインランナーとしてのログを出力
logger = setup_logger(log_dir_name='bots/curate_bot/logs', log_file_name='pipeline.log', logger_name='CurationPipeline')

def main():
    # curate_bot の設定は extractor と compiler で共有される部分も多いと想定し、
    # まず curate_bot の設定を読み込む。各ボットはここから必要な情報を取得する。
    # TODO: 将来的には extractor_bot_config と compiler_bot_config を個別に読み込むことを検討
    pipeline_config = config_loader.get_bot_config("curate_bot")
    if not pipeline_config:
        logger.error("❌ curate_bot の設定が読み込めませんでした。処理を終了します。")
        return

    # scraping設定は bot_config 内の scraping セクションから取得 (引数のデフォルト値用)
    # これは TweetExtractor 側でも利用するが、コマンドライン引数で上書き可能
    scraping_settings = pipeline_config.get("scraping", {})
    default_max_tweets = scraping_settings.get("max_tweets_to_extract", 30) # キー名を変更して明確化も検討
    default_max_to_compile = scraping_settings.get("max_tweets_to_compile", 30)

    parser = argparse.ArgumentParser(description="ツイート収集・コンパイルパイプライン")
    parser.add_argument("--target", required=True, help="収集対象のTwitterユーザー名")
    parser.add_argument("--max-extract", type=int, default=default_max_tweets, 
                        help=f"収集する最大ツイート数 (デフォルト: {default_max_tweets})")
    parser.add_argument("--max-compile", type=int, default=default_max_to_compile, 
                        help=f"Notionに保存処理する最大ツイート数 (デフォルト: {default_max_to_compile})")
    args = parser.parse_args()

    logger.info(f"=== キュレーションパイプライン開始: Target: @{args.target} ===")
    logger.info(f"Extraction limit: {args.max_extract}, Compilation limit: {args.max_compile}")

    # TweetExtractor と TweetCompiler に pipeline_config と logger を渡す
    # 各クラスは pipeline_config から必要な情報を取得する
    # (例: Twitterアカウント情報、Notion APIキー、データベースIDなど)
    try:
        logger.info("--- TweetExtractor 初期化中 ---")
        # TweetExtractor には curate_bot の設定全体を渡し、必要な twitter_accounts などを内部で参照させる
        extractor = TweetExtractor(pipeline_config, parent_logger=logger) 
        logger.info("✅ TweetExtractor 初期化完了")

        logger.info("--- TweetCompiler 初期化中 ---")
        # TweetCompiler にも curate_bot の設定全体を渡し、必要な notion 設定などを内部で参照させる
        compiler = TweetCompiler(pipeline_config, parent_logger=logger)
        logger.info("✅ TweetCompiler 初期化完了")

        # 1. ログイン処理 (Extractor)
        logger.info("--- Twitterログイン処理開始 ---")
        extractor.login(args.target) # ログイン対象はコマンドライン引数のtargetユーザー
        logger.info("✅ Twitterログイン成功")

        # 2. NotionCompilerのセットアップ (Compiler)
        logger.info("--- NotionCompiler セットアップ開始 ---")
        compiler.setup_notion_compiler()
        logger.info("✅ NotionCompiler セットアップ完了")

        # 3. ツイート抽出 (Extractor)
        # extract_tweets は処理済みIDセットを受け取るが、ここではCompilerが持つキャッシュを使う想定はない
        # （Extractorはあくまで抽出に専念し、重複排除はCompilerがNotionデータと照合して行う）
        # ただし、もしExtractor側でも実行中の重複を避けたいなら、別途globally_processed_idsを渡す
        logger.info(f"--- @{args.target}からのツイート抽出開始 (最大{args.max_extract}件) ---")
        extracted_tweets = extractor.extract_tweets(
            args.target,
            args.max_extract,
            set() # extractor内でのスクロール中の重複排除用とは別に、全体での処理済みIDは渡さない
        )
        logger.info(f"✅ ツイート抽出完了。 {len(extracted_tweets)}件のツイート候補を取得。")

        if not extracted_tweets:
            logger.info("抽出されたツイートがありません。パイプラインを終了します。")
            return

        # 4. ツイートのコンパイルと保存 (Compiler)
        logger.info(f"--- 抽出されたツイートのコンパイルとNotionへの保存開始 (最大{args.max_compile}件) ---")
        compile_results = compiler.compile_and_save_tweets(extracted_tweets, args.max_compile)
        logger.info("✅ ツイートのコンパイルと保存完了。")

        logger.info("=== コンパイル処理結果 ===")
        logger.info(f"  Notion保存成功: {compile_results.get('success', 0)}")
        logger.info(f"  Notion保存失敗: {compile_results.get('failed', 0)}")
        logger.info(f"  スキップ(ID無等): {compile_results.get('skipped', 0)}")
        logger.info(f"  重複(処理済): {compile_results.get('duplicated', 0)}")

    except Exception as e:
        logger.error(f"❌ パイプライン処理中にエラーが発生しました: {str(e)}", exc_info=True)
    finally:
        logger.info("--- クリーンアップ処理開始 ---")
        if 'extractor' in locals() and extractor:
            extractor.cleanup()
            logger.info("✅ TweetExtractor クリーンアップ完了")
        if 'compiler' in locals() and compiler: # compiler も cleanup メソッドを持つ想定
            compiler.cleanup()
            logger.info("✅ TweetCompiler クリーンアップ完了")
        logger.info("=== キュレーションパイプライン終了 ===")

if __name__ == "__main__":
    main() 