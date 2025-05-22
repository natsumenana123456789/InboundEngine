from notion_client import Client
from datetime import datetime

class NotionWriter:
    def __init__(self, notion_token, database_id):
        self.notion = Client(auth=notion_token)
        self.database_id = database_id

    def update_database_schema(self):
        """
        Notionデータベースのスキーマを更新します。
        既存の「画像/動画URL」プロパティを削除し、
        新たに「画像URL1」から「画像URL4」までのURLプロパティと、
        「OCRテキスト」プロパティ（リッチテキスト型）を追加します。
        """
        try:
            current_db = self.notion.databases.retrieve(database_id=self.database_id)
            current_properties = current_db.get("properties", {})

            updated_properties = {}
            # 既存のプロパティを維持しつつ、「画像/動画URL」を除外
            for name, prop_data in current_properties.items():
                if name != "画像/動画URL":
                    updated_properties[name] = prop_data 

            # 新しい画像URLプロパティを追加
            for i in range(1, 5):
                prop_name = f"画像URL{i}"
                updated_properties[prop_name] = {"url": {}}
            
            # OCRテキストプロパティを追加
            updated_properties["OCRテキスト"] = {"rich_text": {}}
            
            # タイトルプロパティが必須なので、もしなければ追加
            if "ID" not in updated_properties or "title" not in updated_properties.get("ID", {}):
                 updated_properties["ID"] = {"title": {}}

            self.notion.databases.update(
                database_id=self.database_id,
                properties=updated_properties
            )
            print(f"✅ データベース {self.database_id} のスキーマを更新しました。")
            print("新しいプロパティ: 画像URL1-4 (URLタイプ), OCRテキスト (リッチテキストタイプ)")
            if "画像/動画URL" in current_properties:
                print("古いプロパティ「画像/動画URL」はスキーマから削除されました（もし存在していれば）。")
            return True
        except Exception as e:
            print(f"❌ データベーススキーマの更新に失敗しました: {e}")
            return False

    def add_post(self, post_data):
        try:
            properties = {
                "ID": {"title": [{"text": {"content": post_data.get("ID", "")}}]},
                "投稿日時": {"rich_text": [{"text": {"content": post_data.get("投稿日時", "")}}]},
                "本文": {"rich_text": [{"text": {"content": post_data.get("本文", "")}}]},
                "投稿者": {"rich_text": [{"text": {"content": post_data.get("投稿者", "")}}]},
                "取得日時": {"date": {"start": post_data.get("取得日時", datetime.now().isoformat())}},
                "ステータス": {"select": {"name": post_data.get("ステータス", "新規")}},
            }
            
            image_urls = post_data.get("画像/動画URL", [])
            for i in range(1, 5):
                prop_name = f"画像URL{i}"
                if i -1 < len(image_urls):
                    properties[prop_name] = {"url": image_urls[i-1] if image_urls[i-1] else None}
                else:
                    properties[prop_name] = {"url": None}
            
            # OCRテキストの処理
            ocr_text_content = post_data.get("OCRテキスト")
            if ocr_text_content:
                properties["OCRテキスト"] = {"rich_text": [{"text": {"content": ocr_text_content}}]}
            else:
                # OCRテキストがない場合もプロパティ自体は存在させる（空のrich_text）
                properties["OCRテキスト"] = {"rich_text": []} 

            created_page = self.notion.pages.create(parent={"database_id": self.database_id}, properties=properties)
            return created_page 
        except Exception as e:
            print(f"Notionへの書き込み失敗: {e}")
            return None 

    def _format_media_urls(self, url): # このメソッドは現在未使用ですが、残しておきます。
        return str(url) if url else None 