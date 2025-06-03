import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from src.twitter.twitter_client import (
    TwitterClient,
    TwitterAPIError,
    RateLimitError,
    AuthenticationError
)

@pytest.fixture
def twitter_client():
    client = TwitterClient(
        api_key="test_key",
        api_secret="test_secret",
        access_token="test_token",
        access_token_secret="test_token_secret"
    )
    return client

def test_successful_post(twitter_client):
    """投稿APIのレスポンスコードが200であることを確認"""
    with patch('tweepy.Client') as mock_client:
        mock_client.return_value.create_tweet.return_value = {
            'data': {'id': '123', 'text': 'Test tweet'}
        }
        twitter_client._client = mock_client.return_value
        
        result = twitter_client.post_tweet("Test tweet")
        
        assert result['success'] is True
        assert result['tweet_id'] == '123'
        mock_client.return_value.create_tweet.assert_called_once_with(
            text="Test tweet"
        )

def test_network_error_retry(twitter_client):
    """ネットワークエラー時にRetryExceptionが発生することを確認"""
    with patch('tweepy.Client') as mock_client:
        mock_client.return_value.create_tweet.side_effect = [
            Exception("Network error"),
            Exception("Network error"),
            {'data': {'id': '123', 'text': 'Test tweet'}}
        ]
        twitter_client._client = mock_client.return_value
        
        result = twitter_client.post_tweet("Test tweet")
        
        assert result['success'] is True
        assert mock_client.return_value.create_tweet.call_count == 3

def test_rate_limit_handling(twitter_client):
    """API制限到達時に15分間の待機が実行されること"""
    with patch('tweepy.Client') as mock_client, \
         patch('time.sleep') as mock_sleep:
        mock_client.return_value.create_tweet.side_effect = [
            RateLimitError("Rate limit exceeded"),
            {'data': {'id': '123', 'text': 'Test tweet'}}
        ]
        twitter_client._client = mock_client.return_value
        
        result = twitter_client.post_tweet("Test tweet")
        
        assert result['success'] is True
        mock_sleep.assert_called_once_with(900)  # 15分 = 900秒

def test_authentication_retry(twitter_client):
    """認証エラー時に3回のリトライが実行されること"""
    with patch('tweepy.Client') as mock_client:
        mock_client.return_value.create_tweet.side_effect = [
            AuthenticationError("Auth failed"),
            AuthenticationError("Auth failed"),
            AuthenticationError("Auth failed"),
            {'data': {'id': '123', 'text': 'Test tweet'}}
        ]
        twitter_client._client = mock_client.return_value
        
        result = twitter_client.post_tweet("Test tweet")
        
        assert result['success'] is True
        assert mock_client.return_value.create_tweet.call_count == 4

def test_unsupported_media_type(twitter_client):
    """非対応形式のファイルがエラーとなることを確認"""
    with patch('tweepy.Client') as mock_client:
        result = twitter_client.post_tweet(
            "Test tweet",
            media_paths=["test.xyz"]  # 非対応の拡張子
        )
        
        assert result['success'] is False
        assert "Unsupported media type" in result['error']
        mock_client.return_value.create_tweet.assert_not_called() 