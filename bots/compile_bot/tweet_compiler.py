import os
import sys # sysモジュールをインポート
from typing import List, Dict, Optional
# プロジェクトルートをsys.pathに追加
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from .notion_compiler import NotionCompiler # 同じディレクトリのNotionCompilerをインポート
from utils.logger import setup_logger
# import logging # loggerを引数で受け取る

class TweetCompiler: # クラス名を TweetCompiler に変更
    def __init__(self, bot_config, parent_logger=None):
        self.bot_config = bot_config # compile_bot の設定
        # TODO: ログディレクトリを bots/compile_bot/logs に変更
        self.logger = parent_logger if parent_logger else setup_logger(log_dir_name='bots/compile_bot/logs', logger_name='TweetCompiler_default')
        
        # NotionCompiler に bot_config を渡して初期化
        # NotionCompiler は自身の bot_config から notion 設定を読み込む想定
        self.notion_compiler = NotionCompiler(self.bot_config, self.logger) 
        self.processed_tweet_ids_cache = set()

    def setup_notion_compiler(self): # メソッド名を変更
        """NotionCompilerのセットアップやDBスキーマの確認・更新を行う"""
        try:
            if not self.notion_compiler.is_client_initialized():
                 self.logger.error("NotionCompiler のクライアントが初期化されていません。Notion機能は利用できません。")
                 # 必要ならここで例外を発生させるか、初期化を試みる
                 # self.notion_compiler = NotionCompiler(self.bot_config, self.logger) # 再度初期化を試みる例
                 # if not self.notion_compiler.is_client_initialized():
                 raise RuntimeError("NotionCompilerの初期化に失敗しました。設定を確認してください。")

            self.notion_compiler.ensure_database_schema() 
            self.logger.info("✅ NotionCompiler セットアップ完了 (スキーマ確認含む)")
            
            # 処理済みIDをNotionからロードする (NotionCompilerが担当)
            # NotionCompiler には `load_processed_item_ids` があるのでそれを使う
            # このキャッシュは `compile_bot` の処理中にのみ有効。永続化はNotion側
            self.processed_tweet_ids_cache = self.notion_compiler.load_processed_item_ids(id_property_name="ツイートID")
            self.logger.info(f"Notionから {len(self.processed_tweet_ids_cache)} 件の処理済みツイートIDをロードしました。")
        except Exception as e:
            self.logger.error(f"❌ NotionCompiler のセットアップ中にエラー: {e}", exc_info=True)
            raise

    def compile_and_save_tweets(self, tweets_data: List[Dict], max_items_to_process: int): # メソッド名変更, 型ヒント修正
        if not self.notion_compiler or not self.notion_compiler.is_client_initialized():
            self.logger.error("❌ NotionCompiler が初期化されていません。処理を中止します。")
            raise RuntimeError("NotionCompiler が初期化されていません。")

        results = {"success": 0, "failed": 0, "skipped": 0, "duplicated": 0}
        processed_count_in_current_run = 0

        for tweet_data_from_extractor in tweets_data: # 引数名を変更
            if processed_count_in_current_run >= max_items_to_process:
                self.logger.info(f"今回の実行での処理上限 ({max_items_to_process}件) に達しました。")
                break

            tweet_id = tweet_data_from_extractor.get("id")
            if not tweet_id:
                self.logger.warning("IDがないツイートデータはスキップします。")
                results["skipped"] += 1
                continue

            if tweet_id in self.processed_tweet_ids_cache:
                self.logger.info(f"重複ツイート: {tweet_id} は既に処理済み(キャッシュ参照)。スキップします。")
                results["duplicated"] += 1
                continue
            
            # OCRテキストは tweet_data_from_extractor に "ocr_text" として含まれてくる想定
            # 広告判定も extract_tweets_bot 側で行われている想定

            # NotionCompilerのadd_compiled_itemに渡すためのデータ構造に変換
            # NotionCompilerのexpected_propertiesに合わせてキーをマッピングする
            # 例: tweet_data_from_extractor の "text" -> "本文"
            #     tweet_data_from_extractor の "author_name" -> "投稿者名" (Notion側が何という名前かによる)
            #     tweet_data_from_extractor の "timestamp" -> "投稿日時" (ISO形式に変換が必要かも)
            #     tweet_data_from_extractor の "media_urls" -> "画像URL1", "画像URL2" ...
            
            notion_item_data = {
                "ツイートID": tweet_id,
                "本文": tweet_data_from_extractor.get("text", ""),
                # 投稿者は user ではなく author_name や author_username を使う
                "投稿者": f'{tweet_data_from_extractor.get("author_name", "")} (@{tweet_data_from_extractor.get("author_username", "unknown")})',
                "ツイートURL": f"https://twitter.com/{tweet_data_from_extractor.get('author_username', 'i')}/status/{tweet_id}", # extractor から直接URLが取れればそれを使う
                "投稿日時": tweet_data_from_extractor.get("timestamp"), # ISO形式の文字列を期待
                "OCRテキスト": tweet_data_from_extractor.get("ocr_text")
                # ステータスは add_compiled_item の中でデフォルト「新規」を設定するか、ここで指定
            }
            # 画像URLのマッピング (media_urls はリスト想定)
            media_urls = tweet_data_from_extractor.get("local_media_paths", []) # extractorがローカルパスを返す場合
            if not media_urls: # ローカルパスがなければ、元のmedia_urlsを見る
                 media_urls = [media.get("url") for media in tweet_data_from_extractor.get("media_urls", []) if media.get("type") == "photo"]
            
            for i, media_url_or_path in enumerate(media_urls[:4]): # 最大4つまで
                notion_item_data[f"画像URL{i+1}"] = media_url_or_path 
                # TODO: もし extractor がGoogle DriveのURLを返せるならそれを使う。現状はローカルパスか元URL

            try:
                # NotionCompiler の add_compiled_item を使用
                created_page = self.notion_compiler.add_compiled_item(notion_item_data)
                if created_page:
                    self.processed_tweet_ids_cache.add(tweet_id) # 正常処理後にキャッシュに追加
                    results["success"] += 1
                    processed_count_in_current_run += 1
                    self.logger.info(f"✅ ツイート {tweet_id} をNotionに正常に保存しました。Page ID: {created_page.get('id')}")
                else:
                    self.logger.error(f"❌ ツイート {tweet_id} のNotionへの保存に失敗しました (add_compiled_itemがNoneを返却)。")
                    results["failed"] += 1 # add_compiled_item が None を返した場合もfailedとしてカウント

            except Exception as e:
                self.logger.error(f"❌ ツイート {tweet_id} のNotionへの保存中に予期せぬエラー: {e}", exc_info=True)
                results["failed"] += 1

        return results

    # _is_duplicate は compile_and_save_tweets 内で直接キャッシュを見ているので不要
    # _is_ad_post は extract_tweets_bot 側で処理するので不要

    def cleanup(self):
        """リソースのクリーンアップ (現在は特に何もしない)"""
        self.logger.info("🧹 TweetCompilerのクリーンアップを実行します。")
        # self.notion_compiler = None # 必要に応じて

