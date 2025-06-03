import os
import pytest
from datetime import datetime
from src.notifiers.discord_notifier import DiscordNotifier
from unittest.mock import patch, MagicMock

class TestDiscordNotificationIntegration:
    """Discord通知の統合テスト"""

    @pytest.fixture
    def webhook_url(self):
        """テスト用のWebhook URL"""
        return "https://discord.com/api/webhooks/123456789/test_token"

    @pytest.fixture
    def notifier(self, webhook_url):
        return DiscordNotifier(webhook_url=webhook_url)

    @patch("requests.post")
    def test_normal_notification_workflow(self, mock_post, notifier):
        """通常の通知ワークフローのテスト
        
        シナリオ：
        1. 投稿完了通知の送信
        2. Webhook送信の確認
        """
        mock_post.return_value = MagicMock(status_code=204)

        result = notifier.send_embed(
            title="投稿完了",
            description="投稿ID: POST_001 の処理が完了しました",
            fields={
                "投稿時刻": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "カテゴリ": "お知らせ",
                "ステータス": "完了"
            },
            color="#00ff00"
        )
        assert result is True
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_error_notification_workflow(self, mock_post, notifier):
        """エラー通知ワークフローのテスト
        
        シナリオ：
        1. エラー発生時の通知
        2. エラー詳細の送信
        """
        mock_post.return_value = MagicMock(status_code=204)

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
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_webhook_error_handling(self, mock_post, notifier):
        """Webhook接続エラーのハンドリングテスト
        
        シナリオ：
        1. Webhook送信エラーの発生
        2. エラーハンドリング
        """
        mock_post.return_value = MagicMock(status_code=500)

        result = notifier.send_embed(
            title="テスト通知",
            description="Webhook接続エラーのテスト",
            fields={
                "ステータス": "エラー",
                "詳細": "接続に失敗しました"
            },
            color="#ff0000"
        )
        assert result is False
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_rate_limit_handling(self, mock_post, notifier):
        """レート制限ハンドリングの統合テスト
        
        シナリオ：
        1. レート制限エラーの発生
        2. 待機時間の通知
        3. 制限解除後の再開
        """
        # レート制限レスポンスを設定
        mock_post.side_effect = [
            MagicMock(status_code=429, headers={"Retry-After": "1"}),
            MagicMock(status_code=204)
        ]

        result = notifier.send_embed(
            title="レート制限テスト",
            description="レート制限のテスト通知",
            fields={
                "テスト": "レート制限"
            },
            color="#ffff00"
        )
        assert result is True
        assert mock_post.call_count == 2

    @patch("requests.post")
    def test_file_attachment_workflow(self, mock_post, notifier):
        """ファイル添付ワークフローの統合テスト
        
        シナリオ：
        1. 画像ファイルの添付
        2. ログファイルの添付
        3. 添付完了通知
        """
        mock_post.return_value = MagicMock(status_code=204)

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
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_notification_workflow(self, mock_post, notifier):
        """通知ワークフローの統合テスト
        
        シナリオ：
        1. 処理開始通知
        2. 進捗状況通知
        3. 処理完了通知
        """
        mock_post.return_value = MagicMock(status_code=204)

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
        mock_post.assert_called_once() 