import json
from notion_client import Client
import os

# 設定ファイルのパスを固定
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.json')

def load_config():
    """設定ファイルを読み込む"""
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"❌ 設定ファイルが見つかりません: {CONFIG_FILE_PATH}")
        return None
    with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_database_id(config, database_id):
    """設定ファイルに新しいデータベースIDを保存する"""
    if not config:
        print("❌ 設定オブジェクトがNoneのため、データベースIDを保存できません。")
        return
    # Notion設定部分を取得、なければ作成
    if 'notion' not in config:
        config['notion'] = {}
    if 'databases' not in config['notion']:
        config['notion']['databases'] = {}
    
    config['notion']['databases']['curation'] = database_id
    with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"✅ 新しいデータベースID {database_id} を {CONFIG_FILE_PATH} に保存しました。")

def main():
    config = load_config()
    if not config:
        return

    notion_config = config.get('notion', {})
    NOTION_TOKEN = notion_config.get('token')
    PARENT_PAGE_ID = notion_config.get('parent_page_id')

    if not NOTION_TOKEN:
        print("❌ Notionトークンが設定ファイルに見つかりません。")
        return
    if not PARENT_PAGE_ID:
        print("❌ Notionの親ページIDが設定ファイルに見つかりません。")
        return

    notion = Client(auth=NOTION_TOKEN)
    try:
        db = notion.databases.create(
            parent={"type": "page_id", "page_id": PARENT_PAGE_ID},
            title=[{"type": "text", "text": {"content": "投稿収集DB"}}],
            properties={
                "ID": {"title": {}},
                "投稿日時": {"rich_text": {}},
                "本文": {"rich_text": {}},
                "画像/動画URL": {"rich_text": {}},
                "投稿者": {"rich_text": {}},
                "取得日時": {"date": {}},
                "ステータス": {
                    "select": {
                        "options": [
                            {"name": "新規", "color": "blue"},
                            {"name": "処理済み", "color": "green"}
                        ]
                    }
                }
            }
        )
        database_id = db["id"]
        print("新しいDBのID:", database_id)
        print("Notion上のURL: https://www.notion.so/" + database_id.replace("-", ""))
        save_database_id(config, database_id)
    except Exception as e:
        print(f"❌ Notionデータベースの作成に失敗しました: {e}")

if __name__ == "__main__":
    main() 