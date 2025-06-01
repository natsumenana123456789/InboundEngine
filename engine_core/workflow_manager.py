import logging
import os
import json
from datetime import datetime, date, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple

from .config import Config
from .spreadsheet_manager import SpreadsheetManager
from .discord_notifier import DiscordNotifier
from .scheduler.post_scheduler import PostScheduler, ScheduledPost
from .scheduler.scheduled_post_executor import ScheduledPostExecutor

logger = logging.getLogger(__name__)

# LOGS_DIR は config から取得するので、グローバル定数は不要になるか、デフォルトとしてのみ使用
# SCHEDULE_FILE_NAME と EXECUTED_LOG_FILE_NAME も同様

class WorkflowManager:
    def __init__(self, config: Config, schedule_file_path: str, executed_file_path: str):
        self.config = config
        self.logs_dir = self.config.get("common.logs_directory", "logs") # デフォルト値を指定
        os.makedirs(self.logs_dir, exist_ok=True) # logs_dirの存在確認と作成

        # 引数で渡されたファイルパスを使用
        self.schedule_file_path = schedule_file_path
        self.executed_log_file_path = executed_file_path

        # コアコンポーネントの初期化
        self.spreadsheet_manager = SpreadsheetManager(config=self.config)
        
        # PostScheduler と ScheduledPostExecutor の初期化に必要な情報をconfigから取得
        schedule_settings = self.config.get_schedule_config()
        if not schedule_settings:
            msg = "スケジューラ設定 (auto_post_bot.schedule_settings) がconfig.ymlに見つかりません。"
            logger.error(msg)
            raise ValueError(msg)

        posts_per_account = self.config.get_posts_per_account_schedule() or {}

        self.post_scheduler = PostScheduler(
            config=self.config,
            start_hour=schedule_settings.get("start_hour", 9),
            end_hour=schedule_settings.get("end_hour", 21),
            min_interval_minutes=schedule_settings.get("min_interval_minutes", 30),
            posts_per_account_schedule=posts_per_account,
            schedule_file_path=self.schedule_file_path, # ここで渡す
            max_posts_per_hour_globally=schedule_settings.get("max_posts_per_hour_globally")
        )
        self.post_executor = ScheduledPostExecutor(
            config=self.config, 
            spreadsheet_manager=self.spreadsheet_manager,
            executed_file_path=self.executed_log_file_path # ここで渡す
        )
        
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

        # DiscordNotifierの初期化 (日次サマリー通知用)
        self.summary_notifier: Optional[DiscordNotifier] = None
        if self.config.should_notify_daily_schedule_summary():
            webhook_url = self.config.get_discord_webhook_url("default_notification") # または専用ID
            if webhook_url:
                self.summary_notifier = DiscordNotifier(webhook_url)
                logger.info("日次スケジュールサマリー通知用のDiscordNotifierを初期化しました。")
            else:
                logger.warning("日次スケジュールサマリー通知は有効ですが、Discord Webhook URLが設定されていません。")
        else:
            logger.info("日次スケジュールサマリー通知は無効です。")

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
                    time_str = item_dict["scheduled_time"]
                    if time_str.endswith('Z'):
                        time_str = time_str[:-1] + '+00:00'
                    scheduled_time_dt = datetime.fromisoformat(time_str)

                    if scheduled_time_dt.tzinfo is None: # 基本的には+00:00でawareになるはず
                         logger.warning(f"Parsed datetime {scheduled_time_dt} is naive, forcing UTC. Original str: {item_dict['scheduled_time']}")
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
                            logger.debug(f"実行ログの不正な行をスキップ: {line.strip()}") # DEBUGログ追加
                            continue # 不正な行はスキップ
            except Exception as e:
                logger.error(f"実行ログファイルの読み込みエラー: {e}", exc_info=True)
        
        logger.debug(f"本日 ({target_date.isoformat()}) 実行済みのタスクキー: {len(executed_today_keys)}件 {executed_today_keys if executed_today_keys else ''}") # DEBUGログ追加

        due_posts_count = 0
        successful_posts_count = 0

        logger.debug(f"スケジュール処理開始: now_utc={now_utc.isoformat()}, look_back={look_back_minutes}min, look_forward={look_forward_minutes}min") # DEBUGログ追加
        time_range_start = now_utc - timedelta(minutes=look_back_minutes)
        time_range_end = now_utc + timedelta(minutes=look_forward_minutes)
        logger.debug(f"実行対象時間範囲: {time_range_start.isoformat()} から {time_range_end.isoformat()} まで") # DEBUGログ追加

        for i, post_item in enumerate(schedule):
            logger.debug(f"スケジュール項目 {i+1}/{len(schedule)} を処理中: {post_item}") # DEBUGログ追加
            scheduled_time_utc = post_item["scheduled_time"]
            logger.debug(f"  - 元のscheduled_time: {scheduled_time_utc} (型: {type(scheduled_time_utc)})") # DEBUGログ追加
            
            if not isinstance(scheduled_time_utc, datetime):
                logger.warning(f"  - scheduled_timeがdatetime型ではありません。スキップします。 Item: {post_item}")
                continue

            # 念のため aware でなければ aware にする
            if scheduled_time_utc.tzinfo is None:
                logger.debug(f"  - scheduled_timeにタイムゾーン情報がないためUTCを付与します。") # DEBUGログ追加
                scheduled_time_utc = scheduled_time_utc.replace(tzinfo=timezone.utc)
            
            logger.debug(f"  - 処理用scheduled_time_utc: {scheduled_time_utc.isoformat()} (タイムゾーン: {scheduled_time_utc.tzinfo})") # DEBUGログ追加

            task_key = (post_item["account_id"], scheduled_time_utc.isoformat())
            if task_key in executed_today_keys:
                logger.debug(f"  - タスク {task_key} は既に実行済みのためスキップします。") # DEBUGログ追加
                continue

            # 現在時刻から見て、実行対象期間内か？
            is_within_range = (time_range_start <= scheduled_time_utc <= time_range_end)
            logger.debug(f"  - 実行期間判定: ({time_range_start.isoformat()} <= {scheduled_time_utc.isoformat()} <= {time_range_end.isoformat()}) = {is_within_range}") # DEBUGログ追加
            
            if is_within_range:
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

    def process_scheduled_posts_for_day(self, date_str: str, process_now: bool = False) -> Tuple[int, int]:
        logger.info(f"{date_str} のスケジュール投稿処理を{( '現在時刻ベースで' if process_now else '予定時刻通りに' )}開始します。")
        
        try:
            target_date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            # スケジュールファイルから対象日のスケジュールを読み込む
            posts_for_today: List[ScheduledPost] = self._load_schedule_from_file(target_date_obj)
            
            if not posts_for_today:
                logger.info(f"{date_str} の投稿予定はありません。")
                if self.summary_notifier: # スケジュールが無くても「予定なし」と通知する
                    logger.info(f"{date_str} のスケジュールサマリーをDiscordに通知します（予定なし）。")
                    self.summary_notifier.send_schedule_summary_notification([], date_str)
                return 0, 0
            
            logger.info(f"{date_str} のスケジュール ({len(posts_for_today)}件) を {self.schedule_file_path} から読み込みました。") # self.post_scheduler.schedule_file_path から self.schedule_file_path に変更

            # === Discordへの日次スケジュールサマリー通知 ===
            if self.summary_notifier:
                logger.info(f"{date_str} のスケジュールサマリーをDiscordに通知します。")
                try:
                    self.summary_notifier.send_schedule_summary_notification(posts_for_today, date_str)
                except Exception as e_notify:
                    logger.error(f"Discordへの日次スケジュールサマリー通知中にエラー: {e_notify}", exc_info=True)
            # === 通知処理ここまで ===

            executed_today_count = 0
            successful_posts_count = 0

            already_executed_ids_for_day = set() # 初期化
            if os.path.exists(self.executed_log_file_path):
                try:
                    with open(self.executed_log_file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                log_entry = json.loads(line)
                                # scheduled_timeはISO文字列なので、日付部分で比較
                                if log_entry.get("success") and log_entry.get("scheduled_time", "").startswith(date_str):
                                    # 実行済みIDの形式を ScheduledPost の scheduled_time (datetime オブジェクトのISO形式) に合わせる
                                    # あるいは、より堅牢な一意のIDを ScheduledPost に持たせることを検討
                                    # ここでは scheduled_time のISO文字列と account_id を使う
                                    already_executed_ids_for_day.add((log_entry["account_id"], log_entry["scheduled_time"]))
                            except json.JSONDecodeError:
                                logger.debug(f"実行ログの不正な行をスキップ: {line.strip()}")
                                continue
                except Exception as e:
                    logger.error(f"実行ログファイルの読み込みエラー（日次処理）: {e}", exc_info=True)


            tasks_to_run = []
            for post in posts_for_today:
                # post['scheduled_time'] は _load_schedule_from_file により datetime オブジェクトのはず
                task_key_for_check = (post['account_id'], post['scheduled_time'].isoformat())

                if task_key_for_check in already_executed_ids_for_day:
                    logger.info(f"タスク {post['account_id']} @ {post['scheduled_time'].isoformat()} は既に実行済みのためスキップします。")
                    continue

                scheduled_time_utc = post['scheduled_time'] # 既にUTCのdatetimeのはず
                # 念のためタイムゾーン確認と付与 (load_schedule_from_file で付与されているはず)
                if scheduled_time_utc.tzinfo is None:
                    scheduled_time_utc = scheduled_time_utc.replace(tzinfo=timezone.utc)

                now_utc = datetime.now(timezone.utc)

                if process_now or scheduled_time_utc <= now_utc:
                    tasks_to_run.append(post)
                else:
                    logger.info(f"タスク {post['account_id']} @ {scheduled_time_utc.strftime('%H:%M:%S UTC')} はまだ実行時刻ではありません。")
            
            logger.info(f"実行対象タスク (日次): {[(t['account_id'], t['scheduled_time'].isoformat()) for t in tasks_to_run]}")

            for scheduled_post_data in tasks_to_run:
                executed_today_count += 1
                # scheduled_post_data は ScheduledPost 型なので、そのまま渡せる
                returned_tweet_id: Optional[str] = None
                success_flag: bool = False
                error_reason_val: Optional[str] = "不明な実行エラー"
                try:
                    returned_tweet_id = self.post_executor.execute_post(scheduled_post_data)
                    if returned_tweet_id:
                        successful_posts_count += 1
                        success_flag = True
                        error_reason_val = None
                    else:
                        error_reason_val = "投稿実行条件未達 (記事なし等) またはAPIエラー (Executorログ参照)"
                        logger.warning(f"タスク ({scheduled_post_data['account_id']}, {scheduled_post_data['scheduled_time'].isoformat()}) は実行されましたが、投稿には至りませんでした (Tweet IDなし)。")
                except Exception as e:
                    logger.error(f"タスク ({scheduled_post_data['account_id']}, {scheduled_post_data['scheduled_time'].isoformat()}) の日次実行中に予期せぬエラー: {e}", exc_info=True)
                    error_reason_val = str(e)
                    # success_flag は False のまま
                finally:
                    # _log_executed_post は ScheduledPost 型を期待する
                    self._log_executed_post(scheduled_post_data, success_flag, tweet_id=returned_tweet_id, error_reason=error_reason_val)
            
            logger.info(f"{date_str} のスケジュール投稿処理完了。実行対象 {len(tasks_to_run)}件中、成功 {successful_posts_count}件。")
            return len(tasks_to_run), successful_posts_count

        except Exception as e:
            logger.error(f"{date_str} のスケジュール投稿処理中に予期せぬエラー: {e}", exc_info=True)
            return 0, 0 # エラー時は実行数0、成功数0として返す

    def notify_workflow_completion(self, date_str: str, total_processed: int, total_successful: int):
        # ... (既存のワークフロー完了通知メソッド)
        # こちらは post_executor が個別の成功/失敗通知を行うので、重複を避けるか、サマリーに特化するか検討
        # 現状は main.py から呼び出されている
        if not self.config.get("auto_post_bot.discord_notification.enabled", False):
            return
        
        # この通知は post_executor とは別に、WorkflowManager が完了を通知する想定
        # ここでは summary_notifier を使う (post_executorが使うものと同じインスタンスでよいか、設定を分けるか)
        if self.summary_notifier: # summary_notifierが初期化されていれば使う
            title = f"⚙️ {date_str} バッチ処理完了"
            description = f"処理対象タスク数: {total_processed}\n成功タスク数: {total_successful}"
            color = 0x0000FF # 青色
            if total_processed > 0 and total_successful < total_processed:
                color = 0xFFA500 # オレンジ (一部失敗)
            elif total_processed > 0 and total_successful == 0:
                color = 0xFF0000 # 赤 (全失敗)
            elif total_processed == 0:
                color = 0x808080 # グレー (実行対象なし)
            
            self.summary_notifier.send_simple_notification(title, description, color=color)
        else:
            logger.info("Discord通知が無効か、またはsummary_notifierが初期化されていないため、ワークフロー完了通知をスキップします。")

# ... (もし __main__ ブロックがあれば、ConfigインスタンスをWorkflowManagerに渡すように修正) 