if __name__ == '__main__':
    print("--- TweetCompiler クラスのテスト (NotionCompilerを使用) ---")
    # このテストを実行する前に、config.yml に compile_bot と notion の設定がされていることを確認

    # ダミーのbot_config (実際はconfig_loaderから取得)
    # compile_bot セクションと、その中に notion セクション (またはトップレベルのnotionセクション) が必要
    try:
        from config import config_loader
        test_bot_name = "compile_bot" # またはテスト用のボット名
        bot_config_for_test = config_loader.get_bot_config(test_bot_name)
        if not bot_config_for_test:
            # もし compile_bot の設定がなければ、curate_bot の設定を流用し、必要な部分を書き換えるか、
            # グローバルのnotion設定を使うなどフォールバックを検討
            # ここではエラーとしておく
            raise ValueError(f"{test_bot_name} の設定が config.yml に見つかりません。")
        
        # loggerのセットアップ
        main_logger = setup_logger(log_dir_name=f'bots/{test_bot_name}/logs', logger_name=f'{test_bot_name}_test_main')
        compiler = TweetCompiler(bot_config=bot_config_for_test, parent_logger=main_logger)
        
        main_logger.info("TweetCompilerの初期化完了")
        compiler.setup_notion_compiler()
        main_logger.info("NotionCompilerのセットアップ完了")

    except Exception as e_init:
        print(f"テスト初期化中にエラー: {e_init}")
        # logger が使えるなら logger.error(..., exc_info=True) を使う
        if 'main_logger' in locals(): main_logger.error(f"テスト初期化中にエラー: {e_init}", exc_info=True)
        exit()

    # --- テスト用ツイートデータ --- 
    # TweetExtractorからの出力形式を模倣する
    import datetime
    sample_tweets_from_extractor = [
        {
            "id": "test_tweet_id_001",
            "text": "これは最初のテストツイートです。コンパイル処理のテスト用。",
            "timestamp": datetime.datetime.now().isoformat(),
            "author_name": "Test Author One",
            "author_username": "testauthor1",
            "media_urls": [{"type": "photo", "url": "http://example.com/image1.jpg"}], # extractorからの元URL
            "local_media_paths": ["/path/to/local/image1.jpg"], # extractorがDLした場合のパス
            "ocr_text": "画像1のOCRテキストです"
        },
        {
            "id": "test_tweet_id_002",
            "text": "これは二番目のテストツイート。メディアなし、OCRもなし。",
            "timestamp": (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat(),
            "author_name": "Test Author Two",
            "author_username": "testauthor2",
            "media_urls": [],
            "local_media_paths": [],
            "ocr_text": None
        },
        {
            "id": "already_processed_id_999", # Notionに既に存在するIDを模倣 (テストDBにあれば)
            "text": "これは処理済みのはずのツイート。",
            "timestamp": (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(),
            "author_name": "Processed Author",
            "author_username": "processeduser",
            "media_urls": [], "local_media_paths": [], "ocr_text": None
        }
    ]
    # 処理済みIDキャッシュに手動で追加 (テストのため)
    # compiler.processed_tweet_ids_cache.add("already_processed_id_999") 
    # ↑ setup_notion_compiler() でロードされるので、そちらで確認するか、テストDBに事前に入れておく

    main_logger.info(f"処理対象のサンプルツイートデータ数: {len(sample_tweets_from_extractor)}")
    main_logger.info(f"現在の処理済みIDキャッシュ(Notionからロード後): {compiler.processed_tweet_ids_cache}")

    # --- コンパイルと保存処理の実行 --- 
    # Notionへの実際の書き込みを伴うため、テストDBに対して行うこと。
    # max_items_to_process を調整してテスト件数を制御。
    results = compiler.compile_and_save_tweets(sample_tweets_from_extractor, max_items_to_process=2)

    main_logger.info("=== コンパイル処理結果 ===")
    main_logger.info(f"成功: {results.get('success')}")
    main_logger.info(f"失敗: {results.get('failed')}")
    main_logger.info(f"スキップ: {results.get('skipped')}")
    main_logger.info(f"重複: {results.get('duplicated')}")

    # 期待される結果の確認 (例)
    # - test_tweet_id_001 と test_tweet_id_002 が成功 (success: 2)
    # - already_processed_id_999 が重複 (duplicated: 1) (setup_notion_compiler でロードされていれば)
    #   (max_items_to_process=2 のため、already_processed_id_999 はそもそも処理対象にならない場合もある)

    compiler.cleanup()
    main_logger.info("--- TweetCompiler テスト完了 ---") 