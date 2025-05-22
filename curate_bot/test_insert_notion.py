import json
from notion_writer import NotionWriter
from datetime import datetime

CONFIG_PATH = "curate_bot/config.json"

def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    notion_token = config["NOTION_TOKEN"]
    database_id = config["NOTION_DATABASE_ID"]
    writer = NotionWriter(notion_token, database_id)
    test_post = {
        "ID": "test123456",
        "投稿日時": "2024-06-01 12:34",
        "本文": "これはテスト投稿です。",
        "画像/動画URL": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"],
        "投稿者": "test_user",
        "取得日時": datetime.now().isoformat(),
        "ステータス": "新規"
    }
    success = writer.add_post(test_post)
    if success:
        print("✅ テストデータをNotion DBに挿入しました。")
    else:
        print("❌ 挿入に失敗しました。")

if __name__ == "__main__":
    main() 