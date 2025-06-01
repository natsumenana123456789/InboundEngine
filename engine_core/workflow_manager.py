import logging
import os
import json
from datetime import datetime, date, timezone, timedelta
from typing import List, Optional, Dict, Any

from .config import Config
from .spreadsheet_manager import SpreadsheetManager
from .discord_notifier import DiscordNotifier
from .scheduler.post_scheduler import PostScheduler, ScheduledPost
from .scheduler.scheduled_post_executor import ScheduledPostExecutor

logger = logging.getLogger(__name__)

# デフォルトのログディレクトリとファイル名
LOGS_DIR = "logs"
SCHEDULE_FILE_NAME = "schedule.txt"
EXECUTED_LOG_FILE_NAME = "executed.txt"

class WorkflowManager:
    def __init__(self, config: Config):
        self.config = config
        self.logs_dir = self.config.get("common.logs_directory", LOGS_DIR)
        os.makedirs(self.logs_dir, exist_ok=True)

        self.schedule_file_path = os.path.join(self.logs_dir, SCHEDULE_FILE_NAME)
        self.executed_log_file_path = os.path.join(self.logs_dir, EXECUTED_LOG_FILE_NAME)

        # コアコンポーネントの初期化
        self.spreadsheet_manager = SpreadsheetManager(config=self.config)
        self.post_scheduler = PostScheduler(config=self.config)
        self.post_executor = ScheduledPostExecutor(config=self.config, spreadsheet_manager=self.spreadsheet_manager)
        
        # 通知用Notifier (WorkflowManager自身の通知用)
        wf_notifier_webhook_url = self.config.get_discord_webhook_url("workflow_notifications") # config.ymlに専用IDを設定想定
        if wf_notifier_webhook_url:
            self.workflow_notifier = DiscordNotifier(webhook_url=wf_notifier_webhook_url)
        elif self.post_executor.default_notifier: # executorのものを借用
            self.workflow_notifier = self.post_executor.default_notifier
            logger.info("Workflow通知用にExecutorのデフォルトNotifierを使用します。")
        else:
            self.workflow_notifier = None
            logger.warning("WorkflowManager用のDiscord通知クライアントが設定されていません。")

        logger.info("WorkflowManager初期化完了。")

    def _save_schedule_to_file(self, schedule: List[ScheduledPost], target_date: date):
        """生成されたスケジュールをファイルにJSON形式で保存する。日付ごとに追記または上書き。"""
        # 日付をキーとした辞書として保存する
        full_schedule_data: Dict[str, List[Dict[str, Any]]] = {}
        if os.path.exists(self.schedule_file_path):
            try:
                with open(self.schedule_file_path, 'r', encoding='utf-8') as f:
                    full_schedule_data = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"既存のスケジュールファイル {self.schedule_file_path} が破損しているようです。上書きします。")
            except Exception as e:
                logger.error(f"既存のスケジュールファイル読み込みエラー: {e}", exc_info=True)
                # エラー時は上書きする
        
        # ScheduledPostをJSONシリアライズ可能な形式に変換
        serializable_schedule = [
            {
                "account_id": post["account_id"],
                "scheduled_time": post["scheduled_time"].isoformat(), # datetimeをISO文字列に
                "worksheet_name": post["worksheet_name"]
            }
            for post in schedule
        ]
        
        full_schedule_data[target_date.isoformat()] = serializable_schedule

        try:
            with open(self.schedule_file_path, 'w', encoding='utf-8') as f:
                json.dump(full_schedule_data, f, ensure_ascii=False, indent=4)
            logger.info(f"{target_date.isoformat()} のスケジュール ({len(schedule)}件) を {self.schedule_file_path} に保存しました。")
        except Exception as e:
            logger.error(f"スケジュールファイルの保存に失敗: {e}", exc_info=True)

    def _load_schedule_from_file(self, target_date: date) -> List[ScheduledPost]:
        """ファイルから指定された日付のスケジュールを読み込む。"""
        if not os.path.exists(self.schedule_file_path):
            logger.info(f"スケジュールファイル {self.schedule_file_path} が存在しません。")
            return []
        try:
            with open(self.schedule_file_path, 'r', encoding='utf-8') as f:
                full_schedule_data: Dict[str, List[Dict[str, Any]]] = json.load(f)
            
            date_str = target_date.isoformat()
            if date_str not in full_schedule_data:
                logger.info(f"{date_str} のスケジュールはファイルに存在しません。")
                return []
            
            loaded_schedule_data = full_schedule_data[date_str]
            # JSONからScheduledPost型に変換
            schedule: List[ScheduledPost] = []
            for item_dict in loaded_schedule_data:
                try:
                    # datetimeをISO文字列からパース。タイムゾーン情報を付与（UTCと仮定）
                    # もし保存時にタイムゾーンがなければ、ここで付与する。パース時に awareにする。
                    scheduled_time_dt = datetime.fromisoformat(item_dict["scheduled_time"])
                    if scheduled_time_dt.tzinfo is None:
                         scheduled_time_dt = scheduled_time_dt.replace(tzinfo=timezone.utc)

                    schedule.append({
                        "account_id": item_dict["account_id"],
                        "scheduled_time": scheduled_time_dt,
                        "worksheet_name": item_dict["worksheet_name"]
                    })
                except Exception as e:
                    logger.warning(f"スケジュール項目のパースに失敗: {item_dict}, Error: {e}. スキップします。")
                    continue
            logger.info(f"{date_str} のスケジュール ({len(schedule)}件) を {self.schedule_file_path} から読み込みました。")
            return schedule
        except json.JSONDecodeError:
            logger.error(f"スケジュールファイル {self.schedule_file_path} が破損しています。")
            return []
        except Exception as e:
            logger.error(f"スケジュールファイルの読み込みに失敗: {e}", exc_info=True)
            return []

    def _log_executed_post(self, scheduled_post: ScheduledPost, success: bool, tweet_id: Optional[str] = None, error_reason: Optional[str] = None):
        """実行結果をログファイルに追記する。"""
        log_entry = {
            "account_id": scheduled_post["account_id"],
            "worksheet_name": scheduled_post["worksheet_name"],
            "scheduled_time": scheduled_post["scheduled_time"].isoformat(),
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "tweet_id": tweet_id,
            "error_reason": error_reason
        }
        try:
            with open(self.executed_log_file_path, 'a', encoding='utf-8') as f:
                json.dump(log_entry, f, ensure_ascii=False)
                f.write('\n') # 1行1エントリ
            logger.debug(f"実行ログ追記: Account={log_entry['account_id']}, Success={success}")
        except Exception as e:
            logger.error(f"実行ログの書き込みに失敗: {e}", exc_info=True)

    def generate_daily_schedule(self, target_date: Optional[date] = None, force_regenerate: bool = False):
        """指定された日付（デフォルトは今日）のスケジュールを生成しファイルに保存する。"""
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()
        
        logger.info(f"{target_date.isoformat()} のスケジュール生成処理を開始します。強制再生成: {force_regenerate}")
        
        # 強制再生成でない場合、既存のスケジュールがあればそれを使用
        if not force_regenerate:
            existing_schedule = self._load_schedule_from_file(target_date)
            if existing_schedule:
                logger.info(f"{target_date.isoformat()} の既存スケジュールが見つかったため、再生成をスキップします。")
                if self.workflow_notifier:
                    self.workflow_notifier.send_simple_notification(
                        title=f"🗓️ スケジュール生成スキップ ({target_date.isoformat()})",
                        description=f"{target_date.isoformat()} のスケジュールは既に存在します。({len(existing_schedule)}件)",
                        color=0x0000ff # 青色
                    )
                return

        schedule = self.post_scheduler.generate_schedule_for_day(target_date)
        self._save_schedule_to_file(schedule, target_date)
        if self.workflow_notifier:
            self.workflow_notifier.send_simple_notification(
                title=f"📅 スケジュール生成完了 ({target_date.isoformat()})",
                description=f"{target_date.isoformat()} の投稿スケジュールを {len(schedule)} 件生成しました。詳細はログファイルを確認してください。",
                color=0x00ff00 if schedule else 0xffa500 # 投稿があれば緑、なければオレンジ
            )
        logger.info(f"{target_date.isoformat()} のスケジュール生成処理を完了しました。")

    def process_scheduled_posts_now(self, target_date: Optional[date] = None, look_back_minutes: int = 15, look_forward_minutes: int = 5):
        """
        指定された日付（デフォルトは今日）のスケジュールを読み込み、
        現在時刻の前後N分以内に予定されている未実行の投稿を実行する。
        """
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        logger.info(f"{target_date.isoformat()} のスケジュール投稿処理を開始 (現在時刻ベース)。")
        schedule = self._load_schedule_from_file(target_date)
        if not schedule:
            logger.info(f"{target_date.isoformat()} に実行すべきスケジュールはありません。")
            # 通知はgenerate時か、別途cronの実行監視で行う想定
            return

        now_utc = datetime.now(timezone.utc)
        # 実行済みログから、今日実行成功したタスクのキー(account_id, scheduled_time_iso)セットを取得
        executed_today_keys = set()
        if os.path.exists(self.executed_log_file_path):
            try:
                with open(self.executed_log_file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line)
                            # scheduled_timeはISO文字列なので、日付部分で比較
                            if log_entry.get("success") and log_entry.get("scheduled_time", "").startswith(target_date.isoformat()):
                                executed_today_keys.add((log_entry["account_id"], log_entry["scheduled_time"]))                                
                        except json.JSONDecodeError:
                            continue # 不正な行はスキップ
            except Exception as e:
                logger.error(f"実行ログファイルの読み込みエラー: {e}", exc_info=True)
        
        logger.debug(f"本日 ({target_date.isoformat()}) 実行済みのタスクキー: {len(executed_today_keys)}件")

        due_posts_count = 0
        successful_posts_count = 0

        for post_item in schedule:
            scheduled_time_utc = post_item["scheduled_time"] # 保存時にUTCのはず
            # 念のため aware でなければ aware にする
            if scheduled_time_utc.tzinfo is None:
                scheduled_time_utc = scheduled_time_utc.replace(tzinfo=timezone.utc)

            task_key = (post_item["account_id"], scheduled_time_utc.isoformat())
            if task_key in executed_today_keys:
                # logger.debug(f"タスク {task_key} は既に実行済みのためスキップします。")
                continue

            # 現在時刻から見て、実行対象期間内か？
            # 予定時刻が (now - look_back) から (now + look_forward) の間
            if (now_utc - timedelta(minutes=look_back_minutes)) <= scheduled_time_utc <= (now_utc + timedelta(minutes=look_forward_minutes)):
                due_posts_count += 1
                logger.info(f"実行対象タスク: {post_item['account_id']} @ {scheduled_time_utc.strftime('%H:%M:%S')}")
                
                returned_tweet_id: Optional[str] = None
                success_flag: bool = False
                error_reason_val: Optional[str] = "不明な実行エラー"
                try:
                    returned_tweet_id = self.post_executor.execute_post(post_item)
                    if returned_tweet_id:
                        successful_posts_count +=1
                        success_flag = True
                        error_reason_val = None 
                    else:
                        # execute_postがNoneを返した場合、記事なし or 本文なし or APIキーなし等、またはツイート投稿失敗
                        # 詳細な理由はexecutorのログや通知で記録されているはず
                        error_reason_val = "投稿実行条件未達 (記事なし等) またはAPIエラー (Executorログ参照)" 
                        logger.warning(f"タスク {task_key} は実行されましたが、投稿には至りませんでした (Tweet IDなし)。")
                except Exception as e:
                    logger.error(f"タスク {task_key} の実行中に予期せぬエラー: {e}", exc_info=True)
                    error_reason_val = str(e)
                    success_flag = False # 念のため
                    # executor側で通知しているはずなので、ここでは重複通知を避けるか、より上位のエラーとして通知
                finally:
                    self._log_executed_post(post_item, success_flag, tweet_id=returned_tweet_id, error_reason=error_reason_val)
            # else:
                # logger.debug(f"タスク {task_key} は現在時刻の実行対象外です ({scheduled_time_utc.strftime('%H:%M:%S')} vs Now {now_utc.strftime('%H:%M:%S')}).")
        
        logger.info(f"{target_date.isoformat()} のスケジュール投稿処理完了。実行対象 {due_posts_count}件中、成功 {successful_posts_count}件。")
        if self.workflow_notifier and due_posts_count > 0: # 何か実行試行があった場合のみ通知
             self.workflow_notifier.send_simple_notification(
                title=f"⚙️ 定時投稿処理完了 ({target_date.isoformat()})",
                description=f"{due_posts_count}件の投稿を処理し、{successful_posts_count}件が成功しました。詳細はログを確認してください。",
                color=0x0000ff if successful_posts_count == due_posts_count else (0xffa500 if successful_posts_count > 0 else 0xff0000)
            ) 