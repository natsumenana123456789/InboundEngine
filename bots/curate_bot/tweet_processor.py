import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from .notion_writer import NotionWriter
from .ocr_utils import ocr_images_from_urls
from ...utils.logger import setup_logger
# import logging # loggerを引数で受け取る

class TweetProcessor:
    def __init__(self, bot_config, parent_logger=None):
        self.bot_config = bot_config
        self.logger = parent_logger if parent_logger else setup_logger(log_dir_name='bots/curate_bot/logs', logger_name='TweetProcessor_default')
        
        self.notion_config = self.bot_config.get("notion", {})
        self.gdrive_config = self.bot_config.get("google_drive", {})
        self.scraping_config = self.bot_config.get("scraping", {})

        # NotionWriter に bot_config を渡して初期化
        self.notion_writer = NotionWriter(self.bot_config, self.logger)
        self.processed_tweet_ids_cache = set() # 処理済みIDのキャッシュ (NotionWriterと共有も検討)

    def setup_notion(self):
        """NotionクライアントのセットアップやDBスキーマの確認・更新を行う"""
        try:
            # NotionWriterの初期化時にスキーマ更新が行われる場合があるため、ここでは呼び出しのみ
            self.notion_writer.ensure_database_schema() # スキーマ保証メソッドを呼び出す
            self.logger.info("✅ Notionセットアップ完了 (スキーマ確認含む)")
            # 処理済みIDをNotionからロードする (NotionWriterが担当しても良い)
            self.processed_tweet_ids_cache = self.notion_writer.load_processed_tweet_ids()
            self.logger.info(f"Notionから {len(self.processed_tweet_ids_cache)} 件の処理済みツイートIDをロードしました。")
        except Exception as e:
            self.logger.error(f"❌ Notionのセットアップ中にエラー: {e}", exc_info=True)
            # 必要であればここでプログラムを停止させるか、エラー処理を行う
            raise

    def process_tweets(self, tweets_data, max_tweets_to_process):
        if not self.notion_writer or not self.notion_writer.is_client_initialized():
            self.logger.error("❌ Notionクライアントが初期化されていません。処理を中止します。")
            # self.setup_notion() # 再度セットアップを試みるか、エラーを投げる
            raise RuntimeError("Notionクライアントが初期化されていません。")

        results = {"success": 0, "failed": 0, "skipped": 0, "duplicated": 0}
        processed_count_in_current_run = 0

        for tweet in tweets_data:
            if processed_count_in_current_run >= max_tweets_to_process:
                self.logger.info(f"今回の実行での処理上限 ({max_tweets_to_process}件) に達しました。")
                break

            tweet_id = tweet.get("id")
            if not tweet_id:
                self.logger.warning("IDがないツイートデータはスキップします。")
                results["skipped"] += 1
                continue

            if tweet_id in self.processed_tweet_ids_cache:
                self.logger.info(f"重複ツイート: {tweet_id} は既に処理済みです。スキップします。")
                results["duplicated"] += 1
                continue
            
            ocr_text_results = []
            if self.scraping_config.get("ocr_enabled", False) and tweet.get("media_urls"):
                self.logger.info(f"OCR処理を開始します (ツイートID: {tweet_id})。メディア数: {len(tweet.get('media_urls'))}")
                try:
                    # ocr_images_from_urls は bot_config を必要としない想定 (ロガーは渡す)
                    ocr_text_results = ocr_images_from_urls(tweet.get("media_urls", []), self.logger)
                    self.logger.info(f"OCR結果 (ツイートID: {tweet_id}): {len(ocr_text_results)}件のテキスト抽出")
                except Exception as e_ocr:
                    self.logger.error(f"❌ OCR処理中にエラーが発生しました (ツイートID: {tweet_id}): {e_ocr}", exc_info=True)
                    # OCRエラーは処理継続、テキストは空になる
            
            # OCR結果を結合して1つの文字列にする (Notionの1プロパティに保存するため)
            final_ocr_text = "\n\n---\n\n".join(ocr_text_results).strip() if ocr_text_results else None

            try:
                self.notion_writer.add_post(
                    tweet_id=tweet_id,
                    text=tweet.get("text", ""),
                    user=tweet.get("user", "unknown"),
                    tweet_url=tweet.get("url", ""),
                    media_urls=tweet.get("media_urls", []),
                    created_at_str=tweet.get("created_at"), # created_atは文字列で渡される想定
                    ocr_text=final_ocr_text
                )
                self.processed_tweet_ids_cache.add(tweet_id) # 正常処理後にキャッシュに追加
                results["success"] += 1
                processed_count_in_current_run += 1
                self.logger.info(f"✅ ツイート {tweet_id} をNotionに正常に投稿しました。OCRテキスト長: {len(final_ocr_text) if final_ocr_text else 0}")
            except Exception as e:
                self.logger.error(f"❌ ツイート {tweet_id} のNotionへの投稿中にエラー: {e}", exc_info=True)
                results["failed"] += 1
        
        return results

    def _is_duplicate(self, tweet_id: str) -> bool:
        """重複チェック"""
        if tweet_id in self.processed_tweet_ids_cache:
            return True
        return False

    def _is_ad_post(self, text: str) -> bool:
        """広告投稿の判定"""
        if not text:
            return False
        lowered = text.lower()
        ad_keywords = [
            "r10.to", "ふるさと納税", "カードローン", "お金借りられる",
            "ビューティガレージ", "UNEXT", "エコオク", "#PR",
            "楽天", "Amazon", "A8", "アフィリエイト", "副業",
            "bit.ly", "shp.ee", "t.co/"
        ]
        return any(k.lower() in lowered for k in ad_keywords)

    def cleanup(self):
        """リソースのクリーンアップ"""
        if self.notion_writer:
            self.logger.info("🧹 TweetProcessorのクリーンアップを実行します。")
            self.notion_writer = None 