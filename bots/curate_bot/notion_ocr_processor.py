import os
import sys
import time
from datetime import datetime
# import yaml # config_loader を使うので直接 yaml は不要になる場合がある
from notion_client import Client, APIErrorCode, APIResponseError
import argparse # コマンドライン引数処理のため
import requests # requests をインポート

# プロジェクトルートのパスを取得し、sys.pathに追加
# これにより、プロジェクト内の他モジュールを正しくインポートできる
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from utils.logger import setup_logger
from bots.curate_bot.ocr_utils import ocr_with_gemini_vision, correct_ocr_text_with_gemini # 修正
# config_loader をインポート
from config.config_loader import get_full_config, get_bot_config

class NotionOCRProcessor:
    def __init__(self, logger, is_test_mode=False):
        self.logger = logger
        self.is_test_mode = is_test_mode 
        
        _full_config = get_full_config()
        if not _full_config:
            self.logger.error("❌ 設定ファイル(config.yml)の読み込みに失敗しました。処理を続行できません。")
            raise ValueError("設定ファイルの読み込みに失敗")

        notion_specific_config = _full_config.get("notion", {})
        self.notion_token = notion_specific_config.get("token")
        self.database_id = notion_specific_config.get("databases", {}).get("curation_main")

        gemini_config = _full_config.get("gemini_api", {})
        self.gemini_api_key = gemini_config.get("api_key")
        if not self.gemini_api_key:
            self.logger.warning("⚠️ Gemini APIキーがconfig.ymlの'gemini_api'セクションに設定されていません。OCR処理に失敗する可能性があります。")
        else:
            self.logger.info("✅ Gemini APIキーの読み込みに成功しました。")

        if not self.notion_token or not self.database_id:
            self.logger.error("❌ NotionのトークンまたはデータベースIDがconfig.ymlの'notion'セクションに設定されていません。")
            raise ValueError("Notionの接続情報が不足しています。")

        try:
            self.notion_client = Client(auth=self.notion_token)
            self.logger.info(f"✅ Notionクライアントの初期化に成功しました。DB ID: {self.database_id}")
            # is_test_modeに関わらずスキーマチェックを実行するように変更 (force_check=True を渡す)
            # スキーマチェックで問題があっても、ここではエラーとせず警告に留める（ログ確認が主目的のため）
            if not self._check_database_schema(force_check=True): 
                self.logger.warning("⚠️ Notionデータベースのスキーマチェックで問題が検出されましたが、ログ確認のため処理を続行します。")
        except Exception as e:
            self.logger.error(f"❌ Notionクライアントの初期化またはスキーマチェック中にエラー: {e}", exc_info=True)
            raise

    def _check_database_schema(self, force_check=False):
        """Notionデータベースのスキーマが必要なプロパティと型を持っているか確認する"""
        # is_test_mode が True で force_check が False の場合のみスキップするロジックに変更
        if self.is_test_mode and not force_check:
            self.logger.info("✅ テストモード (force_check=False): データベーススキーマの厳密なチェックをスキップします。")
            return True # スキップする場合は常に True を返す

        self.logger.info(f"スキーマ確認開始: データベース {self.database_id} (強制チェックモード: {force_check})")
        try:
            db_info = self.notion_client.databases.retrieve(database_id=self.database_id)
            current_properties = db_info.get("properties", {})
            self.logger.info("--- 取得したデータベースプロパティ一覧 ---")
            for prop_name, prop_data in current_properties.items():
                self.logger.info(f"  ---> プロパティ名: '{prop_name}', 型: '{prop_data.get('type')}', ID: '{prop_data.get('id')}'")
            self.logger.info("--- プロパティ一覧のログ出力完了 ---")

        except APIResponseError as e:
            self.logger.error(f"❌ データベース情報の取得中にAPIエラー: {e.code} - {e.body}", exc_info=True)
            return False # エラー時は False を返す
        except Exception as e:
            self.logger.error(f"❌ データベース情報の取得中に予期せぬエラー: {e}", exc_info=True)
            return False # エラー時は False を返す

        # 以下は元の期待されるプロパティとの比較ロジック（今回はログ確認が主なので、ここの成否は警告に留める）
        expected_properties = {
            "ツイートID": "title", # 「名前」から変更
            "OCRテキスト": "rich_text",
            "画像URL1": "url",
            # "画像URL2": "url", # 必要に応じてコメント解除
            # "画像URL3": "url",
            # "画像URL4": "url",
            "ステータス": "select",
        }
        expected_status_options = ["新規", "処理済", "エラー"]

        schema_ok = True
        for prop_name_expected, expected_type in expected_properties.items():
            if prop_name_expected not in current_properties:
                self.logger.warning(f"  ⚠️ (スキーマ比較) 期待されるプロパティ '{prop_name_expected}' がDBに存在しません。")
                schema_ok = False # 必須ではないので警告レベル
                continue
            
            actual_type = current_properties[prop_name_expected].get("type")
            if actual_type != expected_type:
                self.logger.warning(f"  ⚠️ (スキーマ比較) プロパティ '{prop_name_expected}' の型が不正です。期待: '{expected_type}', 実際: '{actual_type}'")
                schema_ok = False
            
            if prop_name_expected == "ステータス" and actual_type == "select":
                options = current_properties[prop_name_expected].get("select", {}).get("options", [])
                option_names = [opt.get("name") for opt in options]
                missing_options = [opt_name for opt_name in expected_status_options if opt_name not in option_names]
                if missing_options:
                    self.logger.warning(f"  ⚠️ (スキーマ比較) プロパティ 'ステータス' に不足しているオプションがあります: {missing_options}")

        if schema_ok:
            self.logger.info("✅ (スキーマ比較) 期待されるプロパティ構成との基本的な比較が完了しました。")
        else:
            self.logger.warning("❌ (スキーマ比較) 期待されるプロパティ構成との間に差異が見つかりました。上記のログを確認してください。")
        
        return True # ログ確認が主目的なので、比較結果に関わらずTrueを返し、処理を止めない

    # _load_config メソッドは config_loader を使うため不要になる
    # def _load_config(self, config_path):
    #     try:
    #         abs_config_path = os.path.abspath(config_path)
    #         self.logger.info(f"設定ファイル {abs_config_path} を読み込んでいます...")
    #         if not os.path.exists(abs_config_path):
    #             self.logger.error(f"❌ 設定ファイルが見つかりません: {abs_config_path}")
    #             return None
    #         with open(abs_config_path, 'r', encoding='utf-8') as f:
    #             config_data = yaml.safe_load(f) # ここでyamlを使っていた
    #         self.logger.info("✅ 設定ファイルの読み込みが完了しました。")
    #         return config_data
    #     except Exception as e:
    #         self.logger.error(f"❌ 設定ファイル {config_path} の読み込み中にエラー: {e}", exc_info=True)
    #         return None

    def get_pages_to_ocr(self, limit=10):
        """
        Notionデータベースから「OCRテキスト」が空で、かつ「ステータス」が「新規」または未設定のページを取得する。
        """
        if not self.notion_client:
            self.logger.error("Notionクライアントが初期化されていません。")
            return []
        
        self.logger.info("OCR処理対象のNotionページを取得しています...")
        try:
            # OCRテキストが空、かつ画像URLが1つ以上存在するページをフィルタリング
            # ステータスが「新規」または存在しないものを対象とする
            filter_conditions = {
                "and": [
                    {
                        "property": "OCRテキスト",
                        "rich_text": {
                            "is_empty": True
                        }
                    },
                    { # 画像URLが1つ以上ある (プロパティ名を「画像URL1」に戻す)
                        "or": [
                            {"property": "画像URL1", "url": {"is_not_empty": True}}, # 「画像/動画URL」から「画像URL1」に戻す
                            # 他の画像URLも必要に応じて追加・修正
                            # {"property": "画像URL2", "url": {"is_not_empty": True}},
                            # {"property": "画像URL3", "url": {"is_not_empty": True}},
                            # {"property": "画像URL4", "url": {"is_not_empty": True}},
                        ]
                    }
                ]
            }
            
            response = self.notion_client.databases.query(
                database_id=self.database_id,
                filter=filter_conditions,
                page_size=limit # 一度に処理する件数を制限
            )
            pages = response.get("results", [])
            self.logger.info(f"OCR対象として {len(pages)} 件のページを取得しました。")
            return pages
        except APIResponseError as e:
            self.logger.error(f"❌ Notionからのページ取得中にAPIエラー: {e.code} - {e.body}", exc_info=True)
        except Exception as e:
            self.logger.error(f"❌ Notionからのページ取得中に予期せぬエラー: {e}", exc_info=True)
        return []

    def update_page_ocr_text(self, page_id: str, ocr_text: str, status: str = "処理済"):
        """指定されたページのOCRテキストとステータスを更新する"""
        self.logger.info(f"ページ {page_id} のOCRテキストとステータスを更新します。")
        
        properties_to_update = {}
        page_info = None # ページ情報を保持する変数
        try:
            # まずページの現在のプロパティ情報を取得
            page_info = self.notion_client.pages.retrieve(page_id=page_id)
        except APIResponseError as e:
            self.logger.error(f"❌ ページ {page_id} の情報取得中にAPIエラー: {e.message}", exc_info=True)
            return False # 情報取得に失敗したら更新できない

        available_properties = page_info.get("properties", {}).keys()

        if "OCRテキスト" in available_properties:
            properties_to_update["OCRテキスト"] = {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": ocr_text if ocr_text else ""
                        }
                    }
                ]
            }
        else:
            self.logger.warning(f"ページ {page_id} に 'OCRテキスト' プロパティが存在しません。更新をスキップします。")

        if "ステータス" in available_properties:
            # ステータスプロパティの型が select であることを前提とする
            properties_to_update["ステータス"] = {"select": {"name": status}}
        else:
            self.logger.warning(f"ページ {page_id} に 'ステータス' プロパティが存在しません。更新をスキップします。")

        if not properties_to_update:
            self.logger.info(f"ページ {page_id} で更新対象のプロパティ（OCRテキスト、ステータス）が存在しないため、更新処理をスキップします。")
            return True # 更新対象がない場合も「成功」として扱う（処理は継続できるため）

        try:
            self.notion_client.pages.update(
                page_id=page_id,
                properties=properties_to_update
            )
            self.logger.info(f"✅ ページ {page_id} のOCRテキストとステータスを更新しました。")
            return True
        except APIResponseError as e:
            self.logger.error(f"❌ ページ {page_id} の更新中にAPIエラー: {e.message}", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"❌ ページ {page_id} の更新中に予期せぬエラー: {e}", exc_info=True)
            return False

    def process_single_page(self, page_data):
        """
        単一のNotionページデータに対してOCR処理を実行し、結果を更新する。
        """
        page_id = page_data.get("id")
        properties = page_data.get("properties", {})
        
        image_urls = []
        # プロパティ名を「画像URL1」に戻して画像URLを取得
        url_prop = properties.get("画像URL1", {}).get("url") # 「画像/動画URL」から「画像URL1」に戻す
        if url_prop:
            image_urls.append(url_prop)
        
        # 他の画像URLも必要に応じて取得 (例: 画像URL2, 画像URL3, ...)
        # for i in range(2, 5):
        #     url_prop_numbered = properties.get(f"画像URL{i}", {}).get("url")
        #     if url_prop_numbered:
        #         image_urls.append(url_prop_numbered)
        
        if not image_urls:
            self.logger.info(f"ページ {page_id} には処理対象の画像URLが見つかりませんでした。スキップします。")
            return False

        self.logger.info(f"ページ {page_id} のOCR処理を開始します。画像URL(s): {image_urls}")
        
        processed_image_results = [] # (is_error: bool, text_or_error_code: str, image_url: str)

        for img_url in image_urls:
            self.logger.info(f"  画像URL: {img_url} のOCR処理中...")
            extracted_result = ocr_with_gemini_vision(self.gemini_api_key, img_url, self.logger)
            
            error_keywords = ["DOWNLOAD_FAILED", "OCR_PROCESSING_ERROR"]
            is_error_result = any(keyword in extracted_result for keyword in error_keywords if extracted_result)

            if is_error_result:
                self.logger.warning(f"  画像URL: {img_url} のOCR処理でエラーコード '{extracted_result}' を検出しました。")
                processed_image_results.append((True, extracted_result, img_url))
            elif extracted_result == "": # OCR結果が空だがエラーではない場合
                self.logger.info(f"  画像URL: {img_url} からテキストは抽出されませんでした（エラーではありません）。")
                processed_image_results.append((False, "", img_url)) # 正常だがテキストなし
            else: # 正常にテキスト抽出
                processed_image_results.append((False, extracted_result, img_url))

        # 抽出されたテキストとエラー情報を分ける
        valid_ocr_texts = [res[1] for res in processed_image_results if not res[0] and res[1]]
        error_messages_for_notion = []
        for is_err, code, url in processed_image_results:
            if is_err:
                error_description = f"画像処理エラー ({code}) : {url}"
                if code == "DOWNLOAD_FAILED_404":
                    error_description = f"画像ダウンロード失敗 (404 Not Found): {url}"
                elif "DOWNLOAD_FAILED_HTTP_" in code:
                    status_code = code.split("_")[-1]
                    error_description = f"画像ダウンロード失敗 (HTTPエラー {status_code}): {url}"
                elif code == "DOWNLOAD_FAILED_TIMEOUT":
                    error_description = f"画像ダウンロードタイムアウト: {url}"
                elif code == "DOWNLOAD_FAILED_CONNECTION":
                    error_description = f"画像ダウンロード接続エラー: {url}"
                elif code == "DOWNLOAD_FAILED_OTHER_REQUEST":
                    error_description = f"画像ダウンロードリクエストエラー: {url}"
                elif code == "OCR_PROCESSING_ERROR":
                    error_description = f"OCR内部処理エラー: {url}"
                error_messages_for_notion.append(error_description)

        combined_valid_ocr_text = "\n\n".join(valid_ocr_texts).strip() # 有効なOCRテキストのみ結合

        final_text_to_save = combined_valid_ocr_text
        current_status = "処理済"

        if not valid_ocr_texts: # 有効なOCRテキストが一つもない場合
            if error_messages_for_notion: # エラーメッセージはある場合
                self.logger.error(f"ページ {page_id} の全ての画像で有効なOCRテキストが得られず、エラーが発生しました。")
                # final_text_to_save = "【OCR処理結果】\nなし\n\n【エラー情報】\n" + "\n".join(error_messages_for_notion)
                final_text_to_save = "" # エラー時はOCRテキストを空にする
                current_status = "エラー"
            else: # エラーもなく、テキストも全くない場合（例：画像に文字が全くない、など）
                self.logger.info(f"ページ {page_id} からテキストは抽出されず、エラーもありませんでした。")
                final_text_to_save = "（画像からテキストは抽出されませんでした）"
                # current_status は「処理済」のまま
        else: # 有効なOCRテキストがある場合
            self.logger.info(f"ページ {page_id} の有効なOCRテキスト抽出完了。LLMによる補正を開始します...")
            # LLMには有効なOCRテキストのみを渡す
            corrected_text = correct_ocr_text_with_gemini(self.gemini_api_key, combined_valid_ocr_text, self.logger)
            
            if corrected_text and corrected_text.strip() != combined_valid_ocr_text.strip():
                final_text_to_save = "【OCR処理結果（LLM補正済）】\n" + corrected_text
                self.logger.info(f"ページ {page_id} のLLMによるテキスト補正が完了しました。")
            else:
                self.logger.warning(f"ページ {page_id} のLLMによるテキスト補正に失敗、または変化がありませんでした。補正前のOCRテキストを使用します。")
                final_text_to_save = "【OCR処理結果】\n" + combined_valid_ocr_text
            
            if error_messages_for_notion: # 有効なテキストもあり、エラーもある場合
                final_text_to_save += "\n\n【エラー情報】\n" + "\n".join(error_messages_for_notion)

        #最終出力テキストから余分な接頭辞を削除
        prefixes_to_remove = ["【OCR処理結果（LLM補正済）】\n", "【OCR処理結果】\n"]
        for prefix in prefixes_to_remove:
            if final_text_to_save.startswith(prefix):
                final_text_to_save = final_text_to_save.replace(prefix, "", 1)
                break

        return self.update_page_ocr_text(page_id, final_text_to_save.strip(), status=current_status)

    def _create_page(self, title: str, properties: dict):
        """Notionデータベースに新しいページを作成するユーティリティメソッド (requestsで直接API呼び出し)"""
        self.logger.info("🚧 _create_page を requests を使った直接API呼び出しモードで実行します。(複数プロパティ対応)")

        parent_db = {"database_id": self.database_id}
        
        props_for_payload = { 
            key: value for key, value in properties.items() 
            if key.lower() != "title" and key.lower() != "ツイートid" 
        }
        
        # 「画像URL1」ではなく、引数propertiesで渡されたキー名（ここでは「画像/動画URL」を期待）をそのまま使う。
        # ただし、propertiesのキーが「画像/動画URL」であることをrun_ocr_test_on_new_pageで保証する。

        props_for_payload["ツイートID"] = { 
            "title": [
                {
                    "text": {
                        "content": title 
                    }
                }
            ]
        }
        # `properties`引数から渡された他のプロパティ（例：「画像/動画URL」）は既にprops_for_payloadに含まれている想定。

        payload = {
            "parent": parent_db,
            "properties": props_for_payload
        }

        headers = {
            "Authorization": f"Bearer {self.notion_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

        api_url = "https://api.notion.com/v1/pages"

        self.logger.debug(f"直接API呼び出し URL: {api_url}")
        self.logger.debug(f"直接API呼び出し Headers: {headers}") 
        self.logger.debug(f"直接API呼び出し Payload: {payload}")

        try:
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()  # HTTPエラーがあれば例外を発生
            created_page = response.json()
            self.logger.info(f"✅ (直接API) テスト用ページ '{title}' (ID: {created_page.get('id')}) を作成しました。")
            return created_page
        except requests.exceptions.HTTPError as http_err:
            self.logger.error(f"❌ (直接API) HTTPエラー: {http_err}", exc_info=True)
            self.logger.error(f"    Response Body: {response.text}")
        except Exception as e:
            self.logger.error(f"❌ (直接API) 予期せぬエラー: {e}", exc_info=True)
        return None

    def _delete_page(self, page_id: str):
        """指定されたIDのページをアーカイブ（事実上の削除）するユーティリティメソッド"""
        if not self.notion_client:
            self.logger.error(f"Notionクライアントが初期化されていません。ページ {page_id} を削除できません。")
            return False
        try:
            self.notion_client.pages.update(page_id=page_id, archived=True)
            self.logger.info(f"✅ ページ {page_id} をアーカイブしました。")
            return True
        except APIResponseError as e:
            self.logger.error(f"❌ ページ {page_id} のアーカイブ中にAPIエラー: {e.code} - {e.body}", exc_info=True)
        except Exception as e:
            self.logger.error(f"❌ ページ {page_id} のアーカイブ中に予期せぬエラー: {e}", exc_info=True)
        return False

    def run_ocr_test_on_new_page(self, test_tweet_id: str, test_image_urls: list):
        """指定されたツイートIDと画像URLで新しいページを作成し、OCR処理を実行してページを削除するテストメソッド"""
        self.logger.info(f"--- OCR単体テスト開始: ツイートID '{test_tweet_id}' (requests版、プロパティ「画像URL1」使用) ---")
        
        page_properties = {}
        if test_image_urls:
            # プロパティ名を「画像URL1」に戻す
            page_properties["画像URL1"] = {"url": test_image_urls[0]} 
        else:
            self.logger.warning(f"テスト (ツイートID: '{test_tweet_id}') に画像URLが提供されませんでした。")
        
        created_page_data = self._create_page(title=test_tweet_id, properties=page_properties)

        if not created_page_data or not created_page_data.get("id"):
            self.logger.error(f"テストページ (ツイートID: '{test_tweet_id}') の作成に失敗したため、OCRテストを中止します。")
            return False

        page_id_for_test = created_page_data.get("id")
        test_result = False
        
        try:
            self.logger.info(f"作成したテストページ {page_id_for_test} (ツイートID: '{test_tweet_id}') に対してOCR処理を実行します。")
            test_result = self.process_single_page(created_page_data)
            if test_result:
                self.logger.info(f"テストページ {page_id_for_test} (ツイートID: '{test_tweet_id}') のOCR処理が成功しました。")
            else:
                self.logger.warning(f"テストページ {page_id_for_test} (ツイートID: '{test_tweet_id}') のOCR処理が失敗またはスキップされました。")
        
        except Exception as e:
            self.logger.error(f"テストページ {page_id_for_test} (ツイートID: '{test_tweet_id}') のOCR処理中にエラー: {e}", exc_info=True)
            test_result = False
        finally:
            self.logger.info(f"テストページ {page_id_for_test} (ツイートID: '{test_tweet_id}') を削除します。")
            self._delete_page(page_id_for_test)

        self.logger.info(f"--- OCR単体テスト終了: ツイートID '{test_tweet_id}'. 結果: {'成功' if test_result else '失敗'} ---")
        return test_result

    def run(self, limit_pages=10):
        """
        Notionからページを取得し、順次OCR処理を実行するメインロジック。
        """
        if not self.notion_client:
            self.logger.error("Notionクライアントが利用できません。処理を中止します。")
            return
        
        # if not gemini_client: # ocr_utils側のクライアントを再度確認
        #      self.logger.error("❌ Gemini APIクライアントが初期化されていません。OCR処理を実行できません。")
        #      return

        pages_to_process = self.get_pages_to_ocr(limit=limit_pages)
        if not pages_to_process:
            self.logger.info("現在OCR処理対象のページはありません。")
            return

        self.logger.info(f"--- {len(pages_to_process)}件のページのOCR処理を開始します ---")
        processed_count = 0
        error_count = 0

        for page in pages_to_process:
            try:
                success = self.process_single_page(page)
                if success:
                    processed_count += 1
                else:
                    error_count += 1 # process_single_page内でエラーロギングとステータス更新済み
            except Exception as e:
                error_count += 1
                page_id_for_log = page.get("id", "不明なページID")
                self.logger.error(f"❌ ページ {page_id_for_log} の処理中に予期せぬトップレベルエラー: {e}", exc_info=True)
                # ここでもステータスを「エラー」に更新することを検討
                self.update_page_ocr_text(page_id_for_log, "OCR処理中予期せぬエラー", status="エラー")
            
            time.sleep(5) # 各ページ処理後にウェイト

        self.logger.info(f"--- OCR処理完了 ---")
        self.logger.info(f"処理成功: {processed_count}件")
        self.logger.info(f"処理失敗/スキップ: {error_count}件")


if __name__ == "__main__":
    log_directory = os.path.join(project_root, "bots", "curate_bot", "logs")
    logger = setup_logger(log_dir_name=log_directory, logger_name="NotionOCRProcessor_main", level="DEBUG")

    parser = argparse.ArgumentParser(description="Notion OCR Processor")
    parser.add_argument("--test-ocr", action="store_true", 
                        help="指定されたサンプルURLで一時的なNotionページを作成しOCR処理をテストします。")
    parser.add_argument("--limit", type=int, default=5, help="通常のrunモードで処理する最大ページ数。")
    args = parser.parse_args()

    logger.info(f"🤖 Notion OCR Processor を起動します。設定は config/config.yml から読み込まれます。")

    try:
        processor = NotionOCRProcessor(logger=logger, is_test_mode=args.test_ocr)
        
        if args.test_ocr:
            logger.info("🧪 OCRテストモードで実行します...")
            sample_urls_for_test = [
                "https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png"
            ]
            sample_tweet_id = "test_tweet_id_12345" # テスト用のツイートID
            
            success_test = processor.run_ocr_test_on_new_page(
                test_tweet_id=sample_tweet_id,
                test_image_urls=sample_urls_for_test
            )
            
            if success_test:
                 logger.info("✅ OCRテストモードが正常に完了しました。DBへの書き込みも確認してください。")
            else:
                 logger.error("❌ OCRテストモードで問題が発生しました。詳細はログを確認してください。")

        else:
            logger.info(f"通常モードで実行します。最大処理ページ数: {args.limit}")
            processor.run(limit_pages=args.limit)

    except ValueError as ve:
        logger.error(f"初期化エラー: {ve}", exc_info=True) # exc_info追加
    except RuntimeError as re:
        logger.error(f"実行時エラー: {re}", exc_info=True) # exc_info追加
    except Exception as e:
        logger.error(f"予期せぬエラーにより処理を終了します: {e}", exc_info=True)
    finally:
        logger.info("👋 Notion OCR Processor を終了します。") 