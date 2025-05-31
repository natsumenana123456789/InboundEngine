import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time
import responses
from src.scheduler import PostScheduler
from src.notifiers.discord_notifier import DiscordNotifier

class TestPostWorkflowIntegration:
    """投稿ワークフローの統合テスト"""

    @pytest.fixture
    def webhook_url(self):
        """テスト用のWebhook URL"""
        return "https://discord.com/api/webhooks/123456789/test_token"

    @pytest.fixture
    def scheduler(self):
        return PostScheduler(
            start_hour=10,
            end_hour=22,
            min_interval_minutes=5,
            max_posts_per_day=5
        )

    @pytest.fixture
    def notifier(self, webhook_url):
        return DiscordNotifier(webhook_url=webhook_url)

    @pytest.fixture
    def post_data(self):
        """テスト用の投稿データ"""
        return [
            {
                "id": "POST_001",
                "content": "テスト投稿1",
                "media_url": "https://example.com/image1.jpg",
                "category": "テスト"
            },
            {
                "id": "POST_002",
                "content": "テスト投稿2",
                "media_url": None,
                "category": "お知らせ"
            },
            {
                "id": "POST_003",
                "content": "テスト投稿3",
                "media_url": "https://example.com/image2.jpg",
                "category": "テスト"
            }
        ]

    @pytest.fixture(autouse=True)
    def setup_responses(self):
        """全てのテストで自動的にresponsesを有効化"""
        with responses.RequestsMock() as rsps:
            yield rsps

    def test_normal_post_workflow(self, scheduler, notifier, post_data, webhook_url, setup_responses):
        """通常の投稿ワークフローのテスト
        
        シナリオ：
        1. 投稿可能時間内に3件の投稿を実行
        2. 各投稿の間隔は5分以上
        3. 投稿完了後に通知を送信
        """
        # モックレスポンスの設定
        setup_responses.add(
            responses.POST,
            webhook_url,
            json={"id": "test"},
            status=204,
            match=[responses.matchers.urlencoded_params_matcher({})],
        )

        with freeze_time("2024-01-01 10:00:00") as frozen_time:
            last_post_time = None
            daily_posts = 0

            for post in post_data:
                current_time = datetime.now()

                # 投稿可能時間と間隔のチェック
                if last_post_time:
                    next_time = scheduler.get_next_available_time(last_post_time)
                    if next_time > current_time:
                        # 時間を進める
                        frozen_time.tick(delta=next_time - current_time)
                        current_time = datetime.now()

                # スケジュール検証
                if last_post_time:
                    assert scheduler.validate_post_schedule(
                        current_time,
                        last_post_time,
                        daily_posts
                    )

                # 投稿実行（モック）
                daily_posts += 1
                last_post_time = current_time

                # 投稿通知
                result = notifier.send_embed(
                    title="投稿完了",
                    description=f"ID: {post['id']}\n内容: {post['content']}",
                    fields={
                        "カテゴリ": post["category"],
                        "メディア": "あり" if post["media_url"] else "なし"
                    },
                    color="#00ff00"
                )
                assert result is True

                # 次の投稿のために5分進める
                frozen_time.tick(delta=timedelta(minutes=5))

    def test_post_limit_handling(self, scheduler, notifier, post_data, webhook_url, setup_responses):
        """投稿制限のハンドリングテスト
        
        シナリオ：
        1. 1日の投稿上限（5件）に達する
        2. 上限到達後の投稿をスキップ
        3. 翌日に投稿を再開
        """
        # モックレスポンスの設定
        setup_responses.add(
            responses.POST,
            webhook_url,
            json={"id": "test"},
            status=204,
            match=[responses.matchers.urlencoded_params_matcher({})],
        )

        with freeze_time("2024-01-01 10:00:00") as frozen_time:
            last_post_time = None
            daily_posts = 0

            # 1日目：上限まで投稿
            for _ in range(5):
                current_time = datetime.now()

                if last_post_time:
                    next_time = scheduler.get_next_available_time(last_post_time)
                    if next_time > current_time:
                        frozen_time.tick(delta=next_time - current_time)
                        current_time = datetime.now()

                # 投稿実行
                daily_posts += 1
                last_post_time = current_time

                # 次の投稿のために5分進める
                frozen_time.tick(delta=timedelta(minutes=5))

            # 上限到達の確認
            assert not scheduler.check_daily_post_limit(daily_posts)

            # 上限到達通知
            result = notifier.send_embed(
                title="投稿上限到達",
                description="本日の投稿可能回数に達しました",
                fields={
                    "投稿回数": str(daily_posts),
                    "次回投稿可能時刻": "翌日10:00"
                },
                color="#ffff00"
            )
            assert result is True

            # 翌日に進む
            frozen_time.tick(delta=timedelta(hours=24))
            
            # 翌日の投稿再開
            daily_posts = 0
            current_time = datetime.now()
            assert scheduler.check_daily_post_limit(daily_posts)

    def test_error_recovery_workflow(self, scheduler, notifier, post_data, webhook_url, setup_responses):
        """エラーからの復旧ワークフローのテスト
        
        シナリオ：
        1. 投稿中にエラーが発生
        2. エラー通知を送信
        3. リトライ後に正常投稿
        """
        # モックレスポンスの設定
        setup_responses.add(
            responses.POST,
            webhook_url,
            json={"id": "test"},
            status=204,
            match=[responses.matchers.urlencoded_params_matcher({})],
        )

        with freeze_time("2024-01-01 10:00:00") as frozen_time:
            # エラー発生時の通知
            error_time = datetime.now()
            result = notifier.send_error(
                "投稿処理中にエラーが発生しました",
                {
                    "投稿ID": post_data[0]["id"],
                    "発生時刻": error_time.strftime("%H:%M:%S"),
                    "エラー内容": "ネットワークエラー"
                }
            )
            assert result is True

            # リトライ待機（5分）
            frozen_time.tick(delta=timedelta(minutes=5))

            # リトライ開始通知
            result = notifier.send_embed(
                title="リトライ開始",
                description=f"投稿ID: {post_data[0]['id']}の再投稿を試みます",
                fields={
                    "待機時間": "5分",
                    "リトライ回数": "1回目"
                },
                color="#ffff00"
            )
            assert result is True

            # 投稿成功
            current_time = datetime.now()
            result = notifier.send_embed(
                title="リトライ成功",
                description=f"投稿ID: {post_data[0]['id']}の再投稿に成功しました",
                fields={
                    "リトライ回数": "1回",
                    "経過時間": "5分"
                },
                color="#00ff00"
            )
            assert result is True

    def test_schedule_adjustment_workflow(self, scheduler, notifier, webhook_url, setup_responses):
        """スケジュール調整ワークフローのテスト
        
        シナリオ：
        1. 営業時間外の投稿をスケジュール
        2. 次回の投稿可能時刻を計算
        3. スケジュール変更を通知
        """
        # モックレスポンスの設定
        setup_responses.add(
            responses.POST,
            webhook_url,
            json={"id": "test"},
            status=204,
            match=[responses.matchers.urlencoded_params_matcher({})],
        )

        with freeze_time("2024-01-01 22:30:00") as frozen_time:
            current_time = datetime.now()

            # 営業時間外の確認
            assert not scheduler.is_posting_time(current_time)

            # 次回投稿可能時刻の計算
            next_time = scheduler.calculate_next_post_time(current_time)
            assert next_time.hour == 10  # 翌日10:00
            assert next_time.day == 2    # 翌日

            # スケジュール変更通知
            result = notifier.send_embed(
                title="投稿スケジュール調整",
                description="営業時間外のため、投稿を延期します",
                fields={
                    "現在時刻": current_time.strftime("%H:%M"),
                    "次回投稿予定": next_time.strftime("%Y-%m-%d %H:%M")
                },
                color="#ffff00"
            )
            assert result is True 