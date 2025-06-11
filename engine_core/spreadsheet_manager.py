import gspread
# from google.oauth2.service_account import Credentials # gspread.service_account_from_dict を使うので不要になる可能性
from datetime import datetime, timezone, timedelta
import logging
from typing import List, Dict, Optional, Tuple, Any
import os # if __name__ == '__main__' でのパス解決用に os をインポート
import json # if __name__ == '__main__' でのダミーAPP_CONFIG_JSON用に json をインポート

# このモジュールがengine_coreパッケージ内にあることを想定してConfigをインポート
from .config import Config

logger = logging.getLogger(__name__)

# 「投稿可能」列の真偽値として認識する文字列（大文字・小文字を区別しない）
TRUTHY_VALUES = ["true", "1", "yes", "ok", "✓", "〇", "○", "公開", "投稿可"]

class SpreadsheetManager:
    def __init__(self, config: Config):
        self.config = config
        self.gspread_client = None
        self.bot_type = self.config.get("common.bot_type", "default_bot") # bot_type をConfigから取得(任意)
        
        # get_spreadsheet_columns 呼び出し時の引数を削除
        self.columns = self.config.get_spreadsheet_columns()
        if not self.columns:
            logger.critical("SpreadsheetManager: スプレッドシートの列定義を取得できませんでした。処理を続行できません。")
            # ここで例外を発生させるか、あるいは利用側で self.columns が None でないことを確認する
            # raise ValueError("スプレッドシートの列定義がありません。")

        self._authenticate_gspread()

    def _authenticate_gspread(self):
        self.spreadsheet_id = self.config.get_spreadsheet_id()
        gspread_creds_dict = self.config.get_gspread_service_account_dict()

        if not self.spreadsheet_id:
            logger.error("スプレッドシートIDが設定されていません (APP_CONFIG_JSONのgoogle_sheets.spreadsheet_id)。")
            # クリティカルなエラーなので、ここで処理を中断するか、呼び出し元にNoneを返して対処させる
            raise ValueError("Spreadsheet ID is not configured.")
        
        if not gspread_creds_dict:
            logger.error("gspreadサービスアカウント認証情報が設定されていません (APP_CONFIG_JSONのgoogle_sheets.service_account_credentials)。")
            raise ValueError("gspread service account credentials are not configured.")
        
        try:
            # キーワード引数 credentials= を削除
            gc = gspread.service_account_from_dict(gspread_creds_dict)
            self.gspread_client = gc
            logger.info("gspread: Google Spreadsheetへの接続認証に成功しました。")
        except Exception as e:
            logger.error(f"スプレッドシートへの接続または認証に失敗しました: {e}", exc_info=True)
            # ここで None のままにしておき、利用側で self.gspread_client が None かどうかを確認する
            # あるいは例外を再送出する
            self.gspread_client = None # 失敗したことを明確にする
            raise

    def _get_column_index(self, column_name: str) -> int:
        """列名から1始まりのインデックスを取得する"""
        try:
            return self.columns.index(column_name) + 1
        except ValueError:
            logger.error(f"列名 '{column_name}' が定義されていません。設定された列: {self.columns}")
            raise ValueError(f"Column '{column_name}' not found in configured columns.")

    def get_post_candidate(self, worksheet_name: str) -> Optional[Dict[str, Any]]:
        """
        指定されたワークシートから投稿可能な記事を1件取得する。
        条件:「投稿可能」列が真偽値としてTrue、「最終投稿日時」が古い順。
        取得する情報: ID, 本文, 画像/動画URL, および行インデックス (更新用)
        """
        try:
            worksheet = self.gspread_client.open_by_key(self.spreadsheet_id).worksheet(worksheet_name)
            logger.info(f"ワークシート '{worksheet_name}' を開きました。")
            all_records = worksheet.get_all_records() # ヘッダーをキーとした辞書のリストとして取得
            logger.debug(f"ワークシート '{worksheet_name}' から {len(all_records)} 件のレコードを取得しました。")

        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"ワークシート '{worksheet_name}' が見つかりません。")
            return None
        except Exception as e:
            logger.error(f"ワークシート '{worksheet_name}' の読み込み中にエラー: {e}", exc_info=True)
            return None

        candidates = []
        for i, record in enumerate(all_records):
            try:
                # "投稿可能" 列の値を取得し、文字列に変換して小文字で比較
                # config.ymlで定義された "投稿可能" にあたる列名を取得
                postable_column_name_in_config = "投稿可能" # これはconfigから取得した抽象的な列名
                actual_column_name_header = self.columns[self._get_column_index(postable_column_name_in_config) -1]
                
                postable_val = str(record.get(actual_column_name_header, '')).lower().strip()
                
                if not postable_val in TRUTHY_VALUES:
                    logger.debug(f"行 {i+2}: 列 '{actual_column_name_header}' の値 ('{record.get(actual_column_name_header)}') が非許可条件のためスキップ。正規化後: '{postable_val}'")
                    continue

                # "最終投稿日時" 列の値を取得。空の場合は非常に古い日時として扱う
                last_posted_str = str(record.get(self.columns[self._get_column_index("最終投稿日時") -1], '')).strip()
                last_posted_dt = datetime.min.replace(tzinfo=timezone.utc) # タイムゾーン対応
                if last_posted_str:
                    try:
                        # 様々な日付形式に対応するため、柔軟なパースを試みる (例)
                        # 最も一般的な形式から試す。必要に応じてパース形式を追加・変更。
                        last_posted_dt = datetime.strptime(last_posted_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                    except ValueError:
                        try:
                            last_posted_dt = datetime.strptime(last_posted_str, '%Y/%m/%d %H:%M:%S').replace(tzinfo=timezone.utc)
                        except ValueError:
                            try: # 日付のみの場合
                                last_posted_dt = datetime.strptime(last_posted_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                            except ValueError:
                                logger.warning(f"行 {i+2}: 最終投稿日時の形式が不正です ('{last_posted_str}')。古いものとして扱います。")
                
                candidates.append({
                    "id": str(record.get(self.columns[self._get_column_index("ID") -1], '')),
                    "text": str(record.get(self.columns[self._get_column_index("本文") -1], '')),
                    "media_url": str(record.get(self.columns[self._get_column_index("画像/動画URL")-1], '')),
                    "last_posted_at": last_posted_dt,
                    "row_index": i + 2  # スプレッドシートの行番号 (ヘッダーが1行目なので+2)
                })
            except Exception as e:
                logger.warning(f"ワークシート '{worksheet_name}' のレコード処理中にエラー (行 {i+2}): {record} - {e}", exc_info=True)
                continue
        
        if not candidates:
            logger.info(f"ワークシート '{worksheet_name}' に投稿可能な候補が見つかりませんでした。")
            return None

        # 最終投稿日時が古い順にソート
        candidates.sort(key=lambda x: x["last_posted_at"])
        selected_candidate = candidates[0]
        logger.info(f"ワークシート '{worksheet_name}' から投稿候補を選択しました (ID: {selected_candidate['id']}, 行: {selected_candidate['row_index']})。")
        return selected_candidate

    def update_post_status(self, worksheet_name: str, row_index: int, posted_at: datetime) -> bool:
        """
        指定されたワークシートの行について、投稿済み回数を1増やし、最終投稿日時を更新する。
        列名（ヘッダー）を使って更新対象の列を特定する。
        """
        try:
            worksheet = self.gspread_client.open_by_key(self.spreadsheet_id).worksheet(worksheet_name)
            
            # --- ヘッダー名から列のインデックスを動的に取得 ---
            headers = worksheet.row_values(1)
            
            # 設定ファイルから抽象的な列名を取得
            posted_count_col_name = self.columns[self._get_column_index("投稿済み回数") - 1]
            last_posted_col_name = self.columns[self._get_column_index("最終投稿日時") - 1]

            # ヘッダー名に一致する列のインデックス（1始まり）を探す
            try:
                posted_count_col_idx = headers.index(posted_count_col_name) + 1
            except ValueError:
                logger.error(f"ワークシート '{worksheet_name}' のヘッダーに列名 '{posted_count_col_name}' が見つかりません。")
                return False
            
            try:
                last_posted_col_idx = headers.index(last_posted_col_name) + 1
            except ValueError:
                logger.error(f"ワークシート '{worksheet_name}' のヘッダーに列名 '{last_posted_col_name}' が見つかりません。")
                return False

            # "投稿済み回数" 列の現在の値を取得し、1増やす
            current_posted_count_str = worksheet.cell(row_index, posted_count_col_idx).value
            if current_posted_count_str is None or str(current_posted_count_str).strip() == "":
                current_posted_count = 0
            else:
                try:
                    current_posted_count = int(str(current_posted_count_str).strip())
                except ValueError:
                    logger.warning(f"ワークシート '{worksheet_name}' 行 {row_index} の投稿済み回数 '{current_posted_count_str}' が数値ではありません。0として扱います。")
                    current_posted_count = 0
            new_posted_count = current_posted_count + 1

            # posted_at をJSTに変換
            jst = timezone(timedelta(hours=9))
            posted_at_jst = posted_at.astimezone(jst)
            
            # 更新する値をリストで準備
            updates = [
                gspread.Cell(row_index, posted_count_col_idx, str(new_posted_count)),
                gspread.Cell(row_index, last_posted_col_idx, posted_at_jst.strftime("%Y-%m-%d %H:%M:%S")) # JSTでフォーマット
            ]
            worksheet.update_cells(updates, value_input_option='USER_ENTERED')
            
            logger.info(f"ワークシート '{worksheet_name}' 行 {row_index} のステータスを更新しました (投稿回数: {new_posted_count}, 最終投稿(JST): {posted_at_jst.strftime('%Y-%m-%d %H:%M:%S')})。")
            return True
        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"ワークシート '{worksheet_name}' が見つかりません。更新できませんでした。")
            return False
        except Exception as e:
            logger.error(f"ワークシート '{worksheet_name}' 行 {row_index} の更新中にエラー: {e}", exc_info=True)
            return False

    def get_worksheet_by_name(self, worksheet_name: str) -> Optional[gspread.Worksheet]:
        # This method is not provided in the original file or the code block
        # It's assumed to exist as it's called in the get_post_candidate method
        # It's also called in the update_post_status method
        # It's assumed to return a gspread.Worksheet object if the worksheet exists
        # If the worksheet does not exist, it returns None
        # This method should be implemented to return the worksheet object
        # or None if the worksheet does not exist
        pass

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger.info("SpreadsheetManagerのテストを開始します。")

    # --- テスト用の APP_CONFIG_JSON の準備 (Configクラスのテストから拝借・簡略化) ---
    dummy_gspread_creds_for_sm_test = {
        "type": "service_account", "project_id": "dummy-sm-project",
        "private_key_id": "dummy_key_id_sm", "private_key": "-----BEGIN PRIVATE KEY-----\nSM TEST\n-----END PRIVATE KEY-----\n",
        "client_email": "dummy-sm@dummy-sm-project.iam.gserviceaccount.com", "client_id": "dummy_client_id_sm",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/dummy-sm%40dummy-sm-project.iam.gserviceaccount.com"
    }
    test_app_config_for_sm = {
        "twitter_accounts": [{
            "account_id": "sm_tester", "enabled": True,
            "google_sheets_source": {"worksheet_name": "Sheet1"} # テストで参照するワークシート名
        }],
        "google_sheets": {
            "spreadsheet_id": "1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA", # ユーザーが使用している実際のIDを使用
            "service_account_credentials_json_str": json.dumps(dummy_gspread_creds_for_sm_test)
        },
        "common": {"log_level": "DEBUG"}
        # auto_post_bot.columns などは Config のデフォルト値が使われる想定
    }
    os.environ["APP_CONFIG_JSON"] = json.dumps(test_app_config_for_sm)
    logger.info("SpreadsheetManagerテスト用に環境変数 APP_CONFIG_JSON を設定しました。")
    # --- ここまでテスト用準備 ---

    try:
        config = Config() # 引数なしで初期化
        manager = SpreadsheetManager(config)

        twitter_accounts = config.get_twitter_accounts()
        if not twitter_accounts:
            logger.error("APP_CONFIG_JSONにTwitterアカウントが設定されていません。テストをスキップします。")
        else:
            # get_active_twitter_account_details を使う方が適切かもしれないが、
            # ここでは Config から直接 worksheet_name を取得するのではなく、
            # manager が内部で使う account_id に紐づく worksheet_name をテストデータから取得する。
            # ただし、SpreadsheetManager は直接 worksheet_name を引数に取るので、
            # ここではConfigから最初の有効なアカウントのworksheet_nameを取得する。
            
            active_account_details = config.get_active_twitter_account_details(twitter_accounts[0].get("account_id"))

            if not active_account_details or not active_account_details.get("spreadsheet_worksheet"):
                 logger.error(f"アカウント {twitter_accounts[0].get('account_id')} にspreadsheet_worksheetが設定されていません。")
            else:
                target_worksheet_name = active_account_details.get("spreadsheet_worksheet")
                logger.info(f"テスト対象ワークシート: {target_worksheet_name}")
                
                # 実際のGoogle Sheets APIに接続するため、認証情報とシートIDが有効である必要がある。
                # ダミーの認証情報では get_post_candidate は失敗する。
                logger.warning("以下のテストは、APP_CONFIG_JSON 内のGoogle Sheets認証情報とスプレッドシートIDが有効な場合にのみ成功します。")
                logger.warning(f"現在、テスト用のダミー認証情報 (project_id: {dummy_gspread_creds_for_sm_test.get('project_id')}) を使用しています。")

                candidate = manager.get_post_candidate(target_worksheet_name)

                if candidate:
                    logger.info(f"取得した投稿候補: ID={candidate['id']}, Text='{candidate['text'][:30]}...', Media='{candidate['media_url']}', Row={candidate['row_index']}")
                    now_utc = datetime.now(timezone.utc)
                    success = manager.update_post_status(target_worksheet_name, candidate['row_index'], now_utc)
                    if success:
                        logger.info("投稿ステータスの更新テスト成功。")
                    else:
                        logger.error("投稿ステータスの更新テスト失敗。")
                else:
                    logger.info(f"{target_worksheet_name} に投稿可能な記事がありませんでした（またはAPI接続失敗）。")

    except ValueError as ve:
        logger.error(f"設定エラー: {ve}")
    except Exception as e:
        logger.error(f"SpreadsheetManagerのテスト中に予期せぬエラーが発生: {e}", exc_info=True)
    finally:
        if "APP_CONFIG_JSON" in os.environ:
            del os.environ["APP_CONFIG_JSON"]
            logger.info("SpreadsheetManagerテスト用の環境変数 APP_CONFIG_JSON をクリアしました。") 