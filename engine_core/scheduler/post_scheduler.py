import logging
import random
from datetime import datetime, time, timedelta, date
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

    def _is_within_posting_hours(self, dt: datetime) -> bool:
        """指定された日時が投稿可能時間帯（時のみ考慮）であるかを確認する"""
        return self.start_hour <= dt.hour < self.end_hour

    def generate_schedule_for_day(self, target_date: date) -> List[ScheduledPost]:
        """
        指定された日付の投稿スケジュールを生成する。
        投稿時刻はランダム性を持ちつつ、最短投稿間隔と時間帯制限を考慮する。
        """
        all_scheduled_posts: List[ScheduledPost] = []
        # 各アカウントの投稿数を集計するためのリスト
        post_tasks_for_accounts: List[Tuple[str, Optional[str]]] = [] # (account_id, worksheet_name)

        twitter_accounts = self.config.get_twitter_accounts() # 設定から全Twitterアカウント情報を取得

        for acc_id, num_posts in self.posts_per_account_schedule.items():
            # 対応するアカウント設定情報を見つける
            account_config = next((acc for acc in twitter_accounts if acc.get("account_id") == acc_id), None)
            if not account_config:
                logger.warning(f"アカウントID '{acc_id}' の設定がtwitter_accountsセクションに見つかりません。スキップします。")
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

        random.shuffle(post_tasks_for_accounts) # アカウントの投稿順をランダムにする

        # 1日の開始と終了のdatetimeオブジェクト
        day_start_dt = datetime.combine(target_date, time(self.start_hour, 0, 0))
        day_end_dt = datetime.combine(target_date, time(self.end_hour, 0, 0))

        # 1時間ごとの投稿数をカウントする辞書
        posts_in_hour: Dict[int, int] = {h: 0 for h in range(24)}

        last_post_time_overall = None

        for account_id, worksheet_name in post_tasks_for_accounts:
            placed_post = False
            # 試行回数 (無限ループを避けるため)
            for _try_count in range(100): # 100回試行して配置できなければ諦める
                # 投稿時間帯内でランダムな分を選択 (秒は0に丸める)
                # end_hour は含まないので、end_hour -1 までが有効
                random_hour = random.randint(self.start_hour, self.end_hour -1)
                random_minute = random.randint(0, 59)
                potential_post_time = datetime.combine(target_date, time(random_hour, random_minute, 0))

                # 1. 時間帯内か？ (基本的には上のランダム選出で保証されるはずだが念のため)
                if not self._is_within_posting_hours(potential_post_time):
                    continue

                # 2. 全体の最終投稿時刻からの最短間隔をクリアしているか？
                if last_post_time_overall and (potential_post_time - last_post_time_overall) < timedelta(minutes=self.min_interval_minutes):
                    continue
                
                # 3. (オプション) 1時間あたりの最大投稿数グローバル制限をクリアしているか？
                if self.max_posts_per_hour_globally is not None:
                    if posts_in_hour.get(potential_post_time.hour, 0) >= self.max_posts_per_hour_globally:
                        # logger.debug(f"Hour {potential_post_time.hour} has reached global post limit of {self.max_posts_per_hour_globally}. Trying another time.")
                        continue # この時間はもう満杯

                # 4. 他の既にスケジュールされた投稿との間隔をクリアしているか？
                too_close = False
                for scheduled_item in all_scheduled_posts:
                    if abs((potential_post_time - scheduled_item['scheduled_time']).total_seconds()) < self.min_interval_minutes * 60:
                        too_close = True
                        break
                if too_close:
                    continue
                
                # 全ての条件をクリア
                new_post: ScheduledPost = {
                    "account_id": account_id,
                    "scheduled_time": potential_post_time,
                    "worksheet_name": worksheet_name
                }
                all_scheduled_posts.append(new_post)
                last_post_time_overall = potential_post_time # 全体の最終投稿時刻を更新
                posts_in_hour[potential_post_time.hour] = posts_in_hour.get(potential_post_time.hour, 0) + 1
                placed_post = True
                # logger.debug(f"Placed post for {account_id} at {potential_post_time.strftime('%H:%M:%S')}")
                break # このタスクの配置成功、次のタスクへ
            
            if not placed_post:
                logger.warning(f"アカウント '{account_id}' の投稿を {target_date.isoformat()} のスケジュールに配置できませんでした (試行回数超過)。")

        # 時刻順にソートして返す
        all_scheduled_posts.sort(key=lambda x: x["scheduled_time"])
        logger.info(f"{target_date.isoformat()} のスケジュール生成完了。合計 {len(all_scheduled_posts)} 件。")
        for post_item in all_scheduled_posts:
            logger.debug(f"  - {post_item['account_id']} @ {post_item['scheduled_time'].strftime('%Y-%m-%d %H:%M:%S')} (Sheet: {post_item['worksheet_name']})")
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