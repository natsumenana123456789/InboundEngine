import gspread
from datetime import datetime, timezone, timedelta
import logging
from typing import List, Dict, Optional, Any
import os
import json

from .config import Config

logger = logging.getLogger(__name__)

TRUTHY_VALUES = ["true", "1", "yes", "ok", "✓", "〇", "○", "公開", "投稿可"]

class SpreadsheetManager:
    def __init__(self, config: Config):
        self.config = config
        self.gspread_client = None
        self.columns = self.config.get_spreadsheet_columns()
        if not self.columns:
            raise ValueError("SpreadsheetManager: スプレッドシートの列定義を取得できませんでした。")
        self._authenticate_gspread()

    def _authenticate_gspread(self):
        self.spreadsheet_id = self.config.get_spreadsheet_id()
        gspread_creds_dict = self.config.get_gspread_service_account_dict()

        if not self.spreadsheet_id:
            logger.error("スプレッドシートIDが設定されていません。")
            raise ValueError("Spreadsheet ID is not configured.")
        
        if not gspread_creds_dict:
            logger.error("gspreadサービスアカウント認証情報が設定されていません。")
            raise ValueError("gspread service account credentials are not configured.")
        
        try:
            gc = gspread.service_account_from_dict(gspread_creds_dict)
            self.gspread_client = gc
            logger.info("gspread: Google Spreadsheetへの接続認証に成功しました。")
        except Exception as e:
            logger.error(f"スプレッドシートへの接続または認証に失敗しました: {e}", exc_info=True)
            self.gspread_client = None
            raise

    def _find_value_robustly(self, record: Dict[str, Any], target_column_name: str) -> Optional[Any]:
        """
        設定ファイルで定義された列名を元に、レコードから値を取得する。
        スプレッドシートのヘッダー名の前後の空白、大文字/小文字の違いを吸収する。
        """
        normalized_target = target_column_name.strip().lower()
        for actual_header, value in record.items():
            if actual_header.strip().lower() == normalized_target:
                return value
        # logger.warning(f"列 '{target_column_name}' がスプレッドシートのヘッダーに見つかりませんでした。")
        return None

    def _find_column_index_robustly(self, headers: List[str], target_column_name: str) -> Optional[int]:
        """
        設定ファイルで定義された列名を元に、ヘッダーリストから列のインデックス（1始まり）を取得する。
        ヘッダー名の前後の空白、大文字/小文字の違いを吸収する。
        """
        normalized_target = target_column_name.strip().lower()
        for i, actual_header in enumerate(headers):
            if actual_header.strip().lower() == normalized_target:
                return i + 1
        return None

    def get_post_candidate(self, worksheet_name: str) -> Optional[Dict[str, Any]]:
        """
        指定されたワークシートから投稿可能な記事を1件取得する。
        """
        try:
            worksheet = self.gspread_client.open_by_key(self.spreadsheet_id).worksheet(worksheet_name)
            logger.info(f"ワークシート '{worksheet_name}' を開きました。")
            all_records = worksheet.get_all_records()
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
                postable_val_raw = self._find_value_robustly(record, self.columns['postable'])
                postable_val = str(postable_val_raw or '').strip().lower()

                if postable_val not in TRUTHY_VALUES:
                    continue

                last_posted_str = str(self._find_value_robustly(record, self.columns['last_posted_at']) or '').strip()
                last_posted_dt = datetime.min.replace(tzinfo=timezone.utc)
                if last_posted_str:
                    try:
                        last_posted_dt = datetime.fromisoformat(last_posted_str).astimezone(timezone.utc)
                    except ValueError:
                        try:
                            last_posted_dt = datetime.strptime(last_posted_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                        except ValueError:
                             try:
                                last_posted_dt = datetime.strptime(last_posted_str, '%Y/%m/%d %H:%M:%S').replace(tzinfo=timezone.utc)
                             except ValueError:
                                try:
                                    last_posted_dt = datetime.strptime(last_posted_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                                except ValueError:
                                    logger.warning(f"行 {i+2}: 最終投稿日時の形式が不正です ('{last_posted_str}')。古いものとして扱います。")

                candidates.append({
                    "id": str(self._find_value_robustly(record, self.columns['id']) or ''),
                    "text": str(self._find_value_robustly(record, self.columns['text']) or ''),
                    "media_path": str(self._find_value_robustly(record, self.columns['media_url']) or ''),
                    "last_posted_at": last_posted_dt,
                    "row_index": i + 2
                })
            except Exception as e:
                logger.warning(f"ワークシート '{worksheet_name}' のレコード処理中にエラー (行 {i+2}): {record} - {e}", exc_info=True)
                continue
        
        if not candidates:
            logger.warning(f"ワークシート '{worksheet_name}' に投稿可能な候補が見つかりませんでした。")
            return None

        candidates.sort(key=lambda x: x["last_posted_at"])
        selected_candidate = candidates[0]
        logger.info(f"ワークシート '{worksheet_name}' から投稿候補を選択しました (ID: {selected_candidate['id']}, 行: {selected_candidate['row_index']})。")
        return selected_candidate

    def update_post_status(self, worksheet_name: str, row_index: int, posted_at: datetime) -> bool:
        """
        指定されたワークシートの行について、投稿済み回数を1増やし、最終投稿日時を更新する。
        """
        try:
            worksheet = self.gspread_client.open_by_key(self.spreadsheet_id).worksheet(worksheet_name)
            headers = worksheet.row_values(1)
            
            posted_count_col_idx = self._find_column_index_robustly(headers, self.columns['posted_count'])
            if not posted_count_col_idx:
                logger.error(f"ワークシート '{worksheet_name}' のヘッダーに列名 '{self.columns['posted_count']}' が見つかりません。")
                return False
            
            last_posted_col_idx = self._find_column_index_robustly(headers, self.columns['last_posted_at'])
            if not last_posted_col_idx:
                logger.error(f"ワークシート '{worksheet_name}' のヘッダーに列名 '{self.columns['last_posted_at']}' が見つかりません。")
                return False

            current_posted_count_str = worksheet.cell(row_index, posted_count_col_idx).value
            current_posted_count = 0
            if current_posted_count_str and str(current_posted_count_str).strip():
                try:
                    current_posted_count = int(str(current_posted_count_str).strip())
                except ValueError:
                    logger.warning(f"ワークシート '{worksheet_name}' 行 {row_index} の投稿済み回数 '{current_posted_count_str}' が数値ではありません。0として扱います。")
            new_posted_count = current_posted_count + 1

            jst = timezone(timedelta(hours=9))
            posted_at_jst = posted_at.astimezone(jst)
            
            updates = [
                gspread.Cell(row_index, posted_count_col_idx, str(new_posted_count)),
                gspread.Cell(row_index, last_posted_col_idx, posted_at_jst.strftime("%Y-%m-%d %H:%M:%S"))
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
                    logger.info(f"取得した投稿候補: ID={candidate['id']}, Text='{candidate['text'][:30]}...', Media='{candidate['media_path']}', Row={candidate['row_index']}")
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