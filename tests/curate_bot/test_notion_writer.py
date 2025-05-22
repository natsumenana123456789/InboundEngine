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
            raise unittest.SkipTest("設定ファイルが読み込めませんでした。テストをスキップします。")

        notion_config = cls.config.get('notion', {})
        cls.notion_token = notion_config.get("token")
        cls.database_id = notion_config.get('databases', {}).get('curation')

        if not cls.notion_token or not cls.database_id:
            raise unittest.SkipTest("NotionのトークンまたはデータベースIDが設定されていません。テストをスキップします。")

        # テスト用のロガーをセットアップ
        # tests/logs/test_notion_writer.log のようなパスに出力
        cls.logger = setup_logger(log_dir_name='tests/logs', log_file_name='test_notion_writer.log', logger_name='TestNotionWriter')
        
        # NotionWriterインスタンスを作成 (loggerを渡す)
        cls.writer = NotionWriter(cls.notion_token, cls.database_id, cls.logger)

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
        gdrive_url = "https://drive.google.com/file/d/1uv-Ejpg6mXeX0Zoi367-KWsfG83oDyyj/view?usp=sharing" # ユーザーが指定したURL
        raw_data = self._create_base_post_data("test_single_001", "単一画像(GDrive)のテスト投稿。", [gdrive_url])
        notion_data = self._prepare_notion_post_data(raw_data)
        
        created_page = self.writer.add_post(notion_data)
        self.assertIsNotNone(created_page, "ページの作成に失敗しました。")
        self.assertEqual(created_page["properties"]["ID"]["title"][0]["text"]["content"], raw_data["ID"])
        self.assertEqual(created_page["properties"]["画像URL1"]["url"], gdrive_url)
        self.assertIsNone(created_page["properties"]["画像URL2"]["url"])
        self.logger.info(f"作成されたページID: {created_page.get('id')}")

    def test_02_add_post_multiple_images(self):
        self.logger.info("\n--- test_add_post_multiple_images 開始 ---")
        placeholder_base = "https://via.placeholder.com/150"
        image_urls = [
            f"{placeholder_base}/FF0000/FFFFFF?Text=Img1_test",
            f"{placeholder_base}/00FF00/000000?Text=Img2_test",
            f"{placeholder_base}/0000FF/FFFFFF?Text=Img3_test",
            f"{placeholder_base}/FFFF00/000000?Text=Img4_test"
        ]
        raw_data = self._create_base_post_data("test_multi_001", "複数(4枚)画像のテスト投稿。", image_urls)
        notion_data = self._prepare_notion_post_data(raw_data)

        created_page = self.writer.add_post(notion_data)
        self.assertIsNotNone(created_page, "ページの作成に失敗しました。")
        self.assertEqual(created_page["properties"]["ID"]["title"][0]["text"]["content"], raw_data["ID"])
        for i, url in enumerate(image_urls):
            self.assertEqual(created_page["properties"][f"画像URL{i+1}"]["url"], url, f"画像URL{i+1}が一致しません")
        self.logger.info(f"作成されたページID: {created_page.get('id')}")

    def test_03_add_post_no_image(self):
        self.logger.info("\n--- test_add_post_no_image 開始 ---")
        raw_data = self._create_base_post_data("test_noimg_001", "画像なしのテスト投稿。")
        notion_data = self._prepare_notion_post_data(raw_data)

        created_page = self.writer.add_post(notion_data)
        self.assertIsNotNone(created_page, "ページの作成に失敗しました。")
        self.assertEqual(created_page["properties"]["ID"]["title"][0]["text"]["content"], raw_data["ID"])
        self.assertIsNone(created_page["properties"]["画像URL1"]["url"])
        self.assertIsNone(created_page["properties"]["OCRテキスト"]["rich_text"] or None) # 空のrich_textは[]
        self.logger.info(f"作成されたページID: {created_page.get('id')}")

    def test_04_add_post_with_ocr(self):
        self.logger.info("\n--- test_add_post_with_ocr 開始 ---")
        ocr_image_url = "https://www.bannerbatterien.com/upload/filecache/Banner-Batterien-Logo-jpg_0x0_100_c53520092348a5ce143f9a11da8e1376.jpg"
        expected_ocr_text_partial = "Banner"
        raw_data = self._create_base_post_data("test_ocr_002", "OCR機能のテスト投稿。画像に 'Banner' という文字が含まれるはず。", [ocr_image_url])
        notion_data = self._prepare_notion_post_data(raw_data)

        created_page = self.writer.add_post(notion_data)
        self.assertIsNotNone(created_page, "ページの作成に失敗しました。")
        self.assertEqual(created_page["properties"]["ID"]["title"][0]["text"]["content"], raw_data["ID"])
        self.assertEqual(created_page["properties"]["画像URL1"]["url"], ocr_image_url)
        
        ocr_prop_data = created_page["properties"]["OCRテキスト"].get("rich_text", [])
        inserted_ocr_text = ""
        if ocr_prop_data and isinstance(ocr_prop_data, list) and len(ocr_prop_data) > 0:
            inserted_ocr_text = ocr_prop_data[0].get("text", {}).get("content", "")
        
        self.assertIn(expected_ocr_text_partial.lower(), inserted_ocr_text.lower(), "期待したOCRテキストが含まれていません。")
        self.logger.info(f"作成されたページID: {created_page.get('id')}, OCRテキスト: {inserted_ocr_text[:100]}...")

if __name__ == '__main__':
    unittest.main() 