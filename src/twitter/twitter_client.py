import os
import time
from datetime import datetime, timedelta
import tweepy
from typing import Dict, List, Optional

class TwitterAPIError(Exception):
    """Twitter APIとの通信中に発生したエラー"""
    pass

class RateLimitError(TwitterAPIError):
    """Twitter APIのレート制限に達した場合のエラー"""
    pass

class AuthenticationError(Exception):
    """認証に失敗した場合のエラー"""
    pass

class TwitterClient:
    SUPPORTED_MEDIA_TYPES = ['.jpg', '.jpeg', '.png', '.gif', '.mp4']
    RATE_LIMIT_WAIT_TIME = 900  # 15分
    MAX_AUTH_RETRIES = 3

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str
    ):
        self._client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )

    def post_tweet(
        self,
        text: str,
        media_paths: Optional[List[str]] = None,
        account_id: Optional[str] = None
    ) -> Dict:
        """ツイートを投稿する"""
        try:
            # メディアのバリデーション
            if media_paths and not self._validate_media_types(media_paths):
                return {
                    'success': False,
                    'error': 'Unsupported media type'
                }

            # 投稿の実行（リトライロジック付き）
            retry_count = 0
            while retry_count <= self.MAX_AUTH_RETRIES:
                try:
                    response = self._client.create_tweet(text=text)
                    
                    return {
                        'success': True,
                        'tweet_id': response['data']['id']
                    }
                
                except RateLimitError:
                    time.sleep(self.RATE_LIMIT_WAIT_TIME)
                except AuthenticationError:
                    if retry_count >= self.MAX_AUTH_RETRIES:
                        raise
                    retry_count += 1
                    time.sleep(1)
                except Exception as e:
                    if retry_count >= 2:  # ネットワークエラーは2回までリトライ
                        raise
                    retry_count += 1
                    time.sleep(1)

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _validate_media_types(self, media_paths: List[str]) -> bool:
        """メディアタイプのバリデーション"""
        return all(
            os.path.splitext(path)[1].lower() in self.SUPPORTED_MEDIA_TYPES
            for path in media_paths
        ) 