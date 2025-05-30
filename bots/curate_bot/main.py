import argparse
import os
import sys
import requests

# プロジェクトルートをsys.pathに追加 (他のボットモジュールをインポートするため)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from config import config_loader
from utils.logger import setup_logger
from bots.curate_bot import ocr_utils # ocr_utilsをインポート

# 新しいボットモジュールをインポート
from bots.extract_tweets_bot.tweet_extractor import TweetExtractor # TweetExtractor をインポート
from bots.compile_bot.tweet_compiler import TweetCompiler

# APIクライアントをインポート (投稿用に残す可能性も考慮し、コメントアウトしておく)
# from bots.extract_tweets_bot.twitter_api_client import TwitterApiClient

# ロガーのセットアップ
# curate_bot はパイプラインランナーとしてのログを出力
logger = setup_logger(log_dir_name='bots/curate_bot/logs', log_file_name='pipeline.log', logger_name='CurationPipeline')

def main():
    # curate_bot の設定は extractor と compiler で共有される部分も多いと想定し、
    # まず curate_bot の設定を読み込む。各ボットはここから必要な情報を取得する。
    # TODO: 将来的には extractor_bot_config と compiler_bot_config を個別に読み込むことを検討
    pipeline_config = config_loader.get_full_config() # APIクライアントがフルコンフィグを参照するため
    if not pipeline_config:
        logger.error("❌ 設定ファイル全体が読み込めませんでした。処理を終了します。")
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
    try:
        # logger.info("--- Twitter API クライアント初期化中 ---")
        # api_client = TwitterApiClient() # bot_nameはデフォルト値を使用
        # if not api_client.bearer_token: # App Contextが使えるか簡易チェック
        #     logger.error("❌ Twitter APIクライアントの初期化に失敗したか、Bearer Tokenが無効です。ツイート取得処理を中止します。")
        #     return
        # logger.info("✅ Twitter API クライアント初期化完了")

        logger.info("--- TweetExtractor 初期化中 ---")
        # TweetExtractor には、curate_bot の設定セクション、または extractor_bot 固有の設定を渡す
        # ここでは、ひとまず curate_bot の設定を渡すことを試みる
        extractor_bot_config = config_loader.get_bot_config("extract_tweets_bot")
        if not extractor_bot_config:
            logger.warning("extract_tweets_bot の設定が見つかりません。curate_bot の設定を流用します。")
            extractor_bot_config = config_loader.get_bot_config("curate_bot") # Fallback
        if not extractor_bot_config:
            logger.error("extract_tweets_bot または curate_bot の設定が見つかりません。TweetExtractor を初期化できません。")
            return
        extractor = TweetExtractor(bot_config=extractor_bot_config, parent_logger=logger)
        logger.info("✅ TweetExtractor (snscrape) 初期化完了")

        logger.info("--- TweetCompiler 初期化中 ---")
        # TweetCompilerには従来通りcurate_botの設定セクションを渡すか、あるいはフルコンフィグとbot名を渡すように変更検討
        # ここでは、compile_botが必要とする設定がcurate_botセクション内にあるという前提で、元の引数を維持してみる
        # ただし、NotionCompilerの初期化で full_config を参照している箇所があるので、整合性に注意
        compiler_bot_config = config_loader.get_bot_config("compile_bot") # compile_bot固有の設定を取得
        if not compiler_bot_config:
             logger.warning("compile_botの設定が見つかりません。curate_botの設定を流用します。")
             compiler_bot_config = config_loader.get_bot_config("curate_bot")
        if not compiler_bot_config: # それでもない場合
             logger.error("compile_botまたはcurate_botの設定が見つかりません。TweetCompilerを初期化できません。")
             return
        compiler = TweetCompiler(compiler_bot_config, parent_logger=logger)
        logger.info("✅ TweetCompiler 初期化完了")

        gemini_api_key = config_loader.get_gemini_api_key()
        if not gemini_api_key:
            logger.warning("⚠️ Gemini APIキーが設定されていません。OCR/LLM処理はスキップされます。")

        # スクレイピングベースのログイン処理は不要
        # logger.info("--- Twitterログイン処理開始 ---")
        # extractor.login(args.target)
        # logger.info("✅ Twitterログイン成功")

        logger.info("--- NotionCompiler セットアップ開始 ---")
        compiler.setup_notion_compiler()
        logger.info("✅ NotionCompiler セットアップ完了")

        logger.info(f"--- @{args.target} からのツイート取得開始 (snscrape経由, 最大{args.max_extract}件) ---")
        # snscrape を使ってツイートを取得
        # extract_tweets は (username, max_tweets, globally_processed_ids) を引数に取る
        # globally_processed_ids は NotionCompiler から取得することを想定 (今回は空で開始)
        globally_processed_ids_from_notion = compiler.notion_compiler.get_all_processed_tweet_ids() if compiler.notion_compiler else set()
        logger.info(f"Notionから取得した処理済みツイートID数: {len(globally_processed_ids_from_notion)}")
        
        raw_tweets_from_snscrape = extractor.extract_tweets(
            username=args.target,
            max_tweets=args.max_extract,
            globally_processed_ids=globally_processed_ids_from_notion # 処理済みIDを引き渡す
        )
        logger.info(f"✅ snscrapeからのツイート取得完了。 {len(raw_tweets_from_snscrape)}件のツイート候補を取得。")

        if not raw_tweets_from_snscrape:
            logger.info("snscrapeから取得されたツイートがありません。パイプラインを終了します。")
            return

        # snscrapeからのツイートデータを後続処理が期待する形式に変換
        extracted_tweets = []
        media_download_base_dir = os.path.join(PROJECT_ROOT, "downloaded_media_snscrape") 
        os.makedirs(media_download_base_dir, exist_ok=True)

        # user_map は snscrape の場合、各ツイートにユーザー情報が含まれるため、APIのような事前作成は不要

        for snscrape_tweet_data in raw_tweets_from_snscrape:
            # snscrape の出力形式は TweetExtractor で定義した Dict 形式
            # "id", "text", "timestamp", "author_name", "author_username", "media_files", "url", etc.
            
            media_files_for_ocr = []
            if snscrape_tweet_data.get('media_files'):
                logger.info(f"ツイートID {snscrape_tweet_data['id']} のメディア処理を開始します。")
                for media_info in snscrape_tweet_data['media_files']:
                    media_url = media_info.get('url')
                    media_type = media_info.get('type') # 'photo', 'video', 'gif'
                    
                    if media_url:
                        # メディアのダウンロード処理 (ここは別途実装または既存のものを流用)
                        # ここでは、ダウンロード処理を仮に実装し、後で詳細を詰める
                        # ファイル名は tweet_id と media_type, URLのハッシュなどで一意にする
                        try:
                            # TODO: 適切なダウンロード処理を実装する
                            # (例: requests を使ってダウンロード)
                            # ファイル名に拡張子を付与する
                            filename_suggestion = f"{snscrape_tweet_data['id']}_{media_type}_{os.path.basename(media_url).split('?')[0]}" # クエリパラメータ除去
                            local_media_path = os.path.join(media_download_base_dir, filename_suggestion)
                            
                            # --- ここから簡易ダウンロード処理 ---
                            if not os.path.exists(local_media_path): # まだダウンロードされていなければ
                                logger.info(f"  メディアをダウンロード中: {media_url} -> {local_media_path}")
                                response = requests.get(media_url, stream=True, timeout=10) # requestsをimportする必要あり
                                response.raise_for_status()
                                with open(local_media_path, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                logger.info(f"    ダウンロード成功: {local_media_path}")
                            else:
                                logger.info(f"  メディアは既に存在します: {local_media_path}")
                            # --- ここまで簡易ダウンロード処理 ---

                            media_files_for_ocr.append({
                                'path': local_media_path,
                                'type': media_type,
                                'original_url': media_url
                            })
                        except requests.exceptions.RequestException as e:
                            logger.error(f"  メディアダウンロード失敗: {media_url}, エラー: {e}")
                        except Exception as e:
                            logger.error(f"  メディア処理中に予期せぬエラー: {media_url}, エラー: {e}")
                    else:
                        logger.warning(f"メディア情報にURLがありません: {media_info}")
            
            processed_data = {
                "id": snscrape_tweet_data['id'],
                "text": snscrape_tweet_data['text'],
                "timestamp": snscrape_tweet_data['timestamp'], # ISOフォーマット文字列
                "author_name": snscrape_tweet_data['author_name'],
                "author_username": snscrape_tweet_data['author_username'],
                "media_files": media_files_for_ocr, # ダウンロード後のローカルパス情報
                "url": snscrape_tweet_data.get('url'), # ツイートURL
                # OCR/LLM処理用に追加のフィールドは後で追加される想定
                "_raw_snscrape_output": snscrape_tweet_data # デバッグ用に元データを保持
            }
            extracted_tweets.append(processed_data)

        # 3.5. OCRとLLMによるテキスト処理 (gemini_api_keyがある場合)
        if gemini_api_key and extracted_tweets:
            logger.info(f"--- Gemini APIによるOCR・LLM処理開始 ({len(extracted_tweets)}件のツイート候補) ---")
            processed_tweets_for_compile = []
            for tweet_data in extracted_tweets: # extracted_tweets はリストであることを想定
                # tweet_data は辞書型で、'media_files': [{'path': 'local_path_to_media'}, ...] のような構造を想定
                # これは TweetExtractor (または将来の TwitterApiClient) の出力形式に依存
                if 'media_files' in tweet_data and tweet_data['media_files']:
                    all_ocr_texts = []
                    for media_file_info in tweet_data['media_files']:
                        local_media_path = media_file_info.get('path')
                        media_type = media_file_info.get('type') # 'photo', 'video'など
                        
                        if local_media_path and media_type == 'photo': # 現状、画像のみOCR対象
                            logger.info(f"  画像OCR処理中: {local_media_path}")
                            ocr_result = ocr_utils.ocr_with_gemini_vision(
                                gemini_api_key, 
                                local_media_path, 
                                logger=logger, 
                                is_url=False
                            )
                            if ocr_result and not any(err_code in ocr_result for err_code in ["LOCAL_FILE_NOT_FOUND", "IMAGE_LOAD_FAILED", "DOWNLOAD_FAILED", "OCR_PROCESSING_ERROR"]):
                                logger.info(f"    OCR成功。補正処理へ。")
                                corrected_text = ocr_utils.correct_ocr_text_with_gemini(
                                    gemini_api_key, 
                                    ocr_result, 
                                    logger=logger
                                )
                                all_ocr_texts.append(corrected_text)
                            elif ocr_result: # エラーコードが返ってきた場合
                                logger.warning(f"    OCR処理失敗 ({ocr_result}): {local_media_path}")
                            else: # 空文字が返ってきた場合 (画像にテキストなしなど)
                                logger.info(f"    OCR結果なし (テキスト非検出等): {local_media_path}")
                        elif local_media_path and media_type != 'photo':
                            logger.info(f"  メディアタイプ '{media_type}' はOCR対象外: {local_media_path}")

                    if all_ocr_texts:
                        tweet_data['ocr_text'] = "\n\n---\n\n".join(all_ocr_texts) # 複数メディアの場合、区切り文字で結合
                        logger.info(f"  ツイートID {tweet_data.get('id_str', 'N/A')} のOCR/LLM処理完了。")
                    else:
                        tweet_data['ocr_text'] = "" # OCR対象メディアがなかったか、全て失敗/テキストなし
                else:
                    tweet_data['ocr_text'] = "" # メディアファイルなし
                
                processed_tweets_for_compile.append(tweet_data)
            extracted_tweets = processed_tweets_for_compile # OCR/LLM処理済みのリストで上書き
            logger.info("✅ Gemini APIによるOCR・LLM処理完了。")
        elif not gemini_api_key:
            logger.info("Gemini APIキーがないため、OCR/LLM処理をスキップしました。")
        
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
        # if 'api_client' in locals() and api_client and hasattr(api_client, 'cleanup'): # hasattrで確認する
        #     api_client.cleanup()
        #     logger.info("✅ Twitter API クリーンアップ完了")
        # TwitterApiClient には cleanup メソッドがないため、呼び出しをコメントアウト
        if 'compiler' in locals() and compiler and hasattr(compiler, 'cleanup'): # compilerも同様に確認
            compiler.cleanup()
            logger.info("✅ TweetCompiler クリーンアップ完了")
        logger.info("=== キュレーションパイプライン終了 ===")

if __name__ == "__main__":
    main() 