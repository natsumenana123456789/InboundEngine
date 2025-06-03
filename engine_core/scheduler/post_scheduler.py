import logging
import random
from datetime import datetime, time, timedelta, date, timezone
from typing import List, Dict, Optional, Tuple, TypedDict

# このモジュールがengine_coreパッケージ内にあることを想定してConfigをインポート
from ..config import Config # 親パッケージのconfigモジュールからインポート

logger = logging.getLogger(__name__)

class ScheduledPost(TypedDict):
    account_id: str
    scheduled_time: datetime
    worksheet_name: Optional[str] # どのワークシートから取得するかの情報も追加

class PostScheduler:
    def __init__(self,
                 config: Config,
                 start_hour: int,
                 end_hour: int,
                 min_interval_minutes: int,
                 posts_per_account_schedule: Dict[str, int],
                 schedule_file_path: str, # schedule_file_path を追加
                 max_posts_per_hour_globally: Optional[int] = None): # オプション引数として追加
        self.config = config # Config全体はアカウント情報取得などに必要なので保持
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.min_interval_minutes = min_interval_minutes
        self.posts_per_account_schedule = posts_per_account_schedule
        self.schedule_file_path = schedule_file_path # ファイルパスをインスタンス変数として保持
        self.max_posts_per_hour_globally = max_posts_per_hour_globally

        if not self.posts_per_account_schedule:
            logger.warning("アカウントごとの投稿数設定が空です。")
        
        logger.info(f"PostScheduler初期化完了: 開始={self.start_hour}時, 終了={self.end_hour}時, 最短間隔={self.min_interval_minutes}分, ScheduleFile={self.schedule_file_path}")
        logger.debug(f"アカウント毎の投稿数: {self.posts_per_account_schedule}")

    def _is_within_posting_hours(self, dt_time: time) -> bool:  # 引数を time オブジェクトに変更
        """指定された時刻が投稿可能時間帯（時のみ考慮）であるかを確認する"""
        return self.start_hour <= dt_time.hour < self.end_hour

    def generate_schedule_for_day(self, target_date: date, execution_trigger_time_utc: Optional[datetime] = None) -> List[ScheduledPost]:
        """
        指定された日付の投稿スケジュールを生成する。
        投稿時刻は系統的に割り当て、最短投稿間隔と時間帯制限を考慮する。
        execution_trigger_time_utc が指定された場合、それ以降の時刻にスケジュールする。
        """
        all_scheduled_posts: List[ScheduledPost] = []
        post_tasks_for_accounts: List[Tuple[str, Optional[str]]] = []

        active_twitter_accounts = self.config.get_active_twitter_accounts()

        for acc_id, num_posts in self.posts_per_account_schedule.items():
            account_config = next((acc for acc in active_twitter_accounts if acc.get("account_id") == acc_id), None)
            if not account_config:
                logger.warning(f"有効なアカウントリストにID '{acc_id}' の設定が見つかりません。スキップします。")
                continue
            google_sheets_source = account_config.get("google_sheets_source")
            worksheet = None
            if isinstance(google_sheets_source, dict):
                worksheet = google_sheets_source.get("worksheet_name")

            if not worksheet:
                logger.warning(f"アカウントID '{acc_id}' にspreadsheet_worksheetが設定されていません。スキップします。")
                continue

            for _ in range(num_posts):
                post_tasks_for_accounts.append((acc_id, worksheet))
        
        if not post_tasks_for_accounts:
            logger.info(f"{target_date.isoformat()} の投稿タスクはありません。")
            return []

        random.shuffle(post_tasks_for_accounts) # アカウントの処理順序はランダムにする

        # JSTタイムゾーンの定義
        jst = timezone(timedelta(hours=9))

        # 投稿可能時間帯の開始と終了を target_date の JST で定義
        # PostSchedulerのstart_hour, end_hourはJST基準とする
        day_start_jst_naive = time(self.start_hour, 0, 0)
        # day_end_jst_naive は end_hour ちょうどなので、1分前までを有効とするか、比較時に < end_hour とする
        
        # 1時間ごとの投稿数をカウントする辞書 (JSTの時でカウント)
        posts_in_hour_jst: Dict[int, int] = {h: 0 for h in range(24)}
        
        # 最後に配置した投稿の時刻 (UTC aware)
        # アカウントごとではなく、全体の最終投稿時刻を考慮していましたが、
        # 系統的探索では、次に配置する時刻の基準となるため、初期値はNoneでよい
        
        # 系統的探索のための開始カーソル時刻 (UTC aware)
        # target_date の start_hour (JST) から開始
        current_search_time_jst_naive = day_start_jst_naive
        current_search_dt_utc = datetime.combine(target_date, current_search_time_jst_naive, tzinfo=jst).astimezone(timezone.utc)

        if execution_trigger_time_utc:
            # 実行トリガー時刻が指定されている場合、それ以降から探索開始
            # ただし、常に JST start_hour は尊重する
            if execution_trigger_time_utc > current_search_dt_utc:
                current_search_dt_utc = execution_trigger_time_utc

        logger.info(f"スケジュール配置探索開始時刻 (UTC): {current_search_dt_utc.isoformat()}, (JST): {current_search_dt_utc.astimezone(jst).isoformat()}")

        for account_id, worksheet_name in post_tasks_for_accounts:
            placed_post = False
            # 投稿可能時間帯 (JST end_hour-1 の 59分まで) を超えるまで探索
            # ループの安全停止のため、最大試行回数も設ける (例: 1日の分数 / 間隔)
            max_iterations = (self.end_hour - self.start_hour) * 60 
            
            for i in range(max_iterations):
                potential_post_time_utc = current_search_dt_utc + timedelta(minutes=i) # 1分ずつ進める
                potential_post_time_jst = potential_post_time_utc.astimezone(jst)
                potential_post_time_jst_naive_time = potential_post_time_jst.time()

                # 0. そもそも target_date の範囲か (日付が変わってないか)
                if potential_post_time_jst.date() != target_date:
                    # logger.debug(f"探索が日付 {target_date} を超えました。アカウント {account_id} の配置を終了します。")
                    break # このアカウントの配置はここまで

                # 1. JSTでの投稿時間帯内か？ (start_hour <= hour < end_hour)
                if not self._is_within_posting_hours(potential_post_time_jst_naive_time):
                    if potential_post_time_jst_naive_time.hour >= self.end_hour:
                        # logger.debug(f"探索がJST {self.end_hour}時を超えました。アカウント {account_id} の配置を終了します。")
                        break # このアカウントの配置はここまで (次の日の時間帯に入ってしまうので)
                    continue # まだ開始時刻前ならスキップして探索を続ける

                # 2. (オプション) 1時間あたりの最大投稿数グローバル制限 (JSTの時でカウント) をクリアしているか？
                if self.max_posts_per_hour_globally is not None:
                    if posts_in_hour_jst.get(potential_post_time_jst.hour, 0) >= self.max_posts_per_hour_globally:
                        continue

                # 3. 他の既にスケジュールされた投稿との間隔をクリアしているか？
                too_close = False
                for scheduled_item in all_scheduled_posts: # all_scheduled_posts にはUTC awareな時刻が格納
                    if abs((potential_post_time_utc - scheduled_item['scheduled_time']).total_seconds()) < self.min_interval_minutes * 60:
                        too_close = True
                        break
                if too_close:
                    continue
                
                # 全ての条件をクリア
                new_post: ScheduledPost = {
                    "account_id": account_id,
                    "scheduled_time": potential_post_time_utc, # UTC aware datetime
                    "worksheet_name": worksheet_name
                }
                all_scheduled_posts.append(new_post)
                posts_in_hour_jst[potential_post_time_jst.hour] = posts_in_hour_jst.get(potential_post_time_jst.hour, 0) + 1
                
                # 次の投稿の探索開始時刻を、今の投稿時刻 + 最低間隔 に更新
                current_search_dt_utc = potential_post_time_utc + timedelta(minutes=self.min_interval_minutes)
                placed_post = True
                logger.debug(f"配置成功: {account_id} at {potential_post_time_jst.strftime('%Y-%m-%d %H:%M:%S %Z')} (UTC: {potential_post_time_utc.isoformat()})")
                break # このタスクの配置成功、次のタスクへ
            
            if not placed_post:
                logger.warning(f"アカウント '{account_id}' の投稿を {target_date.isoformat()} のスケジュールに配置できませんでした（適切な空きスロットが見つかりませんでした）。")

        all_scheduled_posts.sort(key=lambda x: x["scheduled_time"])
        logger.info(f"{target_date.isoformat()} のスケジュール生成完了。合計 {len(all_scheduled_posts)} 件。")
        jst = timezone(timedelta(hours=9)) # 再度定義 (スコープのため)
        for post_item in all_scheduled_posts: # デバッグログはJST表示
            logger.debug(f"  - {post_item['account_id']} @ {post_item['scheduled_time'].astimezone(jst).strftime('%Y-%m-%d %H:%M:%S %Z')} (Sheet: {post_item['worksheet_name']})")
        return all_scheduled_posts

