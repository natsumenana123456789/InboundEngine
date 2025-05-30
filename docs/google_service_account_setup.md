# 🔐 Google Service Account設定ガイド

## 🎯 目的
GitHub Actionsで動画変換システムがGoogle Sheetsにアクセスするために必要なサービスアカウントを設定します。

---

## 📋 Step 1: Google Cloud Consoleでプロジェクト作成

### 1-1. Google Cloud Consoleにアクセス
```
🌐 https://console.cloud.google.com/
👤 Googleアカウントでログイン
```

### 1-2. 新しいプロジェクトを作成
```
1. 左上「プロジェクトを選択」をクリック
2. 「新しいプロジェクト」をクリック
3. プロジェクト名: 「InboundEngine」（任意）
4. 「作成」をクリック
```

---

## ⚙️ Step 2: 必要なAPIを有効化

### 2-1. Google Sheets APIを有効化
```
1. Google Cloud Console → 「APIとサービス」 → 「ライブラリ」
2. 「Google Sheets API」を検索
3. 「Google Sheets API」をクリック
4. 「有効にする」をクリック
```

### 2-2. Google Drive APIを有効化（オプション）
```
1. 「APIとサービス」 → 「ライブラリ」
2. 「Google Drive API」を検索
3. 「Google Drive API」をクリック
4. 「有効にする」をクリック
```

---

## 🔑 Step 3: サービスアカウント作成

### 3-1. サービスアカウント作成
```
1. Google Cloud Console → 「IAMと管理」 → 「サービスアカウント」
2. 「サービスアカウントを作成」をクリック
3. サービスアカウント名: 「inbound-engine-sheets」
4. 説明: 「InboundEngine用のGoogle Sheets API接続」
5. 「作成して続行」をクリック
```

### 3-2. 権限設定（スキップ可能）
```
1. 「ロールを選択」で「編集者」を選択（オプション）
2. 「続行」をクリック
3. 「完了」をクリック
```

---

## 🗝️ Step 4: JSONキーファイル生成

### 4-1. キーを作成
```
1. 作成したサービスアカウントをクリック
2. 「キー」タブをクリック
3. 「鍵を追加」 → 「新しい鍵を作成」
4. 「JSON」を選択
5. 「作成」をクリック
```

### 4-2. ファイルダウンロード
```
💾 自動でJSONファイルがダウンロードされます
📁 ファイル名例: inbound-engine-sheets-1234567890ab.json
```

### 4-3. JSONファイルの中身（例）
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "abcd1234...",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG...\n-----END PRIVATE KEY-----\n",
  "client_email": "inbound-engine-sheets@your-project.iam.gserviceaccount.com",
  "client_id": "123456789012345678901",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/inbound-engine-sheets%40your-project.iam.gserviceaccount.com"
}
```

---

## 📊 Step 5: スプレッドシートに権限付与

### 5-1. サービスアカウントのメールアドレスをコピー
```
📧 client_email の値をコピー
例: inbound-engine-sheets@your-project.iam.gserviceaccount.com
```

### 5-2. スプレッドシートで共有設定
```
1. あなたのスプレッドシートを開く
   https://docs.google.com/spreadsheets/d/1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA/edit

2. 右上「共有」をクリック

3. 「ユーザーやグループを追加」に以下を入力:
   inbound-engine-sheets@your-project.iam.gserviceaccount.com

4. 権限: 「編集者」を選択

5. 「送信」をクリック
```

---

## 🔐 Step 6: GitHub Secretsに設定

### 6-1. GitHubリポジトリにアクセス
```
🌐 https://github.com/your-username/InboundEngine
```

### 6-2. Secrets設定画面へ
```
1. リポジトリ → 「Settings」
2. 左サイドバー → 「Secrets and variables」 → 「Actions」
3. 「New repository secret」をクリック
```

### 6-3. Secret追加
```
📝 Name: GOOGLE_SERVICE_ACCOUNT_JSON

💾 Secret: 
ダウンロードしたJSONファイルの中身を全てコピー&ペースト
（改行やスペースも含めて完全にコピー）
```

### 6-4. 設定例
```bash
Name: GOOGLE_SERVICE_ACCOUNT_JSON

Secret: 
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "abcd1234...",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG...\n-----END PRIVATE KEY-----\n",
  "client_email": "inbound-engine-sheets@your-project.iam.gserviceaccount.com",
  "client_id": "123456789012345678901",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/inbound-engine-sheets%40your-project.iam.gserviceaccount.com"
}
```

### 6-5. 保存
```
🔘 「Add secret」をクリック
✅ GOOGLE_SERVICE_ACCOUNT_JSON が追加されたことを確認
```

---

## 🧪 Step 7: 動作テスト

### 7-1. GitHub Actionsで手動実行
```
1. GitHubリポジトリ → 「Actions」
2. 「Video Conversion」をクリック
3. 「Run workflow」をクリック
4. 「Run workflow」をクリック（確認）
```

### 7-2. ログ確認
```
✅ 成功例:
- "✅ Google Sheets API接続成功"
- "📊 都内メンエス: X件のレコードを確認"
- "🎯 変換対象の画像: X件"

❌ 失敗例:
- "❌ Google Sheets API設定エラー"
- "❌ 権限がありません"
```

---

## 🚨 トラブルシューティング

### よくあるエラーと対処法

#### 1. "403 Forbidden" エラー
```
❌ 原因: スプレッドシートに権限がない
✅ 対処: サービスアカウントのメールをスプレッドシートに共有追加
```

#### 2. "Invalid JSON" エラー
```
❌ 原因: GitHub SecretsのJSONが不正
✅ 対処: JSONファイルを完全にコピー（改行含む）
```

#### 3. "API not enabled" エラー
```
❌ 原因: Google Sheets APIが無効
✅ 対処: Google Cloud ConsoleでAPIを有効化
```

#### 4. "Service account not found" エラー
```
❌ 原因: プロジェクトIDが間違い
✅ 対処: 正しいプロジェクトでサービスアカウント作成
```

---

## ✅ 完了チェックリスト

- [ ] Google Cloud Consoleでプロジェクト作成
- [ ] Google Sheets API有効化
- [ ] サービスアカウント作成
- [ ] JSONキーファイルダウンロード
- [ ] スプレッドシートに権限付与
- [ ] GitHub Secretsに GOOGLE_SERVICE_ACCOUNT_JSON 設定
- [ ] GitHub Actions手動実行テスト
- [ ] ログで接続成功確認

## 🎉 設定完了！

これでGitHub Actionsからあなたのスプレッドシートにアクセスできるようになりました！
動画変換システムが正常に動作します。 