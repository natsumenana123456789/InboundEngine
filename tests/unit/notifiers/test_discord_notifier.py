import pytest
import responses
import requests
import json
from datetime import datetime
from src.notifiers.discord_notifier import DiscordNotifier

@pytest.fixture
def notifier():
    return DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")

@pytest.fixture
def mock_response():
    return {
        "status_code": 204,
        "headers": {}
    }

class TestDiscordNotifier:
    """Discord通知機能のテスト"""

    @responses.activate
    def test_send_message_success(self, notifier, mock_response):
        """通常メッセージ送信の成功テスト"""
        responses.add(
            responses.POST,
            "https://discord.com/api/webhooks/test",
            status=204
        )
        
        result = notifier.send_message("テストメッセージ")
        assert result is True
        
        assert len(responses.calls) == 1
        assert json.loads(responses.calls[0].request.body) == {
            "content": "テストメッセージ"
        }

    @responses.activate
    def test_send_embed_success(self, notifier):
        """エンベッドメッセージ送信の成功テスト"""
        responses.add(
            responses.POST,
            "https://discord.com/api/webhooks/test",
            status=204
        )
        
        fields = {"テスト": "値", "キー": "バリュー"}
        result = notifier.send_embed(
            title="テストタイトル",
            description="テスト説明",
            fields=fields,
            color="#ff0000"
        )
        assert result is True
        
        request_body = json.loads(responses.calls[0].request.body)
        embed = request_body["embeds"][0]
        assert embed["title"] == "テストタイトル"
        assert embed["description"] == "テスト説明"
        assert embed["color"] == int("ff0000", 16)
        assert len(embed["fields"]) == 2

    def test_validate_webhook_url(self, notifier):
        """Webhook URLの検証テスト"""
        assert notifier._validate_webhook_url() is True
        
        invalid_notifier = DiscordNotifier("https://invalid.url")
        assert invalid_notifier._validate_webhook_url() is False

    @responses.activate
    def test_rate_limit_handling(self, notifier):
        """レート制限処理のテスト"""
        # 最初のリクエストでレート制限
        responses.add(
            responses.POST,
            "https://discord.com/api/webhooks/test",
            status=429,
            headers={"Retry-After": "2"}
        )
        
        # 2回目のリクエストで成功
        responses.add(
            responses.POST,
            "https://discord.com/api/webhooks/test",
            status=204
        )
        
        result = notifier.send_message("テストメッセージ")
        assert result is True
        assert len(responses.calls) == 2

    @responses.activate
    def test_network_error_retry(self, notifier):
        """ネットワークエラーのリトライテスト"""
        # 2回失敗
        responses.add(
            responses.POST,
            "https://discord.com/api/webhooks/test",
            body=requests.exceptions.RequestException()
        )
        responses.add(
            responses.POST,
            "https://discord.com/api/webhooks/test",
            body=requests.exceptions.RequestException()
        )
        
        # 3回目で成功
        responses.add(
            responses.POST,
            "https://discord.com/api/webhooks/test",
            status=204
        )
        
        result = notifier.send_message("テストメッセージ")
        assert result is True
        assert len(responses.calls) == 3

    def test_message_length_validation(self, notifier):
        """メッセージ長のバリデーションテスト"""
        long_message = "a" * 2001
        with pytest.raises(ValueError) as exc_info:
            notifier.send_message(long_message)
        assert "VALIDATION_ERROR" in str(exc_info.value)

    @responses.activate
    def test_send_error_message(self, notifier):
        """エラーメッセージ送信のテスト"""
        responses.add(
            responses.POST,
            "https://discord.com/api/webhooks/test",
            status=204
        )
        
        error_details = {
            "エラーコード": "E001",
            "発生場所": "テスト関数"
        }
        
        result = notifier.send_error(
            "テストエラーが発生しました",
            error_details
        )
        assert result is True
        
        request_body = json.loads(responses.calls[0].request.body)
        embed = request_body["embeds"][0]
        assert embed["title"] == "エラー発生"
        assert embed["description"] == "テストエラーが発生しました"
        assert embed["color"] == int("ff0000", 16)
        assert len(embed["fields"]) == 2 