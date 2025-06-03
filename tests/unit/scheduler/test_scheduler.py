import pytest
from datetime import datetime, time, timedelta
from freezegun import freeze_time
from src.scheduler import PostScheduler

class TestPostScheduler:
    """投稿スケジューラのテスト"""

    @pytest.fixture
    def scheduler(self):
        return PostScheduler(
            start_hour=10,
            end_hour=22,
            min_interval_minutes=5,
            max_posts_per_day=5
        )

    def test_is_posting_time(self, scheduler):
        """投稿可能時間帯のテスト"""
        # 投稿可能時間内（10:00）
        with freeze_time("2024-01-01 10:00:00"):
            assert scheduler.is_posting_time() is True

        # 投稿可能時間内（21:59）
        with freeze_time("2024-01-01 21:59:00"):
            assert scheduler.is_posting_time() is True

        # 投稿可能時間外（9:59）
        with freeze_time("2024-01-01 09:59:00"):
            assert scheduler.is_posting_time() is False

        # 投稿可能時間外（22:00）
        with freeze_time("2024-01-01 22:00:00"):
            assert scheduler.is_posting_time() is False

    def test_can_post_within_interval(self, scheduler):
        """投稿間隔のテスト"""
        now = datetime(2024, 1, 1, 12, 0, 0)
        
        # 前回の投稿から5分経過
        last_post = now - timedelta(minutes=5)
        assert scheduler.can_post_within_interval(last_post, now) is True

        # 前回の投稿から4分59秒経過
        last_post = now - timedelta(minutes=4, seconds=59)
        assert scheduler.can_post_within_interval(last_post, now) is False

    def test_daily_post_limit(self, scheduler):
        """1日の投稿上限のテスト"""
        now = datetime(2024, 1, 1, 12, 0, 0)
        
        # 投稿回数が上限未満
        daily_posts = 4
        assert scheduler.check_daily_post_limit(daily_posts) is True

        # 投稿回数が上限
        daily_posts = 5
        assert scheduler.check_daily_post_limit(daily_posts) is False

        # 投稿回数が上限超過
        daily_posts = 6
        assert scheduler.check_daily_post_limit(daily_posts) is False

    def test_calculate_next_post_time(self, scheduler):
        """次回投稿時刻の計算テスト"""
        now = datetime(2024, 1, 1, 12, 0, 0)
        
        # 通常ケース（5分後）
        next_time = scheduler.calculate_next_post_time(now)
        assert next_time == now + timedelta(minutes=5)

        # 営業時間外から次の営業時間開始まで
        now = datetime(2024, 1, 1, 22, 0, 0)
        next_time = scheduler.calculate_next_post_time(now)
        expected = datetime(2024, 1, 2, 10, 0, 0)
        assert next_time == expected

    def test_validate_post_schedule(self, scheduler):
        """投稿スケジュールの検証テスト"""
        now = datetime(2024, 1, 1, 12, 0, 0)
        last_post = now - timedelta(minutes=10)
        daily_posts = 3

        # 全条件OK
        assert scheduler.validate_post_schedule(now, last_post, daily_posts) is True

        # 投稿間隔不足
        last_post = now - timedelta(minutes=4)
        assert scheduler.validate_post_schedule(now, last_post, daily_posts) is False

        # 投稿回数超過
        last_post = now - timedelta(minutes=10)
        daily_posts = 6
        assert scheduler.validate_post_schedule(now, last_post, daily_posts) is False

        # 営業時間外
        now = datetime(2024, 1, 1, 9, 0, 0)
        last_post = now - timedelta(minutes=10)
        daily_posts = 3
        assert scheduler.validate_post_schedule(now, last_post, daily_posts) is False

    @freeze_time("2024-01-01 12:00:00")
    def test_get_next_available_time(self, scheduler):
        """次回投稿可能時刻の取得テスト"""
        # 通常ケース
        last_post = datetime(2024, 1, 1, 11, 55, 0)
        next_time = scheduler.get_next_available_time(last_post)
        expected = datetime(2024, 1, 1, 12, 0, 0)
        assert next_time == expected

        # 営業時間外から次の営業時間
        last_post = datetime(2024, 1, 1, 22, 0, 0)
        next_time = scheduler.get_next_available_time(last_post)
        expected = datetime(2024, 1, 2, 10, 0, 0)
        assert next_time == expected

        # 日付をまたぐケース（投稿回数リセット）
        with freeze_time("2024-01-01 23:59:59"):
            last_post = datetime(2024, 1, 1, 21, 55, 0)
            next_time = scheduler.get_next_available_time(last_post)
            expected = datetime(2024, 1, 2, 10, 0, 0)
            assert next_time == expected 