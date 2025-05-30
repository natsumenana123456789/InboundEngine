# GitHub Secrets 設定ガイド - 2アカウント運用版

## 🔐 必要なSecret一覧

### 📱 Twitter API (共通)
```
TWITTER_BEARER_TOKEN: Bearer Token
TWITTER_CONSUMER_KEY: Consumer Key
TWITTER_CONSUMER_SECRET: Consumer Secret
TWITTER_ACCESS_TOKEN: Access Token
TWITTER_ACCESS_TOKEN_SECRET: Access Token Secret
```

### 🏪 アカウント1: jadiAngkat (都内メンエス)
```
ACCOUNT1_EMAIL: アカウントのメールアドレス
ACCOUNT1_CONSUMER_KEY: Consumer Key
ACCOUNT1_CONSUMER_SECRET: Consumer Secret
ACCOUNT1_ACCESS_TOKEN: Access Token
ACCOUNT1_ACCESS_TOKEN_SECRET: Access Token Secret
```

### 🍷 アカウント2: hinataHHHHHH (都内セクキャバ)
```
ACCOUNT2_EMAIL: アカウントのメールアドレス
ACCOUNT2_CONSUMER_KEY: Consumer Key
ACCOUNT2_CONSUMER_SECRET: Consumer Secret
ACCOUNT2_ACCESS_TOKEN: Access Token
ACCOUNT2_ACCESS_TOKEN_SECRET: Access Token Secret
```

### 📊 Google Sheets & Slack
```
GOOGLE_SHEETS_KEY: Google Sheets APIキー（JSON全体）
SLACK_WEBHOOK_URL: Slack Webhook URL
```

## ✅ **これで必要なSecretsは12個だけです！**

## ⚙️ 設定手順

### 1. GitHubリポジトリでSecrets設定
```
1. GitHubリポジトリページを開く
2. Settings タブをクリック
3. 左メニューから「Secrets and variables」→「Actions」を選択
4. 「New repository secret」をクリック
5. 上記のSecret名と値を1つずつ追加
```

### 2. Twitter APIキーの取得方法
```
各アカウントで以下の手順：
1. https://developer.twitter.com/ にアクセス
2. 該当Twitterアカウントでログイン
3. プロジェクト/アプリを作成
4. Keys and tokens からAPIキーを取得
5. App permissions を「Read and write」に設定
```

### 3. Google Sheets APIキーの取得
```
1. Google Cloud Console でプロジェクト作成
2. Google Sheets API を有効化
3. サービスアカウント作成
4. 秘密鍵（JSON）をダウンロード
5. JSON全体をGOOGLE_SHEETS_KEYとして設定
```

### 4. Slack Webhook URLの取得
```
1. Slack ワークスペースでアプリ作成
2. Incoming Webhooks 機能を有効化
3. チャンネルを指定してWebhook URL取得
4. SLACK_WEBHOOK_URLとして設定
```

## 🔍 Secret設定の確認方法

### GitHub Actions画面での確認
```
1. リポジトリの「Actions」タブを開く
2. 任意のワークフロー実行を選択
3. ログでSecret名がマスクされていることを確認
4. エラーメッセージで不足しているSecretを特定
```

### テスト実行での確認
```
1. GitHubリポジトリで「Actions」タブを開く
2. 「Auto Post Bot with Scheduler」を選択
3. 「Run workflow」をクリック
4. Action: "post" を選択して実行
5. ログを確認してエラーがないかチェック
```

## 📈 将来の拡張

### 新しいワークシート追加時
```
1. スプレッドシートに新しいワークシートを作成
2. 列構成を統一（ID、投稿タイプ、最終投稿日時...）
3. 必要に応じて新しいTwitterアカウント追加
4. ワークフローファイルに設定追加
5. 対応するSecretsを追加
```

### 段階的拡張の例
```
Phase 1: 都内メンエス、都内セクキャバ ← 今ここ
Phase 2: + 大阪メンエス（jadiAngkatアカウントで兼用）
Phase 3: + 名古屋メンエス（新規アカウント追加）
Phase 4: + 広島風俗、銀座キャバ（専用アカウント）
```

## ⚠️ セキュリティ注意事項

### Secret管理のベストプラクティス
```
✅ 推奨:
- Secret名は分かりやすく統一的に命名
- APIキーは定期的にローテーション
- 不要になったSecretは削除
- アクセス権限は最小限に設定

❌ 避けるべき:
- Secretをログに出力
- Secret値をコードにハードコーディング
- 複数人でSecret値を共有
- 本番と開発で同じAPIキーを使用
```

### トラブルシューティング
```
🔧 よくある問題：

1. Secret名の typo
   → GitHub Actions ログで「secret not found」エラー

2. Twitter API権限不足
   → 「Forbidden」または「Unauthorized」エラー

3. Google Sheets権限不足
   → 「Permission denied」エラー

4. Slack Webhook URL無効
   → Slack通知が送信されない
```

この設定が完了すると、2つのワークシートでの自動投稿が正常に動作します！
必要に応じて後から追加ワークシートを簡単に拡張できます。 