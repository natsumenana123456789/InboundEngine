import json
import time
from typing import Dict, Optional
import requests
from datetime import datetime

class DiscordNotifier:
    def __init__(self, webhook_url: str, timeout: int = 30):
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.max_retries = 3

    def _validate_webhook_url(self) -> bool:
        """Webhook URLの検証"""
        return self.webhook_url.startswith("https://discord.com/api/webhooks/")

    def _handle_request(self, payload: Dict) -> bool:
        """リクエストの実行とエラーハンドリング"""
        if not self._validate_webhook_url():
            raise ValueError("WEBHOOK_INVALID: 無効なWebhook URLです")

        retries = 0
        while retries < self.max_retries:
            try:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 429:  # レート制限
                    retry_after = int(response.headers.get("Retry-After", 60))
                    time.sleep(retry_after)
                    retries += 1
                    continue
                
                return response.status_code == 204
            
            except requests.exceptions.Timeout:
                raise TimeoutError("TIMEOUT_ERROR: リクエストがタイムアウトしました")
            except requests.exceptions.RequestException:
                retries += 1
                if retries == self.max_retries:
                    raise ConnectionError("NETWORK_ERROR: ネットワークエラーが発生しました")
                time.sleep(5)  # リトライ前の待機

        return False

    def send_message(self, content: str, title: str = None, fields: Dict = None) -> bool:
        """通常メッセージを送信"""
        if len(content) > 2000:
            raise ValueError("VALIDATION_ERROR: メッセージが2000文字を超えています")

        payload = {"content": content}
        return self._handle_request(payload)

    def send_embed(
        self,
        title: str,
        description: str = None,
        fields: Dict = None,
        color: str = None,
        file_path: str = None
    ) -> bool:
        """エンベッドメッセージを送信"""
        embed = {
            "title": title,
            "timestamp": datetime.utcnow().isoformat()
        }

        if description:
            embed["description"] = description

        if color:
            # 16進数の色コードを10進数に変換
            embed["color"] = int(color.replace("#", ""), 16)

        if fields:
            embed_fields = []
            for name, value in fields.items():
                if len(embed_fields) >= 25:
                    break
                embed_fields.append({
                    "name": str(name),
                    "value": str(value),
                    "inline": True
                })
            embed["fields"] = embed_fields

        payload = {"embeds": [embed]}

        if file_path:
            try:
                with open(file_path, "rb") as f:
                    files = {"file": f}
                    response = requests.post(
                        self.webhook_url,
                        files=files,
                        data={"payload_json": json.dumps(payload)}
                    )
                    return response.status_code == 204
            except Exception as e:
                raise IOError(f"ファイルの添付に失敗しました: {str(e)}")

        return self._handle_request(payload)

    def send_error(self, error_message: str, error_details: Dict = None) -> bool:
        """エラーメッセージを送信"""
        return self.send_embed(
            title="エラー発生",
            description=error_message,
            fields=error_details,
            color="#ff0000"
        ) 