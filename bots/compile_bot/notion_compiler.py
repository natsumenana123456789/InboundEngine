import os
import sys
import re
from notion_client import Client, APIErrorCode, APIResponseError
import datetime

# プロジェクトルートをsys.pathに追加 (configモジュール等をインポートするため)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils.logger import setup_logger # 共通ロガー
from config import config_loader # configローダーも必要に応じて使う

class NotionCompiler: # クラス名を NotionCompiler に変更
    def __init__(self, bot_config, parent_logger=None):
        self.bot_config = bot_config # compile_bot の設定全体
        # TODO: ログディレクトリを bots/compile_bot/logs に変更
        self.logger = parent_logger if parent_logger else setup_logger(log_dir_name='bots/compile_bot/logs', logger_name='NotionCompiler_default')

        # Notionに関する設定は bot_config 直下の notion セクションから取得することを想定
        # もしくは、このクラスが呼び出される際に、必要なDBIDなどが直接渡される形でも良い
        notion_specific_config = self.bot_config.get("notion") # まず bot_config から "notion" を試みる
        if not notion_specific_config: # もし bot_config に "notion" がなければ、グローバル設定を試みる
            self.logger.info(f"渡されたbot_configに 'notion' セクションがありません。グローバルの 'notion' 設定を試みます。")
            full_config = config_loader.get_full_config() # config_loader を使って全体のコンフィグを取得
            notion_specific_config = full_config.get("notion", {})

        self.notion_token = notion_specific_config.get("token")
        
        # 使用するDB IDは、呼び出し元やbot_config内のキーで指定される想定
        # 例えば self.bot_config.get("compile_target_db_id") や、
        # notion_specific_config.get("databases", {}).get("compile_target_db") など
        # ここでは、汎用的に database_id をコンストラクタで受け取るか、メソッド呼び出し時に指定する方が柔軟かもしれない
        # 今回は、bot_configから curation_main を参照する既存のロジックを一旦維持し、後で調整
        self.database_id = notion_specific_config.get("databases", {}).get("curation_main") 
        # ↑ TODO: "curation_main" という名前が適切か、あるいは呼び出し元から指定されるべきか検討

        self.client = None
        if self.notion_token and self.database_id:
            try:
                self.client = Client(auth=self.notion_token)
                self.logger.info(f"✅ Notionクライアントの初期化に成功しました。DB ID: {self.database_id}")
            except Exception as e:
                self.logger.error(f"❌ Notionクライアントの初期化中にエラー: {e}", exc_info=True)
                self.client = None
        else:
            self.logger.warning("⚠️ NotionのトークンまたはデータベースIDが設定されていません。Notion機能は無効になります。")

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
                {"name": "コンパイル済", "color": "purple"}, # 「処理済」から変更
                {"name": "投稿済", "color": "green"}, # auto_post_botが使う想定
                {"name": "エラー", "color": "red"}
            ]}},
            "最終更新日時": {"last_edited_time": {}}
        }

    def is_client_initialized(self):
        return self.client is not None

    def ensure_database_schema(self, target_database_id=None):
        db_id_to_check = target_database_id if target_database_id else self.database_id
        if not db_id_to_check:
            self.logger.error("確認対象のNotionデータベースIDが指定されていません。")
            return
        if not self.is_client_initialized():
            self.logger.error("Notionクライアントが初期化されていないため、スキーマを確認できません。")
            return
        
        self.logger.info(f"データベース {db_id_to_check} のスキーマを確認・更新します...")
        try:
            db_info = self.client.databases.retrieve(database_id=db_id_to_check)
            current_properties_on_notion = db_info['properties']
            properties_to_update = {}
            needs_update = False

            current_title_prop_name = None
            for name, details in current_properties_on_notion.items():
                if details['type'] == 'title':
                    current_title_prop_name = name
                    break
            
            expected_title_name = "ツイートID"
            if current_title_prop_name and current_title_prop_name != expected_title_name:
                self.logger.info(f"  Titleプロパティ '{current_title_prop_name}' を '{expected_title_name}' にリネームします。")
                properties_to_update[current_title_prop_name] = {"name": expected_title_name}
                needs_update = True
                current_properties_on_notion[expected_title_name] = current_properties_on_notion.pop(current_title_prop_name)
            elif not current_title_prop_name:
                self.logger.warning(f"  データベースにTitleプロパティが見つかりません。'{expected_title_name}' をTitleとして新規作成します。")
                properties_to_update[expected_title_name] = self.expected_properties[expected_title_name]
                needs_update = True

            for name, expected_details in self.expected_properties.items():
                expected_type_key = list(expected_details.keys())[0]
                if name == expected_title_name and expected_type_key == "title":
                    continue # Titleは上で処理済み

                if name not in current_properties_on_notion:
                    self.logger.info(f"  プロパティ '{name}' (型: {expected_type_key}) を新規作成します。")
                    properties_to_update[name] = expected_details
                    needs_update = True
                elif current_properties_on_notion[name]['type'] != expected_type_key:
                    self.logger.info(f"  プロパティ '{name}' の型が異なります (現在: {current_properties_on_notion[name]['type']}, 期待: {expected_type_key})。型を更新します。")
                    properties_to_update[name] = expected_details
                    needs_update = True
                elif name == "ステータス" and expected_type_key == "select":
                    current_options = {opt['name'] for opt in current_properties_on_notion[name]['select']['options']}
                    expected_options_details = expected_details['select']['options']
                    expected_options_names = {opt['name'] for opt in expected_options_details}
                    if not expected_options_names.issubset(current_options):
                        self.logger.info(f"  プロパティ '{name}' の選択肢を更新します。")
                        properties_to_update[name] = {"select": {"options": expected_options_details}}
                        needs_update = True
            
            if needs_update:
                self.logger.info(f"スキーマの更新を実行します... 更新内容: {properties_to_update}")
                self.client.databases.update(database_id=db_id_to_check, properties=properties_to_update)
                self.logger.info("✅ データベーススキーマの更新が完了しました。")
            else:
                self.logger.info("✅ データベーススキーマは最新です。")

        except APIResponseError as e:
            if e.code == APIErrorCode.ObjectNotFound:
                self.logger.error(f"❌ 指定されたデータベースIDが見つかりません: {db_id_to_check}")
            else:
                self.logger.error(f"❌ データベーススキーマ確認・更新APIエラー: {e}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"❌ データベーススキーマ確認・更新中予期せぬエラー: {e}", exc_info=True)
            raise

    def load_processed_item_ids(self, id_property_name="ツイートID", target_database_id=None):
        db_id_to_query = target_database_id if target_database_id else self.database_id
        if not db_id_to_query:
            self.logger.error("対象のNotionデータベースIDが指定されていません。")
            return set()
        if not self.is_client_initialized():
            self.logger.warning("Notionクライアント未初期化のため、処理済みIDをロードできません。")
            return set()

        processed_ids = set()
        try:
            self.logger.info(f"データベース {db_id_to_query} から処理済みアイテムID (プロパティ名: {id_property_name}) をロードしています...")
            has_more = True
            start_cursor = None
            while has_more:
                response = self.client.databases.query(
                    database_id=db_id_to_query,
                    filter={"property": id_property_name, "title": {"is_not_empty": True}},
                    page_size=100,
                    start_cursor=start_cursor
                )
                for page in response.get("results", []):
                    title_property = page.get("properties", {}).get(id_property_name, {}).get("title", [])
                    if title_property and len(title_property) > 0:
                        item_id = title_property[0].get("plain_text")
                        if item_id:
                            processed_ids.add(item_id)
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
            self.logger.info(f"ロード完了: {len(processed_ids)} 件の処理済みID ('{id_property_name}') が見つかりました。")
        except Exception as e:
            self.logger.error(f"❌ Notionからの処理済みIDロード中にエラー: {e}", exc_info=True)
        return processed_ids

    def add_compiled_item(self, item_data: dict, target_database_id=None):
        db_id_to_add_to = target_database_id if target_database_id else self.database_id
        if not db_id_to_add_to:
            self.logger.error("追加対象のNotionデータベースIDが指定されていません。")
            return None
        if not self.is_client_initialized():
            self.logger.error("Notionクライアントが初期化されていないため、アイテムを追加できません。")
            return None

        # item_data は、expected_propertiesのキーに合わせたデータを持つ辞書と想定
        # 例: {"ツイートID": "123", "本文": "...", ...}
        page_properties = {}
        for prop_name, prop_details_config in self.expected_properties.items():
            prop_type = list(prop_details_config.keys())[0] # 'title', 'rich_text', 'url', 'date', 'select' など
            value = item_data.get(prop_name)

            if value is None: continue # 値がなければそのプロパティは設定しない

            if prop_type == "title":
                page_properties[prop_name] = {"title": [{"text": {"content": str(value)}}]}
            elif prop_type == "rich_text":
                # Notionのrich_textは2000字制限があるので注意
                page_properties[prop_name] = {"rich_text": [{"text": {"content": str(value)[:2000]}}]}
            elif prop_type == "url":
                page_properties[prop_name] = {"url": str(value) if str(value).startswith(("http://", "https://")) else None}
            elif prop_type == "date" and value: # 日付型の場合、ISOフォーマット文字列を期待
                try:
                    # 入力はISO文字列かdatetimeオブジェクト
                    iso_date_str = value if isinstance(value, str) else datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).isoformat()
                    page_properties[prop_name] = {"date": {"start": iso_date_str}}
                except (ValueError, AttributeError) as e_date:
                    self.logger.warning(f"プロパティ '{prop_name}' の日付形式 '{value}' が不正です: {e_date}。設定されません。")
            elif prop_type == "select" and isinstance(value, str): # セレクト型の場合、選択肢の名前(文字列)を期待
                page_properties[prop_name] = {"select": {"name": value}}
            # 他のプロパティタイプ (number, checkbox, multi_selectなど) も必要に応じて追加
            
            # media_urls のようなリスト形式のURLは個別処理が必要
            # ここでは expected_properties にある 画像URL1～4 を直接設定するロジックを汎用化
            elif prop_name.startswith("画像URL") and prop_type == "url":
                 # item_data["media_urls"] のようなリストから対応するURLを取得する処理が必要だったが、
                 # ここでは item_data に直接 "画像URL1": "http://..." のように入っていることを期待する
                 if str(value).startswith(("http://", "https://")):
                     page_properties[prop_name] = {"url": str(value)}

        if not page_properties.get("ツイートID") and not page_properties.get(item_data.get("_title_prop_name", "ツイートID")):
             self.logger.error("❌ 追加するアイテムにID (titleプロパティ) がありません。スキップします。")
             return None

        try:
            self.logger.info(f"Notionデータベース {db_id_to_add_to} にアイテムを追加中: {page_properties.get('ツイートID', {}).get('title', [{}])[0].get('text', {}).get('content', 'ID不明')[:30]}...")
            created_page = self.client.pages.create(
                parent={"database_id": db_id_to_add_to},
                properties=page_properties
            )
            self.logger.info(f"✅ Notionにアイテムが正常に追加されました。Page ID: {created_page['id']}")
            return created_page
        except APIResponseError as e:
            self.logger.error(f"❌ Notionへのアイテム追加中にAPIエラーが発生しました: {e}", exc_info=True)
            if "conflict_error" in str(e).lower() or e.code == APIErrorCode.ConflictError: # 既存IDとのコンフリクトなど
                 self.logger.warning(f"  アイテムIDの重複やその他のコンフリクトの可能性があります。")
        except Exception as e:
            self.logger.error(f"❌ Notionへのアイテム追加中に予期せぬエラーが発生しました: {e}", exc_info=True)
        return None

    def update_item_status(self, page_id: str, status: str, target_database_id=None):
        # target_database_id は現行のNotion Clientではpages.updateには不要だが、ログや将来のために残す
        if not self.is_client_initialized():
            self.logger.error("Notionクライアントが初期化されていないため、ステータスを更新できません。")
            return False
        if not page_id or not status:
            self.logger.error("ページIDまたはステータスが指定されていません。")
            return False
        
        # ステータスがexpected_propertiesで定義された選択肢にあるか確認（任意）
        valid_statuses = {opt['name'] for opt in self.expected_properties.get("ステータス", {}).get("select", {}).get("options", [])}
        if status not in valid_statuses:
            self.logger.warning(f"指定されたステータス '{status}' は定義済みの選択肢にありません。({valid_statuses})。そのまま更新を試みます。")

        try:
            self.logger.info(f"Notionページ {page_id} のステータスを '{status}' に更新します。")
            self.client.pages.update(
                page_id=page_id,
                properties={
                    "ステータス": {"select": {"name": status}}
                }
            )
            self.logger.info(f"✅ ページ {page_id} のステータス更新成功。")
            return True
        except APIResponseError as e:
            self.logger.error(f"❌ Notionページのステータス更新中にAPIエラー: {e}", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"❌ Notionページのステータス更新中に予期せぬエラー: {e}", exc_info=True)
            return False

