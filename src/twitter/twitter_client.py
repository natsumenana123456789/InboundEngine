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
    MAX_DAILY_POSTS = 5
    MAX_ACCOUNT_POSTS = 5
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
        self._daily_post_count = 0
        self._account_post_counts = {}
        self._last_reset = datetime.now()

    def post_tweet(
        self,
        text: str,
        media_paths: Optional[List[str]] = None,
        account_id: Optional[str] = None
    ) -> Dict:
        """ツイートを投稿する"""
        try:
            # 投稿制限のチェック
            if account_id and not self._check_account_post_limits(account_id):
                return {
                    'success': False,
                    'error': 'Account post limit exceeded'
                }
            
            if not self._check_post_limits(account_id):
                return {
                    'success': False,
                    'error': 'Daily post limit exceeded'
                }

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
                    
                    # 投稿カウントの更新
                    self._update_post_counts(account_id)
                    
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

    def _check_post_limits(self, account_id: Optional[str]) -> bool:
        """1日の投稿制限をチェック"""
        now = datetime.now()
        if now - self._last_reset > timedelta(days=1):
            self._daily_post_count = 0
            self._account_post_counts = {}
            self._last_reset = now
        
        return self._daily_post_count < self.MAX_DAILY_POSTS

    def _check_account_post_limits(self, account_id: str) -> bool:
        """アカウントごとの投稿制限をチェック"""
        return self._account_post_counts.get(account_id, 0) < self.MAX_ACCOUNT_POSTS

    def _update_post_counts(self, account_id: Optional[str]) -> None:
        """投稿カウントを更新"""
        self._daily_post_count += 1
        if account_id:
            self._account_post_counts[account_id] = \
                self._account_post_counts.get(account_id, 0) + 1

    def _validate_media_types(self, media_paths: List[str]) -> bool:
        """メディアタイプのバリデーション"""
        return all(
            os.path.splitext(path)[1].lower() in self.SUPPORTED_MEDIA_TYPES
            for path in media_paths
        ) 