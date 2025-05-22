import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from .notion_writer import NotionWriter

class TweetProcessor:
    def __init__(self, config):
        self.config = config
        self.notion_config = config.get("notion", {})
        self.notion_writer = None
        self.registered_ids_map = {}

    def setup_notion(self):
        """Notionライターの設定"""
        notion_token = self.notion_config.get("token")
        database_id = self.notion_config.get("databases", {}).get("curation")
        if not notion_token or not database_id:
            print("⚠️ NotionのトークンまたはデータベースIDが設定されていません。Notionへの保存はスキップされます。")
            self.notion_writer = None
            return None
        self.notion_writer = NotionWriter(notion_token, database_id)
        return self.notion_writer

    def process_tweets(self, tweets: List[Dict], target_count: int) -> Dict[str, int]:
        """ツイートの処理と保存"""
        results = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "duplicated": 0
        }

        for tweet in tweets:
            try:
                # 重複チェック
                if self._is_duplicate(tweet["id"]):
                    results["duplicated"] += 1
                    continue

                # 広告チェック
                if self._is_ad_post(tweet.get("text", "")):
                    results["skipped"] += 1
                    continue

                # データの保存
                if self.notion_writer:
                    media_to_write = None
                    if tweet.get("media_urls"):
                        # Take the first URL from the list for the Notion URL property
                        media_to_write = tweet["media_urls"][0]
                    
                    success = self.notion_writer.add_post({
                        "ID": tweet["id"],
                        "投稿日時": tweet.get("created_at", ""),
                        "本文": tweet.get("text", ""),
                        "画像/動画URL": media_to_write, # Pass the single URL string
                        "投稿者": tweet.get("username", ""),
                        "取得日時": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                        "ステータス": "新規"
                    })
                    if success:
                        results["success"] += 1
                    else:
                        results["failed"] += 1

                # 目標数に達したら終了
                if results["success"] >= target_count:
                    break

            except Exception as e:
                print(f"⚠️ ツイート処理中にエラー: {str(e)}")
                results["failed"] += 1
                continue

        return results

    def _is_duplicate(self, tweet_id: str) -> bool:
        """重複チェック"""
        if tweet_id in self.registered_ids_map:
            return True
        self.registered_ids_map[tweet_id] = True
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
            self.notion_writer = None 