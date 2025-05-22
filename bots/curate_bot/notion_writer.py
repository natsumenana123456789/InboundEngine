import os
import re
from notion_client import Client, APIErrorCode, APIResponseError
import datetime
from ...utils.logger import setup_logger # 共通ロガー
# from ...config import config_loader # ここでの直接参照は不要になる想定

class NotionWriter:
    def __init__(self, bot_config, parent_logger=None):
        self.bot_config = bot_config
        self.logger = parent_logger if parent_logger else setup_logger(log_dir_name='bots/curate_bot/logs', logger_name='NotionWriter_default')

        notion_specific_config = self.bot_config.get("notion", {})
        self.notion_token = notion_specific_config.get("token")
        # どのDBを使用するかは bot_config の scraping.extract_target や notion.databases から解決する必要がある
        # ここでは curation_main をデフォルトとするが、より動的にすべきケースもある
        self.database_id = notion_specific_config.get("databases", {}).get("curation_main")
        
        self.client = None
        if self.notion_token and self.database_id:
            try:
                self.client = Client(auth=self.notion_token)
                self.logger.info(f"✅ Notionクライアントの初期化に成功しました。DB ID: {self.database_id}")
            except Exception as e:
                self.logger.error(f"❌ Notionクライアントの初期化中にエラー: {e}", exc_info=True)
                self.client = None # 初期化失敗時はNoneに設定
        else:
            self.logger.warning("⚠️ NotionのトークンまたはデータベースIDが設定されていません。Notion機能は無効になります。")

        # 期待されるプロパティ定義 (ensure_database_schema で使用)
        self.expected_properties = {
            "ツイートID": {"title": {}},
            "本文": {"rich_text": {}},
            "投稿者": {"rich_text": {}},
            "ツイートURL": {"url": {}},
            "投稿日時": {"date": {}},
            "画像URL1": {"url": {}},
            "画像URL2": {"url": {}},
            "画像URL3": {"url": {}},
            "画像URL4": {"url": {}},
            "OCRテキスト": {"rich_text": {}},
            "ステータス": {"select": {"options": [
                {"name": "新規", "color": "blue"},
                {"name": "処理済", "color": "green"},
                {"name": "エラー", "color": "red"}
            ]}},
            "最終更新日時": {"last_edited_time": {}} # これも追加しておくと便利
        }

    def is_client_initialized(self):
        return self.client is not None

    def ensure_database_schema(self):
        if not self.is_client_initialized():
            self.logger.error("Notionクライアントが初期化されていないため、スキーマを確認できません。")
            return
        
        self.logger.info(f"データベース {self.database_id} のスキーマを確認・更新します...")
        try:
            db_info = self.client.databases.retrieve(database_id=self.database_id)
            current_properties = db_info['properties']
            
            properties_to_update = {}
            needs_update = False

            # 既存プロパティをチェックし、不足または型が異なる場合は更新対象に追加
            for name, expected_type_details in self.expected_properties.items():
                expected_type_key = list(expected_type_details.keys())[0] # 例: "title", "rich_text", "url"
                if name not in current_properties or current_properties[name]['type'] != expected_type_key:
                    self.logger.info(f"  プロパティ '{name}' (型: {expected_type_key}) を追加/更新します。")
                    properties_to_update[name] = expected_type_details
                    needs_update = True
                elif name == "ステータス" and expected_type_key == "select": # selectの場合、オプションも確認
                    current_options = {opt['name'] for opt in current_properties[name]['select']['options']}
                    expected_options = {opt['name'] for opt in expected_type_details['select']['options']}
                    if not expected_options.issubset(current_options):
                        self.logger.info(f"  プロパティ '{name}' の選択肢を更新します。")
                        properties_to_update[name] = expected_type_details # 型ごと更新
                        needs_update = True
            
            # 古いメディアURLプロパティ（例：「画像/動画URL」）があれば削除も検討できるが、ここでは追加のみ

            if needs_update:
                self.logger.info("スキーマの更新を実行します...")
                self.client.databases.update(database_id=self.database_id, properties=properties_to_update)
                self.logger.info("✅ データベーススキーマの更新が完了しました。")
            else:
                self.logger.info("✅ データベーススキーマは最新です。更新は不要です。")

        except APIResponseError as e:
            if e.code == APIErrorCode.ObjectNotFound:
                self.logger.error(f"❌ 指定されたデータベースIDが見つかりません: {self.database_id}")
            else:
                self.logger.error(f"❌ データベーススキーマの確認・更新中にAPIエラーが発生しました: {e}", exc_info=True)
            raise # エラーを再送出
        except Exception as e:
            self.logger.error(f"❌ データベーススキーマの確認・更新中に予期せぬエラーが発生しました: {e}", exc_info=True)
            raise # エラーを再送出

    def load_processed_tweet_ids(self):
        if not self.is_client_initialized():
            self.logger.warning("Notionクライアント未初期化のため、処理済みIDをロードできません。")
            return set()

        processed_ids = set()
        try:
            self.logger.info(f"データベース {self.database_id} から処理済みツイートIDをロードしています...")
            # "ツイートID" プロパティを持つページを検索 (ページング対応が必要な場合がある)
            has_more = True
            start_cursor = None
            while has_more:
                response = self.client.databases.query(
                    database_id=self.database_id,
                    filter={"property": "ツイートID", "title": {"is_not_empty": True}},
                    page_size=100, # 一度に取得する件数
                    start_cursor=start_cursor
                )
                for page in response.get("results", []):
                    title_property = page.get("properties", {}).get("ツイートID", {}).get("title", [])
                    if title_property and len(title_property) > 0:
                        tweet_id = title_property[0].get("plain_text")
                        if tweet_id:
                            processed_ids.add(tweet_id)
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
            self.logger.info(f"ロード完了: {len(processed_ids)} 件の処理済みツイートIDが見つかりました。")
        except Exception as e:
            self.logger.error(f"❌ Notionからの処理済みツイートIDのロード中にエラー: {e}", exc_info=True)
            # エラーが発生しても空のセットを返す (処理が継続できるように)
        return processed_ids

    def add_post(self, tweet_id: str, text: str, user: str, tweet_url: str, media_urls: list, created_at_str: str = None, ocr_text: str = None):
        if not self.is_client_initialized():
            self.logger.error("Notionクライアントが初期化されていないため、投稿を追加できません。")
            return None # 失敗を示す

        page_properties = {
            "ツイートID": {"title": [{"text": {"content": tweet_id}}]}, 
            "本文": {"rich_text": [{"text": {"content": text[:2000]}}]}, # Notionのrich_textは2000字制限
            "投稿者": {"rich_text": [{"text": {"content": user}}]}, 
            "ツイートURL": {"url": tweet_url if tweet_url else None},
            "ステータス": {"select": {"name": "新規"}}
        }

        if created_at_str:
            try:
                # ISO 8601形式の文字列からdatetimeオブジェクトに変換し、再度ISO形式で設定
                # Twitter API v2 は通常 `YYYY-MM-DDTHH:mm:ss.sssZ` の形式
                dt_object = datetime.datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                page_properties["投稿日時"] = {"date": {"start": dt_object.isoformat()}}
            except ValueError as e:
                self.logger.warning(f"投稿日時文字列 '{created_at_str}' の形式が不正です: {e}。投稿日時は設定されません。")

        # 最大4つのメディアURLを設定
        for i in range(4):
            prop_name = f"画像URL{i+1}"
            if i < len(media_urls) and media_urls[i]:
                page_properties[prop_name] = {"url": media_urls[i]}
            else:
                page_properties[prop_name] = {"url": None} # 使わないURLはNoneでクリア
        
        if ocr_text:
            page_properties["OCRテキスト"] = {"rich_text": [{"text": {"content": ocr_text[:2000]}}]} # 2000字制限
        else:
            page_properties["OCRテキスト"] = {"rich_text": []} # 空のリストでクリア

        try:
            self.logger.info(f"Notionにページを作成中... ツイートID: {tweet_id}")
            created_page = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=page_properties
            )
            self.logger.info(f"✅ Notionにページが正常に作成されました。Page ID: {created_page['id']}, ツイートID: {tweet_id}")
            return created_page # 作成されたページオブジェクトを返す
        except APIResponseError as e:
            self.logger.error(f"❌ Notionへのページ作成中にAPIエラーが発生しました (ツイートID: {tweet_id}): {e.code} - {e.body}", exc_info=True)
        except Exception as e:
            self.logger.error(f"❌ Notionへのページ作成中に予期せぬエラーが発生しました (ツイートID: {tweet_id}): {e}", exc_info=True)
        return None # エラー時はNoneを返す

    def _format_media_urls(self, url): # このメソッドは現在未使用ですが、残しておきます。
        return str(url) if url else None 