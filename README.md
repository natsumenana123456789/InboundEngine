# InboundEngine - 自動投稿Bot管理システム

## 📋 概要

InboundEngineは、X（旧Twitter）への自動投稿を効率的に管理するシステムです。スプレッドシートからデータを取得し、複数アカウントで自動投稿を行い、Slack通知でリアルタイムに状況を把握できます。

## 🚀 システム構成

### 現在稼働中のボット
- **auto_post_bot**: X API を使用した自動投稿ボット（メイン機能）
- **curate_bot**: コンテンツキュレーション・OCR処理ボット（現在無効化）

### 主要な機能
- ✅ X API による安定した投稿
- ✅ 複数アカウント対応
- ✅ スプレッドシートからの自動データ取得
- ✅ 最終投稿日時による投稿順序制御
- ✅ ランダムスペース挿入（重複回避）
- ✅ 動画メタデータ変換
- ✅ Slack 通知連携
- ✅ 投稿状況のスプレッドシート自動更新
- ✅ 自動スケジュール生成・管理

### スケジュール管理機能
`schedule_posts.py` による自動投稿スケジュール管理：
- **自動スケジュール生成**: 複数アカウントの投稿時刻を自動計算
- **時間間隔制御**: アカウント間で10分以上の間隔を確保
- **営業時間制限**: 9時〜21時の間で投稿スケジュール
- **Slack通知**: 当日のスケジュールを朝に通知
- **実行状況管理**: executed.txtで実行済み投稿を記録

### 設定ファイルの簡素化 🔧

`config/config.yml`は実際に使用されている機能のみに簡素化されています：

**現在有効な設定**:
- `common`: 基本設定（ログレベル、Google認証ファイル）
- `twitter_api`: X API認証情報
- `auto_post_bot`: 自動投稿Bot設定（アカウント情報、Slack連携）
- `curate_bot`: 無効化状態（将来使用予定）
- `analyze_bot`: 無効化状態（将来使用予定）

**削除された設定項目**:
- `default_user_agents`: 現在未使用
- `notion`: Notion連携は現在未使用
- `gemini_api / openai_api`: OCR・AI機能は現在未使用
- `posting_settings詳細`: デフォルト値で動作
- `scheduler詳細設定`: `schedule_posts.py`で管理
- その他の未使用設定

## 📚 READMEファイルの役割分担

このプロジェクトには複数のREADMEファイルがあり、それぞれ異なる役割を持っています：

### 📖 **このファイル (./README.md)**
- **対象ユーザー**: システム管理者・運用担当者
- **内容**: 全体概要、毎日の運用手順、アカウント管理、エラー対応
- **用途**: 日常運用のメインガイド

### 📖 **auto_post_bot (./bots/auto_post_bot/README 2.md)**
- **対象ユーザー**: 開発者・設定変更担当者
- **内容**: 自動投稿システムの技術詳細、Notion連携、プロファイル管理
- **用途**: 自動投稿機能の詳細設定と開発

### 📖 **curate_bot (./bots/curate_bot/README.md)**
- **対象ユーザー**: キュレーション機能利用者
- **内容**: X投稿収集、OCR機能、Notion連携の詳細
- **用途**: コンテンツキュレーションシステムの設定と運用

### 📖 **marshmallow (./bots/curate_bot/marshmallow/README.md)**
- **対象ユーザー**: Marshmallow-QA利用者
- **内容**: 質問・回答自動投稿機能
- **用途**: Marshmallowサービスとの連携機能

## 📝 毎日の運用手順

### 1. 朝の確認作業
```bash
# ターミナルでプロジェクトディレクトリに移動
cd /path/to/InboundEngine

# 仮想環境を有効化
source .venv/bin/activate

# ログ確認（前日の投稿状況チェック）
tail -20 logs/auto_post_logs/app.log

# 本日のスケジュール確認
python schedule_posts.py
```

### 2. スケジュール投稿実行
```bash
# 自動スケジュール生成（初回実行時）
python schedule_posts.py

# 現在時刻以降でスケジュール生成（中途半端な時間からでも対応）
python schedule_posts.py --now

# 既存スケジュールを強制的に再生成
python schedule_posts.py --force-regenerate

# 手動投稿実行
python -m bots.auto_post_bot.post_tweet

# または、定期実行の場合
# crontabで設定された時間に自動実行される
```

