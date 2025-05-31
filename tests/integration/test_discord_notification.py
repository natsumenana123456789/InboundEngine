import os
import pytest
import responses
from datetime import datetime
from src.notifiers.discord_notifier import DiscordNotifier

class TestDiscordNotificationIntegration:
    """Discord通知機能の統合テスト"""

    @pytest.fixture
    def webhook_url(self):
        """テスト用のWebhook URL"""
        return "https://discord.com/api/webhooks/123456789/test_token"

    @pytest.fixture
    def notifier(self, webhook_url):
        return DiscordNotifier(webhook_url=webhook_url)

    @pytest.fixture(autouse=True)
    def setup_responses(self):
        """全てのテストで自動的にresponsesを有効化"""
        with responses.RequestsMock() as rsps:
            yield rsps

    def test_notification_workflow(self, notifier, webhook_url, setup_responses):
        """通知ワークフローの統合テスト
        
        シナリオ：
        1. 処理開始通知
        2. 進捗状況通知
        3. 処理完了通知
        """
        # モックレスポンスの設定
        setup_responses.add(
            responses.POST,
            webhook_url,
            json={"id": "test"},
            status=204,
            match=[responses.matchers.urlencoded_params_matcher({})],
        )

        # 処理開始通知
        result = notifier.send_embed(
            title="処理開始",
            description="投稿処理を開始します",
            fields={
                "処理内容": "画像付き投稿",
                "予定件数": "3件"
            },
            color="#0000ff"
        )
        assert result is True

        # 進捗状況通知
        for i in range(1, 4):
            result = notifier.send_embed(
                title="処理進捗",
                description=f"{i}件目の処理が完了しました",
                fields={
                    "進捗": f"{i}/3",
                    "残り": f"{3-i}件"
                },
                color="#00ff00"
            )
            assert result is True

        # 処理完了通知
        result = notifier.send_embed(
            title="処理完了",
            description="全ての処理が完了しました",
            fields={
                "処理件数": "3件",
                "所要時間": "15分"
            },
            color="#00ff00"
        )
        assert result is True

    def test_error_notification_workflow(self, notifier, webhook_url, setup_responses):
        """エラー通知ワークフローの統合テスト
        
        シナリオ：
        1. エラー発生通知
        2. リトライ通知
        3. 復旧完了通知
        """
        # モックレスポンスの設定
        setup_responses.add(
            responses.POST,
            webhook_url,
            json={"id": "test"},
            status=204,
            match=[responses.matchers.urlencoded_params_matcher({})],
        )

        # エラー発生通知
        error_time = datetime.now()
        result = notifier.send_error(
            "画像処理中にエラーが発生しました",
            {
                "エラー種別": "IOError",
                "発生時刻": error_time.strftime("%H:%M:%S"),
                "対象ファイル": "image.jpg"
            }
        )
        assert result is True

        # リトライ通知
        result = notifier.send_embed(
            title="リトライ実行",
            description="画像処理を再試行します",
            fields={
                "リトライ回数": "1回目",
                "対象ファイル": "image.jpg"
            },
            color="#ffff00"
        )
        assert result is True

        # 復旧完了通知
        result = notifier.send_embed(
            title="復旧完了",
            description="エラーから復旧しました",
            fields={
                "復旧時間": "5分",
                "処理結果": "成功"
            },
            color="#00ff00"
        )
        assert result is True

    def test_rate_limit_handling(self, notifier, webhook_url, setup_responses):
        """レート制限ハンドリングの統合テスト
        
        シナリオ：
        1. レート制限エラーの発生
        2. 待機時間の通知
        3. 制限解除後の再開
        """
        # レート制限エラーのモック
        setup_responses.add(
            responses.POST,
            webhook_url,
            json={"message": "You are being rate limited."},
            status=429,
            headers={"Retry-After": "60"},
            match=[responses.matchers.urlencoded_params_matcher({})],
        )

        # 通常レスポンスのモック
        setup_responses.add(
            responses.POST,
            webhook_url,
            json={"id": "test"},
            status=204,
            match=[responses.matchers.urlencoded_params_matcher({})],
        )

        # レート制限通知
        result = notifier.send_embed(
            title="レート制限",
            description="Discord APIのレート制限に達しました",
            fields={
                "待機時間": "60秒",
                "制限解除予定": "1分後"
            },
            color="#ff0000"
        )
        assert result is True

        # 制限解除通知
        result = notifier.send_embed(
            title="制限解除",
            description="レート制限が解除されました",
            fields={
                "待機時間": "60秒",
                "状態": "正常"
            },
            color="#00ff00"
        )
        assert result is True

    def test_file_attachment_workflow(self, notifier, webhook_url, setup_responses):
        """ファイル添付ワークフローの統合テスト
        
        シナリオ：
        1. 画像ファイルの添付
        2. ログファイルの添付
        3. 添付完了通知
        """
        # モックレスポンスの設定
        setup_responses.add(
            responses.POST,
            webhook_url,
            json={"id": "test"},
            status=204,
            match=[responses.matchers.urlencoded_params_matcher({})],
        )

        # 画像添付通知
        result = notifier.send_embed(
            title="画像添付",
            description="画像ファイルを添付します",
            fields={
                "ファイル名": "test.jpg",
                "サイズ": "1.2MB"
            },
            color="#00ff00"
        )
        assert result is True

        # ログ添付通知
        result = notifier.send_embed(
            title="ログ添付",
            description="ログファイルを添付します",
            fields={
                "ファイル名": "error.log",
                "サイズ": "256KB"
            },
            color="#00ff00"
        )
        assert result is True

        # 添付完了通知
        result = notifier.send_embed(
            title="添付完了",
            description="全てのファイルの添付が完了しました",
            fields={
                "添付ファイル数": "2件",
                "総サイズ": "1.45MB"
            },
            color="#00ff00"
        )
        assert result is True 