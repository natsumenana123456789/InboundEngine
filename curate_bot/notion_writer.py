from notion_client import Client
from datetime import datetime

class NotionWriter:
    def __init__(self, notion_token, database_id):
        self.notion = Client(auth=notion_token)
        self.database_id = database_id

    def add_post(self, post_data):
        try:
            properties = {
                "ID": {"title": [{"text": {"content": post_data.get("ID", "")}}]},
                "投稿日時": {"rich_text": [{"text": {"content": post_data.get("投稿日時", "")}}]},
                "本文": {"rich_text": [{"text": {"content": post_data.get("本文", "")}}]},
                "画像/動画URL": {"url": post_data.get("画像/動画URL") if post_data.get("画像/動画URL") else None},
                "投稿者": {"rich_text": [{"text": {"content": post_data.get("投稿者", "")}}]},
                "取得日時": {"date": {"start": post_data.get("取得日時", datetime.now().isoformat())}},
                "ステータス": {"select": {"name": post_data.get("ステータス", "新規")}},
            }
            self.notion.pages.create(parent={"database_id": self.database_id}, properties=properties)
            return True
        except Exception as e:
            print(f"Notionへの書き込み失敗: {e}")
            return False

    def _format_media_urls(self, url):
        return str(url) if url else None 