# --- mainブロックのテストコード (リファクタリングに合わせて修正) ---
if __name__ == "__main__":
    print("--- NotionCompiler クラスのテスト ---")
    
    # このテストを実行する前に、config/config.yml にNotionの設定がされていることを確認してください。
    # (notion.token と notion.databases.curation_main またはテスト用DB ID)
    
    # ボット設定のダミー (実際はconfig_loader経由で取得)
    # get_bot_config("compile_bot") のようなものを想定
    # compile_bot の設定に notion セクションがあり、その中に token と databases.curation_main がある想定
    # さらに、その curation_main がテスト対象のDB IDであるとする
    try:
        test_bot_config = config_loader.get_bot_config("compile_bot") # compile_botという設定がある前提
        if not test_bot_config:
             # フォールバックとして全体設定から直接notionセクションを見る (get_bot_config が compile_bot を返さない場合など)
            full_cfg = config_loader.get_full_config()
            if full_cfg.get("notion"): # notionセクションがあればそれをcompile_botの設定として扱う
                test_bot_config = {"notion": full_cfg.get("notion"), "bot_name":"compile_bot_test_direct_notion_config"}
            else:
                raise ValueError("compile_bot または notion の設定がconfig.ymlに見つかりません。")
        
        # もし get_bot_config が "notion" キーをトップレベルに持たない場合 (例えば "curate_bot" の設定を流用している場合など)
        # 以下のようにして notion セクションを test_bot_config に設定する必要があるかもしれない
        # if "notion" not in test_bot_config:
        #     full_config_for_notion = config_loader.get_full_config()
        #     if full_config_for_notion.get("notion"):
        #         test_bot_config["notion"] = full_config_for_notion.get("notion")
        #     else:
        #         raise ValueError("テスト用のNotion設定(token, database_id)が読み込めません。")

        # NotionCompilerが期待するDB IDを特定する
        # ここでは、test_bot_config["notion"]["databases"]["curation_main"] を使うことを想定しているが、
        # テスト用に別のDB IDを指定できるようにする。
        # 環境変数や引数でテスト用DB IDを渡せるようにするのが望ましい。
        # 例: TEST_NOTION_DB_ID = os.getenv("TEST_COMPILE_DB_ID")
        # if TEST_NOTION_DB_ID:
        #    if "databases" not in test_bot_config.get("notion", {}): test_bot_config.setdefault("notion", {}).setdefault("databases", {})
        #    test_bot_config["notion"]["databases"]["curation_main"] = TEST_NOTION_DB_ID
        #    print(f"環境変数からテスト用DB IDを設定: {TEST_NOTION_DB_ID}")

        compiler = NotionCompiler(bot_config=test_bot_config)
    except ValueError as e:
        logger.error(f"テスト用NotionCompiler初期化失敗: {e}")
        exit()
    except Exception as e_init:
        logger.error(f"テスト用NotionCompiler初期化中に予期せぬエラー: {e_init}", exc_info=True)
        exit()

    if not compiler.is_client_initialized():
        print("Notionクライアントが初期化されていません。テストを続行できません。config.ymlを確認してください。")
        exit()

    # 1. スキーマ確認・更新テスト
    print("\n--- 1. データベーススキーマ確認・更新テスト ---")
    try:
        compiler.ensure_database_schema()
        print("  スキーマ確認・更新処理が完了しました。エラーがなければ成功です。")
    except Exception as e_schema:
        print(f"  スキーマ確認・更新中にエラーが発生しました: {e_schema}")

    # 2. 処理済みIDロードテスト
    print("\n--- 2. 処理済みアイテムIDロードテスト ---")
    processed_ids = compiler.load_processed_item_ids()
    print(f"  ロードされた処理済みIDの件数: {len(processed_ids)}")
    if processed_ids:
        print(f"  例 (最初の5件): {list(processed_ids)[:5]}")

    # 3. アイテム追加テスト
    print("\n--- 3. Notionへのアイテム追加テスト ---")
    import uuid
    test_item_id = f"test_compile_{uuid.uuid4()}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    sample_item_data = {
        "ツイートID": test_item_id,
        "本文": "これはNotionCompilerからのテスト投稿です。\nリファクタリングされました。",
        "投稿者": "Test User (@testuser)",
        "ツイートURL": f"https://twitter.com/testuser/status/{test_item_id.split('_')[-1]}", # ダミーURL
        "投稿日時": datetime.datetime.now().isoformat(),
        "画像URL1": "https://pbs.twimg.com/media/AAAA.jpg", # ダミー画像URL
        "OCRテキスト": "サンプルOCRテキスト from compiler test",
        "ステータス": "新規"
    }
    print(f"追加予定のアイテムデータ: {sample_item_data}")
    
    # created_page = compiler.add_compiled_item(sample_item_data)
    # if created_page:
    #     print(f"  アイテム追加成功。Page ID: {created_page.get('id')}")
    #     # 4. ステータス更新テスト (追加したアイテムに対して)
    #     print("\n--- 4. アイテムステータス更新テスト ---")
    #     time.sleep(1) # Notion側での反映を少し待つ
    #     update_success = compiler.update_item_status(page_id=created_page.get('id'), status="コンパイル済")
    #     if update_success:
    #         print(f"  ページ {created_page.get('id')} のステータスを「コンパイル済」に更新成功。")
    #     else:
    #         print(f"  ページ {created_page.get('id')} のステータス更新失敗。")
    # else:
    #     print("  アイテム追加失敗。ログを確認してください。")
    print("（実際のアイテム追加・更新処理はコメントアウトされています。テスト時に有効化してください。）")

    print("\n--- NotionCompiler テスト完了 ---") 