### 2.1. 🕐 中途半端な時間からのスケジュール生成

**例：午後3時38分に始める場合**
```bash
# 現在時刻（15:38）以降でスケジュール生成
python schedule_posts.py --now

# 実行例：
# ⏰ 現在時刻 15:38 以降でスケジュール生成します
# ✅ 新しいスケジュールを作成しました:
#   hinataHHHHHH: 2025-05-30 17:33:00 (約1時間54分後)
#   jadiAngkat: 2025-05-30 21:27:00 (約5時間48分後)
```

**営業時間外（22時以降）の場合**
```bash
python schedule_posts.py --now
# ⏰ 現在時刻 23:15 は営業時間外です
# 📅 翌日 (2025-05-31) の 10:00 からスケジュール生成します
```

**オプション一覧**
- `--now`: 現在時刻以降でスケジュール生成
- `--force-regenerate`: 既存スケジュールがあっても強制再生成
- `--mark-executed ACCOUNT DATETIME`: 指定投稿を実行済みにマーク

### 3. 結果確認
- **Slack**: 投稿成功/失敗の通知とスケジュール通知を確認
- **スプレッドシート**: 最終投稿日時と投稿済み回数が更新されているか確認
- **ログファイル**: 詳細なエラー情報が必要な場合
- **schedule.txt**: 当日の投稿スケジュール確認
- **executed.txt**: 実行済み投稿の履歴確認

## 🔧 アカウント追加手順

