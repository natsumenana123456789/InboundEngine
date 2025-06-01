import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta
import logging
from typing import List, Dict, Optional, Tuple, Any

# このモジュールがengine_coreパッケージ内にあることを想定してConfigをインポート
from .config import Config

logger = logging.getLogger(__name__)

# 「投稿可能」列の真偽値として認識する文字列（大文字・小文字を区別しない）
TRUTHY_VALUES = ["true", "1", "yes", "ok", "✓", "〇", "○", "公開", "投稿可"]

class SpreadsheetManager:
    def __init__(self, config: Config, bot_type: str = "auto_post_bot"):
        self.config = config
        self.bot_type = bot_type
        self.spreadsheet_id = self.config.get_spreadsheet_id()
        self.gspread_key_path = self.config.gspread_service_account_key_path
        self.columns = self.config.get_spreadsheet_columns(bot_type)

        if not self.spreadsheet_id:
            logger.error("Spreadsheet IDが設定されていません。")
            raise ValueError("Spreadsheet ID is not configured.")
        if not self.gspread_key_path:
            logger.error("gspreadサービスアカウントキーのパスが設定されていません。")
            raise ValueError("gspread service account key path is not configured.")
        if not self.columns:
            logger.error(f"{bot_type} 用の列定義が見つかりません。")
            raise ValueError(f"Spreadsheet columns for {bot_type} are not configured.")
        
        try:
            self.creds = Credentials.from_service_account_file(
                self.gspread_key_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            # self.client = gspread.authorize(self.creds) # authorize で得られる client の型が不明確な場合がある
            # self.spreadsheet = self.client.open_by_id(self.spreadsheet_id) # これがエラー

            # gspread.service_account を使用する形に変更
            gc = gspread.service_account(filename=self.gspread_key_path)
            self.spreadsheet = gc.open_by_key(self.spreadsheet_id) # open_by_key は ID を受け入れる

            logger.info(f"スプレッドシート (ID: {self.spreadsheet_id}) への接続に成功しました。")
        except Exception as e:
            logger.error(f"スプレッドシートへの接続または認証に失敗しました: {e}", exc_info=True)
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
            worksheet = self.spreadsheet.worksheet(worksheet_name)
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
        """
        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            
            # "投稿済み回数" 列の現在の値を取得し、1増やす
            posted_count_col_idx = self._get_column_index("投稿済み回数")
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

            # "最終投稿日時" 列を更新
            last_posted_col_idx = self._get_column_index("最終投稿日時")
            
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

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger.info("SpreadsheetManagerのテストを開始します。")
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file_path = os.path.join(project_root, "config/config.yml")
        
        config = Config(config_path=config_file_path)
        manager = SpreadsheetManager(config)

        # config.yml から最初のTwitterアカウントの情報を取得して、そのワークシート名を使用
        twitter_accounts = config.get_twitter_accounts()
        if not twitter_accounts:
            logger.error("config.ymlにTwitterアカウントが設定されていません。テストをスキップします。")
        else:
            target_worksheet_name = twitter_accounts[0].get("spreadsheet_worksheet")
            if not target_worksheet_name:
                 logger.error(f"アカウント {twitter_accounts[0].get('account_id')} にspreadsheet_worksheetが設定されていません。")
            else:
                logger.info(f"テスト対象ワークシート: {target_worksheet_name}")
                candidate = manager.get_post_candidate(target_worksheet_name)

                if candidate:
                    logger.info(f"取得した投稿候補: ID={candidate['id']}, Text='{candidate['text'][:30]}...', Media='{candidate['media_url']}', Row={candidate['row_index']}")
                    # テスト用に現在のUTC時刻で更新
                    now_utc = datetime.now(timezone.utc)
                    success = manager.update_post_status(target_worksheet_name, candidate['row_index'], now_utc)
                    if success:
                        logger.info("投稿ステータスの更新テスト成功。")
                    else:
                        logger.error("投稿ステータスの更新テスト失敗。")
                else:
                    logger.info(f"{target_worksheet_name} に投稿可能な記事がありませんでした。")

    except ValueError as ve:
        logger.error(f"設定エラー: {ve}")
    except Exception as e:
        logger.error(f"SpreadsheetManagerのテスト中に予期せぬエラーが発生: {e}", exc_info=True) 