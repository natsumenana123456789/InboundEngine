# 開発仕様書

## 通知機能（Notifiers）

### 概要
各種通知サービス（Discord等）への通知を統一的なインターフェースで実現する機能。

### 要件

#### 1. 基本機能
- 通知メッセージの送信
- エラー発生時の通知
- 処理結果の通知

#### 2. 通知サービス
1. Discord通知
   - Webhook URLによる通知
   - エンベッドメッセージのサポート
   - エラーレベルに応じた色分け
   - ファイル添付機能

#### 3. エラーハンドリング
- ネットワークエラーの適切な処理
- Webhook URLの検証
- リトライ機能（最大3回）
- タイムアウト設定（30秒）

#### 4. メッセージフォーマット
- タイトル（必須）
- 説明文（オプション）
- フィールド（キーバリューペア、オプション）
- タイムスタンプ（自動付与）
- カラーコード
  - 成功: #00ff00
  - 警告: #ffff00
  - エラー: #ff0000
  - 情報: #0000ff

### テスト仕様

#### 1. 単体テスト（Discord通知）

##### 基本機能テスト
- 通常メッセージの送信
- エンベッドメッセージの送信
- ファイル添付機能

##### エラーハンドリングテスト
- 無効なWebhook URLの処理
- ネットワークエラーのリトライ
- タイムアウトの処理

##### メッセージフォーマットテスト
- 各種フィールドの正常な送信
- 文字数制限の処理
- 特殊文字のエスケープ

##### セキュリティテスト
- Webhook URLのバリデーション
- 機密情報の適切な処理

### 実装詳細

#### 1. クラス構造
```python
class DiscordNotifier:
    def __init__(self, webhook_url: str, timeout: int = 30):
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.max_retries = 3

    def send_message(self, content: str, title: str = None, fields: dict = None) -> bool:
        """通常メッセージを送信"""
        pass

    def send_embed(self, title: str, description: str = None, fields: dict = None, 
                  color: str = None, file_path: str = None) -> bool:
        """エンベッドメッセージを送信"""
        pass

    def send_error(self, error_message: str, error_details: dict = None) -> bool:
        """エラーメッセージを送信"""
        pass
```

#### 2. エラーコード
- `WEBHOOK_INVALID`: Webhook URLが無効
- `NETWORK_ERROR`: ネットワークエラー
- `TIMEOUT_ERROR`: タイムアウト
- `RATE_LIMIT`: レート制限到達
- `VALIDATION_ERROR`: メッセージバリデーションエラー

#### 3. 設定パラメータ
```yaml
notifiers:
  discord:
    webhook_url: "${DISCORD_WEBHOOK_URL}"
    timeout: 30
    max_retries: 3
    rate_limit:
      max_requests: 5
      window_seconds: 60
```

### 制限事項
1. Discord Webhook制限
   - レート制限: 5回/分
   - メッセージサイズ: 最大2000文字
   - 添付ファイル: 最大8MB
   - エンベッドフィールド: 最大25個

2. エラーハンドリング
   - ネットワークエラー時は3回までリトライ
   - タイムアウトは30秒
   - レート制限超過時は60秒待機 