### 1. X Developer Portal での準備
1. [X Developer Portal](https://developer.twitter.com/) にログイン
2. 新しいアプリを作成
3. API Keys を取得:
   - Consumer Key
   - Consumer Secret  
   - Access Token
   - Access Token Secret

### 2. 設定ファイル更新
`config/config.yml` の `twitter_accounts` セクションに追加:

```yaml
auto_post_bot:
  twitter_accounts:
    - account_id: "新アカウント名"
      email: "メールアドレス"
      username: "ユーザー名"
      password: "パスワード（参考用）"
      consumer_key: "取得したConsumer Key"
      consumer_secret: "取得したConsumer Secret"
      access_token: "取得したAccess Token"
      access_token_secret: "取得したAccess Token Secret"
      google_sheets_source:
        enabled: true
        worksheet_name: "ワークシート名"
```

### 3. スケジュール設定に追加
`schedule_posts.py` の `ACCOUNTS` リストに新しいアカウント名を追加:

```python
ACCOUNTS = ['jadiAngkat', 'hinataHHHHHH', '新アカウント名']
```

### 4. スプレッドシート準備
Google スプレッドシートに新しいワークシートを作成し、以下の列を設定:
- ID
- 投稿タイプ
- 最終投稿日時
- 文字数
- 本文
- 画像/動画URL
- 投稿可能（チェックボックス）
- 投稿済み回数

## 📊 スプレッドシートへのデータ追加手順

### 1. 基本的な投稿データ形式
| ID | 投稿タイプ | 最終投稿日時 | 文字数 | 本文 | 画像/動画URL | 投稿可能 | 投稿済み回数 |
|----|-----------|-------------|--------|------|-------------|----------|-------------|
| 1  | 通常投稿   | 2025-01-01 10:00:00 | 50 | 投稿内容... | https://drive.google.com/... | ✅ | 0 |

### 2. 重要な注意点
- **ID**: 各行に一意のIDを設定
- **本文**: 文字数制限（280文字以下）を考慮
- **画像/動画URL**: Google Driveの共有URLを使用
- **最終投稿日時**: 古い日時のものから優先的に投稿される
- **投稿可能**: ✅ チェック済みの投稿のみが実行対象（未チェックは除外）
- **投稿アカウント判別**: ワークシート名で自動判別（都内メンエス→jadiAngkat、都内セクキャバ→hinataHHHHHH）

### 3. Google Drive メディアファイルの準備
1. 画像・動画をGoogle Driveにアップロード
2. 「リンクを知っている全員が閲覧可」に設定
3. 共有URLをスプレッドシートに貼り付け

## 📝 新しい投稿を追加する手順

### 1. コンテンツ準備フェーズ
```bash
# メディアファイルの準備（推奨ファイル形式）
# 画像: JPG, PNG (5MB以下)
# 動画: MP4 (512MB以下、2分20秒以下)
```

### 2. Google Drive へのアップロード
1. **フォルダ組織化**:
   - アカウント別フォルダを作成（例：`jadiAngkat_media`）
   - 日付別サブフォルダで整理（例：`2025-01-30`）

2. **アップロード手順**:
   ```
   1. Google Drive にログイン
   2. 対象フォルダを開く
   3. ファイルをドラッグ&ドロップ
   4. アップロード完了を確認
   ```

3. **共有設定**:
   ```
   1. ファイルを右クリック → 「共有」
   2. 「リンクを知っている全員」に変更
   3. 「閲覧者」権限を確認
   4. 「リンクをコピー」をクリック
   ```

### 3. スプレッドシート更新の詳細手順

#### ステップ1: 新しい行の追加
1. Google Sheets で該当のワークシートを開く
2. 最下行の下に新しい行を挿入
3. ID列に連番を入力（既存の最大ID + 1）

#### ステップ2: 基本情報の入力
```
ID: 連番（例：49）
投稿タイプ: 通常投稿
最終投稿日時: 優先度に応じた日時（古い日時 = 高優先度）
文字数: 本文の文字数（自動計算も可）
本文: 投稿内容（280文字以下）
画像/動画URL: Google Driveの共有URL
投稿可能: ✅
投稿済み回数: 0（初期値）
```

#### ステップ3: 本文作成のベストプラクティス
- **文字数確認**: 280文字以下に収める
- **ハッシュタグ**: 適切なハッシュタグを含める
- **改行**: 読みやすさを考慮した改行
- **絵文字**: 適度な絵文字の使用

#### ステップ4: 投稿可能フラグの設定
- **✅ チェック済み**: 投稿対象に含まれる
- **❌ 未チェック**: 投稿から除外される
- **用途例**: 
  - 下書き状態の投稿を一時的に無効化
  - 季節限定投稿の期間外での無効化
  - テスト投稿の本番環境での除外

### 4. 優先度設定による投稿順序制御

#### 高優先度（すぐに投稿したい）
```
最終投稿日時: 2020-01-01 00:00:00
```

#### 通常優先度
```
最終投稿日時: 現在日時の1日前
```

#### 低優先度（後回しにしたい）
```
最終投稿日時: 現在日時
```

### 5. 投稿後の自動更新確認

投稿実行後、以下が自動更新されます：
- **最終投稿日時**: 投稿実行時刻に更新
- **投稿済み回数**: +1 されて更新
- **ステータス**: （設定によって「投稿完了」に更新）

### 6. 品質チェックポイント

#### 投稿前チェックリスト
- [ ] 本文の誤字脱字確認
- [ ] 文字数制限（280文字以下）
- [ ] メディアファイルの表示確認
- [ ] URL の動作確認
- [ ] アカウント名の正確性
- [ ] 優先度設定の妥当性

#### メディアファイルチェック
- [ ] ファイル形式が対応しているか
- [ ] ファイルサイズが制限内か
- [ ] 画質・音質が適切か
- [ ] Google Drive の共有設定が正しいか

### 7. 大量投稿追加時の効率化

#### CSVインポート方法
1. Excel または Google Sheets でデータを準備
2. CSV形式でエクスポート
3. Google Sheets の「ファイル」→「インポート」
4. 既存データに追加する設定で実行

#### 一括メディアアップロード
1. Google Drive デスクトップアプリを使用
2. ローカルフォルダで整理してから同期
3. 一括で共有設定を変更

### 8. トラブル時の対処法

#### スプレッドシート更新が反映されない
```bash
# 権限確認
# Google Sheets の共有設定を確認
# サービスアカウントがエディター権限を持っているか確認

# 手動で同期確認
python -c "
from bots.auto_post_bot.post_tweet import get_posts_from_sheet
posts = get_posts_from_sheet('jadiAngkat')
print(f'取得件数: {len(posts)}')
"
```

#### メディアダウンロードエラー
1. Google Drive URL の形式確認
2. 共有設定の確認
3. ファイルサイズの確認
4. インターネット接続の確認

## ⚠️ エラーパターンと対応方法

### 1. API認証エラー
**症状**: `Twitter APIクライアントの初期化に失敗`
**アラート**: Slack に「❌ 投稿失敗」通知
**対応**:
```bash
# API キーの確認
grep -A 10 "twitter_api:" config/config.yml

# 権限確認（X Developer Portal で確認）
# - Read and write permissions が設定されているか
# - アクセストークンが最新か
```

### 2. スプレッドシート接続エラー
**症状**: `Google Sheetsからのデータ取得中にエラー`
**アラート**: ログファイルにエラー記録
**対応**:
```bash
# サービスアカウントキーの確認
ls -la config/gspread-key.json

# スプレッドシート名の確認
grep "sheet_name:" config/config.yml
```

### 3. メディアダウンロードエラー
**症状**: `メディアのダウンロードに失敗`
**アラート**: ログに「画像のダウンロード中にエラー」
**対応**:
- Google Drive URLの共有設定を確認
- インターネット接続状況を確認
- URL形式が正しいか確認

### 4. FFmpeg関連エラー
**症状**: `動画メタデータ変換中にエラー`
**対応**:
```bash
# FFmpegのインストール確認
ffmpeg -version

# macOSの場合、再インストール
brew install ffmpeg
```

### 5. スケジュール生成エラー
**症状**: `10分以上離れた時刻が見つかりませんでした`
**アラート**: ログファイルにエラー記録
**対応**:
```bash
# schedule_posts.pyの設定を確認・調整
# MIN_INTERVAL_MINUTES の値を小さくする
# START_HOUR と END_HOUR の範囲を広げる
# POSTS_PER_ACCOUNT の値を小さくする
```

## 💻 PC移動時の注意点

### 1. カフェなど公共Wi-Fi使用時
```bash
# VPN接続の確認（推奨）
# API制限やセキュリティ考慮

# 手動実行でテスト
python -m bots.auto_post_bot.post_tweet

# エラーがないことを確認してから定期実行
```

### 2. 環境の持ち運び手順
```bash
# 1. 仮想環境の有効化確認
source .venv/bin/activate
which python  # プロジェクト内のpythonが使われているか確認

# 2. 依存関係の確認
pip list | grep tweepy
pip list | grep gspread

# 3. 設定ファイルの確認
ls -la config/

# 4. ログディレクトリの確認
ls -la logs/auto_post_logs/

# 5. スケジュールファイルの確認
ls -la schedule.txt executed.txt
```

### 3. トラブルシューティング
```bash
# パスの確認
pwd
ls -la

# Python環境の確認
python --version
pip --version

# 必要に応じて依存関係の再インストール
pip install -r requirements.txt

# スケジュールファイルの再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## 📋 定期実行の設定

### crontab設定例（推奨）
```bash
# crontabを編集
crontab -e

# 毎朝8時にスケジュール生成＋Slack通知
0 8 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python schedule_posts.py >> logs/schedule.log 2>&1

# 毎日9時、13時、17時に投稿実行
0 9,13,17 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python -m bots.auto_post_bot.post_tweet >> logs/cron.log 2>&1
```

### スケジュール管理の詳細
```bash
# 当日のスケジュール確認
cat schedule.txt

# 実行済み投稿の確認
cat executed.txt

# スケジュールの手動再生成
rm schedule.txt
python schedule_posts.py
```

## 📞 緊急時の連絡先・対応

### 1. Bot停止方法
```bash
# 実行中プロセスの確認
ps aux | grep python

# 強制停止（必要に応じて）
pkill -f "post_tweet"
pkill -f "schedule_posts"
```

### 2. 手動投稿での緊急対応
```bash
# 特定アカウントのみテスト投稿
python -c "
from bots.auto_post_bot.post_tweet import *
# 手動でのテスト実行コード
"

# スケジュールをリセットして再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## ☁️ クラウド運用（推奨）

### 🎯 GitHub Actions（最推奨）

#### **コスト**: 🟢 **完全無料**
- プライベートリポジトリでも月2,000分無料
- 1日4回実行 = 月約240分 → **実質無料**

#### **運用の簡単さ**: 🟢 **最簡単**
- Git push だけで自動デプロイ
- ゼロメンテナンション（サーバー管理不要）
- Web UIでログ確認可能

#### **DevOps**: 🟢 **最も簡単**
- Secrets管理が組み込み
- 手動実行ボタンあり
- 自動スケーリング

### 🚀 GitHub Actions 完全デプロイ手順

#### 1. リポジトリ準備
```bash
# プライベートリポジトリ作成（機密情報があるため）
gh repo create InboundEngine-Bot --private
git remote add origin https://github.com/yourusername/InboundEngine-Bot.git
git push -u origin main
```

#### 2. GitHub Secrets 設定 ⚙️
`Settings > Secrets and variables > Actions` で以下を設定:

**🔑 必須Secrets:**
```
# 共通設定
GOOGLE_SHEETS_KEY: (gspread-key.json の内容をまるごと)
SLACK_WEBHOOK_URL: (Slack Webhook URL)
TWITTER_BEARER_TOKEN: (X API Bearer Token - 共通)

# jadiAngkat アカウント用 (Account1)
ACCOUNT1_CONSUMER_KEY: (jadiAngkat用 Consumer Key)
ACCOUNT1_CONSUMER_SECRET: (jadiAngkat用 Consumer Secret)
ACCOUNT1_ACCESS_TOKEN: (jadiAngkat用 Access Token)
ACCOUNT1_ACCESS_TOKEN_SECRET: (jadiAngkat用 Access Token Secret)
ACCOUNT1_EMAIL: (jadiAngkatのメールアドレス)

# hinataHHHHHH アカウント用 (Account2)
ACCOUNT2_CONSUMER_KEY: (hinataHHHHHH用 Consumer Key)
ACCOUNT2_CONSUMER_SECRET: (hinataHHHHHH用 Consumer Secret)
ACCOUNT2_ACCESS_TOKEN: (hinataHHHHHH用 Access Token)
ACCOUNT2_ACCESS_TOKEN_SECRET: (hinataHHHHHH用 Access Token Secret)
ACCOUNT2_EMAIL: (hinataHHHHHHのメールアドレス)
```

**💡 Secrets設定の簡潔リスト:**
```
GOOGLE_SHEETS_KEY
SLACK_WEBHOOK_URL
TWITTER_BEARER_TOKEN
ACCOUNT1_CONSUMER_KEY
ACCOUNT1_CONSUMER_SECRET
ACCOUNT1_ACCESS_TOKEN
ACCOUNT1_ACCESS_TOKEN_SECRET
ACCOUNT1_EMAIL
ACCOUNT2_CONSUMER_KEY
ACCOUNT2_CONSUMER_SECRET
ACCOUNT2_ACCESS_TOKEN
ACCOUNT2_ACCESS_TOKEN_SECRET
ACCOUNT2_EMAIL
```

#### 3. 自動実行スケジュール 📅
設定済みの実行スケジュール:
- **毎朝8時**: スケジュール生成 + Slack通知
- **毎日10時、14時、18時、21時**: 自動投稿実行
- **Git push時**: 「スクリプトが更新されました。」Slack通知

#### 4. 手動実行オプション 🔧
GitHub Actions画面で「Run workflow」ボタンから:
- `post`: 投稿実行
- `schedule`: 通常スケジュール生成
- `schedule-now`: 現在時刻以降でスケジュール生成

#### 5. Slack通知の詳細 📱

**📢 Git Push通知:**
```
🔄 スクリプトが更新されました。
Repository: user/InboundEngine-Bot
Commit: feat: 新機能追加
Author: user
Branch: main
```

**📅 スケジュール通知（改善版）:**
```
📅 自動投稿スケジュール

• jadiAngkat: 05/30 17:33 (約1時間54分後)
• hinataHHHHHH: 05/30 21:27 (約5時間48分後)

📊 合計2件 | 2アカウント
⏰ 生成時刻: 2025-05-30 15:38:15
```

**🌙 夜間実行時の通知:**
```
🌙 夜間スケジュール生成完了 （営業時間外のため翌日に設定）

• jadiAngkat: 05/31 11:15 (約12時間37分後)
• hinataHHHHHH: 05/31 16:42 (約18時間4分後)

📊 合計2件 | 2アカウント | 本日0件・翌日2件
⏰ 生成時刻: 2025-05-30 23:15:30
```

### 🔧 その他のクラウドオプション

#### **Railway** ($5/月の無料クレジット)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

#### **AWS EC2 t2.micro** (1年間無料)
- より多くの設定が必要
- Linux サーバー管理スキル必要

#### **Google Cloud Run** (月200万リクエスト無料)
- Dockerfile が必要
- GCP の設定が複雑

### ✅ GitHub Actions の利点

- **完全無料** (プライベートリポジトリでも実質無料)
- **ゼロメンテナンス** (サーバー管理不要)
- **自動スケーリング** (必要に応じてリソース調整)
- **ログ管理** (Web UIで確認可能)
- **手動実行** (緊急時にボタン一つで実行)
- **セキュリティ** (Secrets 管理が組み込み)
- **DevOps** (Git push で自動デプロイ)

### 📋 移行手順

#### 1. ローカル → クラウド移行
```bash
# 機密情報をGitHub Secretsに移行
# テスト実行で動作確認
# ローカル cron を停止
# GitHub Actions を有効化
```

#### 2. 段階的移行
1. 最初は手動実行のみでテスト
2. 動作確認後にスケジュール実行を有効化
3. ローカル実行を徐々に停止

**結論: GitHub Actions が最もコスト効率と運用効率のバランスが良く、DevOps も最も簡単です！** 🎉

## 📊 実際の運用ログ例

### 正常実行時のログ
```
2025-05-30 14:59:37,071 - INFO - ===== Auto Post Bot 開始 =====
2025-05-30 14:59:38,817 - INFO - 48 件の投稿ストックを取得しました。
2025-05-30 14:59:38,819 - INFO - [DEBUG] 全8件中、最終投稿日時が最も古い投稿を選択しました
2025-05-30 14:59:44,834 - INFO - ツイート投稿成功。Tweet ID: 1928330467050410158
2025-05-30 14:59:45,161 - INFO - Slack通知を送信しました
2025-05-30 14:59:49,048 - INFO - 投稿ID 3 のステータスを '投稿完了' に更新しました
```

### スケジュール生成時のログ
```
新しいスケジュールを作成しました:
jadiAngkat,2025-05-30 09:15:00
hinataHHHHHH,2025-05-30 14:32:00
jadiAngkat,2025-05-30 18:45:00
Slackにスケジュールを通知しました
```

### エラー発生時のログ例
```
2025-05-30 15:00:00,000 - ERROR - Twitter APIクライアントの初期化に失敗しました
2025-05-30 15:00:00,001 - ERROR - Google Sheetsからのデータ取得中にエラーが発生しました
2025-05-30 15:00:00,002 - ERROR - メディアのダウンロードに失敗しました
```

## ❓ よくある質問（FAQ）

### Q: 投稿が実行されないのですが？
**A**: 以下を確認してください：
1. スプレッドシートに投稿データがあるか
2. API認証情報が正しいか
3. スケジュールが正しく生成されているか（`schedule.txt`を確認）

### Q: 同じ投稿が何度も実行されます
**A**: スプレッドシートの「最終投稿日時」列が正しく更新されていない可能性があります。Google Sheetsの権限とサービスアカウントキーを確認してください。

### Q: 動画投稿でエラーが出ます
**A**: 
1. FFmpegがインストールされているか確認
2. 動画ファイルサイズが512MB以下か確認
3. Google DriveのURLが正しいか確認

### Q: Slack通知が来ません
**A**: `config/config.yml`の`slack`セクションでWebhook URLが正しく設定されているか確認してください。

### Q: スケジュールが生成されません
**A**: 
1. `schedule_posts.py`の設定値を確認
2. アカウント数と投稿回数の設定が適切か確認
3. 営業時間設定（START_HOUR, END_HOUR）を確認

### Q: PC移動後に動作しません
**A**: 
1. インターネット接続を確認
2. 仮想環境が正しく有効化されているか確認
3. `which python`で正しいPythonが使用されているか確認
4. スケジュールファイルが存在するか確認（`ls schedule.txt executed.txt`）

### Q: 投稿順序を変更したい
**A**: スプレッドシートの「最終投稿日時」列を編集することで、投稿順序を制御できます。古い日時のものから優先的に投稿されます。

### Q: 複数アカウントを同時実行したい
**A**: 現在のシステムは各アカウントを順次実行します。完全な同時実行には改修が必要です。

### Q: スケジュールを手動で調整したい
**A**: `schedule.txt`ファイルを直接編集するか、`schedule_posts.py`の設定値を変更してスケジュールを再生成してください。

## 🔗 関連リソース

- **X API Documentation**: https://developer.twitter.com/en/docs
- **Google Sheets API**: https://developers.google.com/sheets/api
- **FFmpeg**: https://ffmpeg.org/
- **ログファイル場所**: `logs/auto_post_logs/app.log`
- **設定ファイル**: `config/config.yml`
- **スケジュールファイル**: `schedule.txt` / `executed.txt`

---
**最終更新**: 2025年1月  
**バージョン**: 2.0.0 

## 🎯 システム概要

X（Twitter）での自動投稿を行うシステムです。Google スプレッドシートから投稿データを取得し、スケジュールに従って自動投稿を実行します。

### 主要機能
- 📊 Google スプレッドシートからの投稿データ取得
- 🤖 X API を使用した自動投稿
- 📅 スケジュール管理システム
- 📹 動画メタデータ変換（FFmpeg）
- 🔀 ランダムスペース挿入（検出回避）
- 📱 Slack 通知
- 🧵 ツリー投稿対応（長文自動分割）

## 🔧 アカウント管理

すべてのアカウント情報は `config/config.yml` で一元管理されます。

### 🔄 新しいアカウント追加手順

#### 1. X Developer Portal での準備
1. [X Developer Portal](https://developer.twitter.com/) にアクセス
2. 新しいアプリケーションを作成
3. API Keys と Access Tokens を取得

#### 2. config.yml への追加
`config/config.yml` の `twitter_accounts` セクションに追加：

```yaml
auto_post_bot:
  twitter_accounts:
    - account_id: "新アカウント名"
      email: "メールアドレス"
      username: "ユーザー名"
      password: "パスワード（参考用）"
      consumer_key: "取得したConsumer Key"
      consumer_secret: "取得したConsumer Secret"
      access_token: "取得したAccess Token"
      access_token_secret: "取得したAccess Token Secret"
      google_sheets_source:
        enabled: true
        worksheet_name: "ワークシート名"
```

#### 3. 投稿データ用ワークシートの準備
1. Google Drive で新しいワークシートを作成
2. 投稿データを追加（[投稿データ追加手順](#-投稿データ追加手順) 参照）
3. 適切な共有設定を行う

#### 4. Git でデプロイ
```bash
git add config/config.yml
git commit -m "新しいアカウント追加: 新アカウント名"
git push
```

#### 5. 動作確認
```bash
# 特定アカウントでテスト実行
python3 bots/auto_post_bot/post_tweet.py --account 新アカウント名

# スケジューラでの確認
python3 schedule_posts.py
```

### 🎛️ 運用上の利点

1. **シンプル管理**: config.yml だけでアカウント設定が完結
2. **バージョン管理**: Git でアカウント追加履歴を管理
3. **即座反映**: Git push で設定がすぐに有効
4. **分かりやすい**: 情報が分散せず、全てがconfig.ymlに集約

### ⚠️ ツリー投稿機能

長文投稿（270字超過）は自動的にツリー投稿（スレッド投稿）に分割されます。

- **Twitter文字数制限**: 280字
- **システム制限**: 270字（安全マージン）
- **推奨**: 240字以下

#### 制限超過時の動作
1. **270字以上**: 自動的にツリー投稿（スレッド投稿）に分割
2. **240字以上**: 警告ログを出力（投稿は実行）
3. **ログ出力例**:
   ```
   📝 長文投稿を検出: 350字 → ツリー投稿に分割します
   ツリー投稿: 2個のツイートに分割
     1. (1/2) 最初の部分の投稿内容... (265字)
     2. (2/2) 続きの投稿内容... (85字)
   ✅ ツリー投稿投稿成功 (Tweet ID: 1234567890)
   ```

#### ツリー投稿の特徴
- **自動分割**: 句読点、改行、スペースで自然に分割
- **スレッド番号**: "(1/3)"のような番号を自動追加
- **メディア添付**: 最初のツイートにのみ画像・動画を添付
- **投稿間隔**: ツイート間に2秒の間隔を設定
- **連続投稿**: 返信形式でスレッドを自動構成