if __name__ == '__main__':
    import os

    logging.basicConfig(level=logging.DEBUG)
    logger.info("PostSchedulerのテストを開始します。")

    try:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_file_path = os.path.join(project_root, "config/config.yml")
        
        config_instance = Config(config_path=config_file_path)
        
        # PostScheduler の初期化を新しい __init__ に合わせて変更
        schedule_conf = config_instance.get_schedule_config()
        if not schedule_conf:
            raise ValueError("config.ymlからschedule_settingsが見つかりません。")

        posts_schedule = config_instance.get_posts_per_account_schedule()
        if not posts_schedule:
             posts_schedule = {} # テスト用に空辞書を許容 (実際はエラーかデフォルトが良い)
             logger.warning("テスト用に posts_per_account_schedule が空ですが続行します。")


        # schedule_file_path を config から取得 (テストなので通常のパスを使用)
        schedule_file = schedule_conf.get("schedule_file", "logs/schedule.txt")

        scheduler = PostScheduler(
            config=config_instance,
            start_hour=schedule_conf.get("start_hour", 9),
            end_hour=schedule_conf.get("end_hour", 21),
            min_interval_minutes=schedule_conf.get("min_interval_minutes", 30),
            posts_per_account_schedule=posts_schedule,
            schedule_file_path=schedule_file, # ここで渡す
            max_posts_per_hour_globally=schedule_conf.get("max_posts_per_hour_globally")
        )

        today = date.today()
        logger.info(f"{today.isoformat()} のスケジュールを生成します...")
        generated_schedule = scheduler.generate_schedule_for_day(today)

        if generated_schedule:
            logger.info(f"--- {today.isoformat()} 生成スケジュール ---")
            for item in generated_schedule:
                print(f"Account: {item['account_id']}, Time: {item['scheduled_time'].strftime('%H:%M')}, Worksheet: {item['worksheet_name']}")
        else:
            logger.info(f"{today.isoformat()} にスケジュールされた投稿はありません。")
        
        tomorrow = today + timedelta(days=1)
        logger.info(f"{tomorrow.isoformat()} のスケジュールを生成します...")
        generated_schedule_tomorrow = scheduler.generate_schedule_for_day(tomorrow)
        if generated_schedule_tomorrow:
            logger.info(f"--- {tomorrow.isoformat()} 生成スケジュール ---")
            for item in generated_schedule_tomorrow:
                print(f"Account: {item['account_id']}, Time: {item['scheduled_time'].strftime('%H:%M')}, Worksheet: {item['worksheet_name']}")
        else:
            logger.info(f"{tomorrow.isoformat()} にスケジュールされた投稿はありません。")


    except ValueError as ve:
        logger.error(f"設定エラー: {ve}")
    except ImportError as ie:
        logger.error(f"インポートエラー: {ie}. engine_coreのルートからテストを実行しているか確認してください。")
    except Exception as e:
        logger.error(f"PostSchedulerのテスト中に予期せぬエラー: {e}", exc_info=True) 