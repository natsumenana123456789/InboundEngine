from datetime import datetime, time, timedelta

class PostScheduler:
    """投稿スケジューラ"""

    def __init__(
        self,
        start_hour: int = 10,
        end_hour: int = 22,
        min_interval_minutes: int = 5,
        max_posts_per_day: int = 5
    ):
        """
        Args:
            start_hour: 投稿開始時刻（時）
            end_hour: 投稿終了時刻（時）
            min_interval_minutes: 最小投稿間隔（分）
            max_posts_per_day: 1日の最大投稿回数
        """
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.min_interval_minutes = min_interval_minutes
        self.max_posts_per_day = max_posts_per_day

    def is_posting_time(self, current_time: datetime = None) -> bool:
        """現在時刻が投稿可能な時間帯かどうかを判定

        Args:
            current_time: 判定する時刻（Noneの場合は現在時刻）

        Returns:
            bool: 投稿可能な時間帯の場合はTrue
        """
        if current_time is None:
            current_time = datetime.now()

        current_hour = current_time.hour
        return self.start_hour <= current_hour < self.end_hour

    def can_post_within_interval(
        self,
        last_post_time: datetime,
        current_time: datetime = None
    ) -> bool:
        """前回の投稿から最小投稿間隔が経過しているかを判定

        Args:
            last_post_time: 前回の投稿時刻
            current_time: 判定する時刻（Noneの場合は現在時刻）

        Returns:
            bool: 最小投稿間隔が経過している場合はTrue
        """
        if current_time is None:
            current_time = datetime.now()

        elapsed = current_time - last_post_time
        return elapsed.total_seconds() >= self.min_interval_minutes * 60

    def check_daily_post_limit(self, daily_posts: int) -> bool:
        """1日の投稿回数が上限を超えていないかを判定

        Args:
            daily_posts: その日の投稿回数

        Returns:
            bool: 投稿回数が上限未満の場合はTrue
        """
        return daily_posts < self.max_posts_per_day

    def calculate_next_post_time(self, current_time: datetime = None) -> datetime:
        """次回の投稿可能時刻を計算

        Args:
            current_time: 基準時刻（Noneの場合は現在時刻）

        Returns:
            datetime: 次回の投稿可能時刻
        """
        if current_time is None:
            current_time = datetime.now()

        # 最小投稿間隔後の時刻
        next_time = current_time + timedelta(minutes=self.min_interval_minutes)

        # 営業時間外の場合は翌日の開始時刻
        if next_time.hour >= self.end_hour:
            next_time = next_time.replace(
                hour=self.start_hour,
                minute=0,
                second=0,
                microsecond=0
            )
            next_time += timedelta(days=1)
        elif next_time.hour < self.start_hour:
            next_time = next_time.replace(
                hour=self.start_hour,
                minute=0,
                second=0,
                microsecond=0
            )

        return next_time

    def validate_post_schedule(
        self,
        current_time: datetime,
        last_post_time: datetime,
        daily_posts: int
    ) -> bool:
        """投稿スケジュールが全ての条件を満たしているかを検証

        Args:
            current_time: 現在時刻
            last_post_time: 前回の投稿時刻
            daily_posts: その日の投稿回数

        Returns:
            bool: 全ての条件を満たしている場合はTrue
        """
        return (
            self.is_posting_time(current_time) and
            self.can_post_within_interval(last_post_time, current_time) and
            self.check_daily_post_limit(daily_posts)
        )

    def get_next_available_time(self, last_post_time: datetime) -> datetime:
        """次回の投稿可能時刻を取得

        Args:
            last_post_time: 前回の投稿時刻

        Returns:
            datetime: 次回の投稿可能時刻
        """
        current_time = datetime.now()
        
        # 最小投稿間隔を考慮した次回時刻
        next_time = max(
            current_time,
            last_post_time + timedelta(minutes=self.min_interval_minutes)
        )

        # 営業時間外の場合は翌日の開始時刻
        if not self.is_posting_time(next_time):
            next_time = next_time.replace(
                hour=self.start_hour,
                minute=0,
                second=0,
                microsecond=0
            )
            if next_time < current_time:
                next_time += timedelta(days=1)

        return next_time 