import json
from notion_writer import NotionWriter
from datetime import datetime
import os # 設定ファイルのパス解決のために追加

# CONFIG_PATH = "curate_bot/config.json" # 古いパス
# 設定ファイルのパスを config/settings.json に変更
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.json')

def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ 設定ファイルが見つかりません: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    notion_config = config.get('notion', {})
    notion_token = notion_config.get("token")
    # データベースIDは 'curation' キーから取得
    database_id = notion_config.get('databases', {}).get('curation')

    if not notion_token:
        print("❌ Notionトークンが設定ファイルに見つかりません。")
        return
    if not database_id:
        print("❌ NotionデータベースID (curation) が設定ファイルに見つかりません。")
        return

    writer = NotionWriter(notion_token, database_id)

    # ---- スキーマ更新 (初回実行時やスキーマ変更時にコメントを外して実行) ----
    print("スキーマを更新しますか？ (yes/no)") # スキーマ更新を再度有効化
    choice = input().lower()
    if choice == 'yes':
        print("データベーススキーマを更新しています...")
        if writer.update_database_schema():
            print("スキーマの更新が完了しました。再度スクリプトを実行して投稿テストを行ってください。")
        else:
            print("スキーマの更新に失敗しました。エラーを確認してください。")
        return # スキーマ更新後は一旦終了
    else:
        print("スキーマ更新をスキップしました。")
    # ---- スキーマ更新ここまで ----

    print(f"データベース {database_id} への投稿テストを開始します。")

    # OCRテスト用の画像URLと期待されるテキスト
    ocr_test_image_url = "https://www.bannerbatterien.com/upload/filecache/Banner-Batterien-Logo-jpg_0x0_100_c53520092348a5ce143f9a11da8e1376.jpg"
    expected_ocr_text_partial = "Banner"

    test_post_ocr = {
        "ID": "test_ocr_001",
        "投稿日時": "2024-07-15 10:00",
        "本文": "OCR機能のテスト投稿です。画像に 'Banner' という文字が含まれているはずです。",
        "画像/動画URL": [ocr_test_image_url],
        "投稿者": "test_user_ocr",
        "取得日時": datetime.now().isoformat(),
        "ステータス": "新規",
        # "OCRテキスト" は processor側で自動的に付与されるので、ここでは指定しない
    }
    
    # 既存のテストデータも残す場合 (Google DriveのURLテストなど)
    test_gdrive_url = "https://drive.google.com/file/d/1uv-Ejpg6mXeX0Zoi367-KWsfG83oDyyj/view?usp=sharing"
    test_post_1_image = {
        "ID": "test_gdrive_image_001",
        "投稿日時": "2024-07-01 10:00",
        "本文": "Google Drive URLのテスト投稿です。",
        "画像/動画URL": [test_gdrive_url],
        "投稿者": "test_user_gdrive",
        "取得日時": datetime.now().isoformat(),
        "ステータス": "新規"
    }
    
    # 複数の画像URLを持つテストデータ (4つまでテスト)
    placeholder_base = "https://via.placeholder.com/150"
    test_post_4_images = {
        "ID": "test_multi_image_004",
        "投稿日時": "2024-07-01 12:00",
        "本文": "最大4つの画像URLを持つテスト投稿です。",
        "画像/動画URL": [
            f"{placeholder_base}/FF0000/FFFFFF?Text=Img1",
            f"{placeholder_base}/00FF00/000000?Text=Img2",
            f"{placeholder_base}/0000FF/FFFFFF?Text=Img3",
            f"{placeholder_base}/FFFF00/000000?Text=Img4"
        ],
        "投稿者": "test_user_multi",
        "取得日時": datetime.now().isoformat(),
        "ステータス": "新規"
    }
    
    # 画像なしのテストデータ
    test_post_no_image = {
        "ID": "test_no_image_001",
        "投稿日時": "2024-07-01 13:00",
        "本文": "画像URLがないテスト投稿です。",
        "画像/動画URL": [], # 空のリスト
        "投稿者": "test_user_no_image",
        "取得日時": datetime.now().isoformat(),
        "ステータス": "新規"
    }

    posts_to_test = [
        test_post_1_image, 
        test_post_4_images,
        test_post_no_image,
        test_post_ocr # OCRテスト用の投稿を追加
    ]

    all_successful = True
    for i, test_post_data in enumerate(posts_to_test):
        print(f"\n--- テスト投稿 {i+1} ({test_post_data.get('ID')}) を実行中 ---")
        
        # tweet_processor.pyの process_tweets を模倣してOCR処理を呼び出す
        # 本来は TweetProcessor をインスタンス化して使うが、ここでは簡易的に NotionWriter に直接渡す
        # process_tweets 側で ocr_text が付与されるので、ここでの test_post_data には "OCRテキスト" は不要
        
        # Notionに書き込むデータを作成 (TweetProcessor内での処理を想定)
        notion_post_data = {
            "ID": test_post_data.get("ID"),
            "投稿日時": test_post_data.get("投稿日時"),
            "本文": test_post_data.get("本文"),
            "画像/動画URL": test_post_data.get("画像/動画URL", []),
            "投稿者": test_post_data.get("投稿者"),
            "取得日時": test_post_data.get("取得日時"),
            "ステータス": test_post_data.get("ステータス"),
        }
        
        # OCR処理のシミュレーション (本来はTweetProcessorが行う)
        # test_insert_notion.py は NotionWriter のテストが主目的なので、
        # OCR処理自体は ocr_utils や tweet_processor に任せる。
        # ここでは、OCR対象の投稿の場合のみ、期待値を設定する。
        
        # NotionWriterに渡す前に、OCR処理を実行 (tweet_processor.py の処理を模倣)
        # このテストスクリプトでは直接 NotionWriter を使うため、OCR処理もここで行う
        from ocr_utils import ocr_images_from_urls # ここでインポート
        ocr_text_result_for_writer = None
        if test_post_data.get("画像/動画URL"):
            ocr_text_result_for_writer = ocr_images_from_urls(test_post_data.get("画像/動画URL"))
        notion_post_data["OCRテキスト"] = ocr_text_result_for_writer
        
        created_page = writer.add_post(notion_post_data)
        
        if created_page:
            print(f"✅ テスト投稿 {test_post_data.get('ID')} をNotion DBに挿入しました (Page ID: {created_page.get('id')})。")
            inserted_properties = created_page.get("properties", {})
            
            # URLの検証
            expected_urls = test_post_data.get("画像/動画URL", [])
            urls_match = True
            for url_idx in range(1, 5):
                prop_key = f"画像URL{url_idx}"
                inserted_url_obj = inserted_properties.get(prop_key, {})
                inserted_url = inserted_url_obj.get("url")
                
                expected_single_url = None
                if url_idx -1 < len(expected_urls):
                    expected_single_url = expected_urls[url_idx-1]
                
                if inserted_url != expected_single_url: # None同士もOK
                    print(f"   ❌ URL検証エラー: {prop_key} - 期待値: {expected_single_url}, 実際値: {inserted_url}")
                    urls_match = False
                    all_successful = False
            if urls_match:
                print("   ✅ 画像URLは期待通りに挿入されました。")

            # OCRテキストの検証 (test_post_ocr の場合のみ)
            if test_post_data.get("ID") == "test_ocr_001":
                ocr_prop_data = inserted_properties.get("OCRテキスト", {}).get("rich_text", [])
                inserted_ocr_text = ""
                if ocr_prop_data and isinstance(ocr_prop_data, list) and len(ocr_prop_data) > 0:
                    inserted_ocr_text = ocr_prop_data[0].get("text", {}).get("content", "")
                
                if expected_ocr_text_partial.lower() in inserted_ocr_text.lower():
                    print(f"   ✅ OCRテキスト検証成功: 期待した文字列 '{expected_ocr_text_partial}' が含まれています。")
                    print(f"      実際のOCRテキスト: {inserted_ocr_text[:200]}...") # 長い場合は一部表示
                else:
                    print(f"   ❌ OCRテキスト検証エラー: 期待した文字列 '{expected_ocr_text_partial}' が含まれていません。")
                    print(f"      実際のOCRテキスト: {inserted_ocr_text[:200]}...")
                    all_successful = False
        
        else:
            print(f"❌ テスト投稿 {test_post_data.get('ID')} の挿入に失敗しました。")
            all_successful = False

    if all_successful:
        print("\n🎉 全てのテストが成功しました！")
    else:
        print("\n⚠️ いくつかのテストで問題が発生しました。ログを確認してください。")

if __name__ == "__main__":
    main() 