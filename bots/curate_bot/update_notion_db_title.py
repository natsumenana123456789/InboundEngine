import json
import os
from notion_client import Client

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.json')

def load_config():
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"❌ 設定ファイルが見つかりません: {CONFIG_FILE_PATH}")
        return None
    with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    config = load_config()
    if not config:
        return

    notion_config = config.get('notion', {})
    NOTION_TOKEN = notion_config.get('token')
    DATABASE_ID = notion_config.get('databases', {}).get('curation')
    NEW_TITLE = "投稿収集DB"

    if not NOTION_TOKEN:
        print("❌ Notionトークンが設定ファイルに見つかりません。")
        return
    if not DATABASE_ID:
        print("❌ NotionのデータベースID (curation) が設定ファイルに見つかりません。")
        return

    notion = Client(auth=NOTION_TOKEN)

    try:
        print(f"🔄 データベースID: {DATABASE_ID} のタイトルを「{NEW_TITLE}」に変更します...")
        notion.databases.update(
            database_id=DATABASE_ID,
            title=[{"type": "text", "text": {"content": NEW_TITLE}}]
        )
        print(f"✅ データベースのタイトルを「{NEW_TITLE}」に変更しました。")
    except Exception as e:
        print(f"❌ Notionデータベースのタイトル変更に失敗しました: {e}")

if __name__ == "__main__":
    main() 