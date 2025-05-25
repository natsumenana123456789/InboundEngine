import unittest
import os
import json
from datetime import datetime

# プロジェクトルートを基準にパスを設定
# このテストファイルは InboundEngine/tests/curate_bot/test_notion_writer.py にある想定
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# botsとutilsをsys.pathに追加してインポート可能にする
import sys
sys.path.insert(0, PROJECT_ROOT)

from bots.curate_bot.notion_writer import NotionWriter
from bots.curate_bot.ocr_utils import ocr_images_from_urls # OCR処理もテストするためインポート
from config import config_loader # 設定ローダーをインポート
from utils.logger import setup_logger # テスト用ロガー

# テスト用の設定ファイルパス (プロジェクトルートからの相対パス)
# CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config', 'settings.json') # config_loader が処理

class TestNotionWriter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """テストクラス全体の初期設定"""
        cls.config = config_loader.load_config()
        if not cls.config:
            # ロガーがまだ初期化されていない可能性があるため、標準出力にフォールバック
            print("ERROR: 設定ファイルが読み込めませんでした。テストをスキップします。")
            raise unittest.SkipTest("設定ファイルが読み込めませんでした。テストをスキップします。")

        # Notion設定の取得元を修正
        curate_bot_notion_config = cls.config.get('curate_bot', {}).get('notion', {})
        cls.notion_token = curate_bot_notion_config.get("token")
        cls.database_id = curate_bot_notion_config.get('databases', {}).get('curation_main') # キーを 'curation_main' に修正

        # ロガーを先に初期化
        cls.logger = setup_logger(log_dir_name='tests/logs', log_file_name='test_notion_writer.log', logger_name='TestNotionWriter')

        # デバッグログを出力
        cls.logger.info(f"DEBUG: Notion Token read from config: {cls.notion_token}")
        cls.logger.info(f"DEBUG: Database ID (curation_main) read from config: {cls.database_id}")

        if not cls.notion_token or not cls.database_id:
            cls.logger.error("❌ NotionのトークンまたはデータベースIDが設定ファイルから正しく読み取れませんでした。テストをスキップします。")
            raise unittest.SkipTest("NotionのトークンまたはデータベースIDが設定されていません。テストをスキップします。")

        # NotionWriterインスタンスを作成
        curate_bot_config = cls.config.get('curate_bot')
        if not curate_bot_config:
            cls.logger.error("❌ curate_bot の全体設定が読み込めませんでした。テストをスキップします。")
            raise unittest.SkipTest("curate_bot の設定が読み込めませんでした。")
        cls.writer = NotionWriter(curate_bot_config, cls.logger)

        # スキーマ更新を試みる
        try:
            cls.logger.info("テストクラス初期化時にデータベーススキーマの確認・更新を試みます...")
            cls.writer.ensure_database_schema()
        except Exception as e:
            cls.logger.error(f"スキーマ確認・更新中にエラーが発生しました: {e}")
            # スキーマ更新の失敗がテスト続行不可能と判断する場合はSkipTestも検討

        # スキーマ更新はここでは自動実行しない (手動または別途スクリプトで対応)
        # print("スキーマを更新しますか？ (yes/no)")
        # choice = input().lower()
        # if choice == 'yes':
        #     print("データベーススキーマを更新しています...")
        #     if cls.writer.update_database_schema():
        #         print("スキーマの更新が完了しました。")
        #     else:
        #         print("スキーマの更新に失敗しました。")
        #         raise unittest.SkipTest("スキーマ更新に失敗したため、以降のテストをスキップします。")

    def _create_base_post_data(self, post_id,本文, image_urls=None,投稿者="test_user"):
        """テスト用の基本的な投稿データを作成するヘルパーメソッド"""
        return {
            "ID": post_id,
            "投稿日時": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "本文":本文,
            "画像/動画URL": image_urls if image_urls else [], # TweetProcessorに渡す際のキー
            "投稿者":投稿者,
            "取得日時": datetime.now().isoformat(),
            "ステータス": "新規テスト", # テスト用のステータス
        }

    def _prepare_notion_post_data(self, raw_post_data):
        """NotionWriter.add_postに渡す形式のデータを作成 (OCR処理も含む)"""
        notion_data = {
            "ID": raw_post_data.get("ID"),
            "投稿日時": raw_post_data.get("投稿日時"),
            "本文": raw_post_data.get("本文"),
            "投稿者": raw_post_data.get("投稿者"),
            "取得日時": raw_post_data.get("取得日時"),
            "ステータス": raw_post_data.get("ステータス"),
        }
        
        media_urls = raw_post_data.get("画像/動画URL", [])
        # NotionWriterは画像URL1-4のキーを期待する
        for i in range(1, 5):
            if i - 1 < len(media_urls):
                notion_data[f"画像URL{i}"] = media_urls[i-1]
            else:
                notion_data[f"画像URL{i}"] = None

        ocr_text_result = None
        if media_urls:
            self.logger.info(f"テストケース {raw_post_data.get('ID')} のためOCR処理を実行: {media_urls}")
            ocr_text_result = ocr_images_from_urls(media_urls, self.logger)
        notion_data["OCRテキスト"] = ocr_text_result
        return notion_data

    def test_01_add_post_single_image(self):
        self.logger.info("\n--- test_add_post_single_image 開始 ---")
        gdrive_url = "https://www.publicdomainpictures.net/pictures/20000/velka/cat-looking-at-viewer.jpg" # OCRテスト用の直リンク画像に変更
        raw_data = self._create_base_post_data("test_single_001", "単一画像(直リンク)のテスト投稿。", [gdrive_url])
        # notion_data は add_post に直接渡さないが、OCRテキストの準備のために呼び出す
        prepared_notion_props = self._prepare_notion_post_data(raw_data) 
        
        created_page = self.writer.add_post(
            tweet_id=raw_data["ID"],
            text=raw_data["本文"],
            user=raw_data["投稿者"],
            tweet_url=f"https://twitter.com/{raw_data['投稿者']}/status/{raw_data['ID']}", # ダミーURL
            media_urls=raw_data["画像/動画URL"],
            created_at_str=raw_data["投稿日時"], # _create_base_post_data は %Y-%m-%d %H:%M 形式なのでISO形式に変換が必要かも
            ocr_text=prepared_notion_props["OCRテキスト"]
        )
        self.assertIsNotNone(created_page, "ページの作成に失敗しました。")
        self.assertEqual(created_page["properties"]["ツイートID"]["title"][0]["text"]["content"], raw_data["ID"]) # プロパティ名を修正
        self.assertEqual(created_page["properties"]["画像URL1"]["url"], gdrive_url)
        self.assertIsNone(created_page["properties"]["画像URL2"]["url"])
        self.logger.info(f"作成されたページID: {created_page.get('id')}")

    def test_02_add_post_multiple_images(self):
        self.logger.info("\n--- test_add_post_multiple_images 開始 ---")
        # placeholder.com は名前解決エラーが出ていたため、別の安定した画像URLに変更 (例: placekitten)
        image_urls = [
            "http://placekitten.com/200/300",
            "http://placekitten.com/200/301",
            "http://placekitten.com/200/302",
            "http://placekitten.com/200/303"
        ]
        raw_data = self._create_base_post_data("test_multi_001", "複数(4枚)画像のテスト投稿。", image_urls)
        prepared_notion_props = self._prepare_notion_post_data(raw_data)

        created_page = self.writer.add_post(
            tweet_id=raw_data["ID"],
            text=raw_data["本文"],
            user=raw_data["投稿者"],
            tweet_url=f"https://twitter.com/{raw_data['投稿者']}/status/{raw_data['ID']}",
            media_urls=raw_data["画像/動画URL"],
            created_at_str=raw_data["投稿日時"],
            ocr_text=prepared_notion_props["OCRテキスト"]
        )
        self.assertIsNotNone(created_page, "ページの作成に失敗しました。")
        self.assertEqual(created_page["properties"]["ツイートID"]["title"][0]["text"]["content"], raw_data["ID"]) # プロパティ名を修正
        for i, url in enumerate(image_urls):
            self.assertEqual(created_page["properties"][f"画像URL{i+1}"]["url"], url, f"画像URL{i+1}が一致しません")
        self.logger.info(f"作成されたページID: {created_page.get('id')}")

    def test_03_add_post_no_image(self):
        self.logger.info("\n--- test_add_post_no_image 開始 ---")
        raw_data = self._create_base_post_data("test_noimg_001", "画像なしのテスト投稿。")
        prepared_notion_props = self._prepare_notion_post_data(raw_data)

        created_page = self.writer.add_post(
            tweet_id=raw_data["ID"],
            text=raw_data["本文"],
            user=raw_data["投稿者"],
            tweet_url=f"https://twitter.com/{raw_data['投稿者']}/status/{raw_data['ID']}",
            media_urls=raw_data["画像/動画URL"], # 空のリストになる
            created_at_str=raw_data["投稿日時"],
            ocr_text=prepared_notion_props["OCRテキスト"] # None になる
        )
        self.assertIsNotNone(created_page, "ページの作成に失敗しました。")
        self.assertEqual(created_page["properties"]["ツイートID"]["title"][0]["text"]["content"], raw_data["ID"]) # プロパティ名を修正
        self.assertIsNone(created_page["properties"]["画像URL1"]["url"])
        # OCRテキストがNoneの場合、Notionではrich_textプロパティ自体が存在しないか、空のリストになる
        ocr_prop_data = created_page["properties"]["OCRテキスト"].get("rich_text", [])
        self.assertTrue(not ocr_prop_data, "OCRテキストがNoneであるべきが、何らかの値が設定されています。")
        self.logger.info(f"作成されたページID: {created_page.get('id')}")

    def test_04_add_post_with_ocr(self):
        self.logger.info("\n--- test_add_post_with_ocr 開始 ---")
        # OCRテスト用の画像URLを安定していそうなものに変更
        ocr_image_url = "https://www.gstatic.com/webp/gallery/1.jpg" 
        expected_ocr_text_partial = "Google" # 画像の内容に合わせて期待値を変更 (この画像には "Google" の文字が含まれているはず)
        raw_data = self._create_base_post_data("test_ocr_002", "OCR機能のテスト投稿。", [ocr_image_url])
        prepared_notion_props = self._prepare_notion_post_data(raw_data)

        created_page = self.writer.add_post(
            tweet_id=raw_data["ID"],
            text=raw_data["本文"],
            user=raw_data["投稿者"],
            tweet_url=f"https://twitter.com/{raw_data['投稿者']}/status/{raw_data['ID']}",
            media_urls=raw_data["画像/動画URL"],
            created_at_str=raw_data["投稿日時"],
            ocr_text=prepared_notion_props["OCRテキスト"]
        )
        self.assertIsNotNone(created_page, "ページの作成に失敗しました。")
        self.assertEqual(created_page["properties"]["ツイートID"]["title"][0]["text"]["content"], raw_data["ID"]) # プロパティ名を修正
        self.assertEqual(created_page["properties"]["画像URL1"]["url"], ocr_image_url)
        
        ocr_prop_data = created_page["properties"]["OCRテキスト"].get("rich_text", [])
        inserted_ocr_text = ""
        if ocr_prop_data and isinstance(ocr_prop_data, list) and len(ocr_prop_data) > 0:
            inserted_ocr_text = ocr_prop_data[0].get("text", {}).get("content", "")
        
        self.assertIn(expected_ocr_text_partial.lower(), inserted_ocr_text.lower(), f"期待したOCRテキスト '{expected_ocr_text_partial}' が含まれていません。実際のテキスト: '{inserted_ocr_text}'")
        self.logger.info(f"作成されたページID: {created_page.get('id')}, OCRテキスト: {inserted_ocr_text[:100]}...")

if __name__ == '__main__':
    unittest.main() 