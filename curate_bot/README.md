# 🐦 scrape_and_save_tweets - X(Twitter)投稿収集＋ Notion 連携スクリプト

このツールは X（旧 Twitter）から投稿を効率的に収集し、Notion データベースへ自動保存する Python スクリプトです。特定アカウントの投稿・スレッド、キーワードによる検索など複数の収集モードをサポートし、Web ブラウザの自動操作（Selenium）で効率的にデータを取得します。

---

## 📋 目次

1. [主な機能](#%EF%B8%8F-主な機能)
2. [環境構築](#-環境構築)
3. [設定ファイル詳細](#-設定ファイル詳細)
4. [コマンド実行方法](#-コマンド実行方法)
5. [モード別詳細説明](#-モード別詳細説明)
6. [Notion 連携方法](#-notion連携方法)
7. [URL 重複排除と最適化](#-url重複排除と最適化)
8. [画像・動画の自動保存](#-画像動画の自動保存)
9. [OCR 機能と自然言語処理](#-ocr機能と自然言語処理)
10. [トラブルシューティング](#-トラブルシューティング)
11. [サンプル出力](#-サンプル出力)
12. [更新履歴](#-更新履歴)

---

## ⚙️ 主な機能

- **マルチモード収集**：アカウント・キーワード・トレンド検索
- **スレッド・自リプライ対応**：関連投稿を一括収集
- **メディア自動保存**：画像・動画をローカルに保存
- **Notion 自動連携**：専用データベースに投稿を構造化保存
- **OCR 画像解析**：画像内のテキスト自動抽出（OpenAI Vision）
- **自然言語処理**：投稿カテゴライズと内容要約
- **メトリクス取得**：インプレッション・エンゲージメント等の指標収集
- **重複排除機能**：URL と ID 両方での高精度重複チェック
- **エラー耐性**：接続問題や API 制限に対するリトライロジック
- **セッション管理**：再ログイン不要の Cookie 保存機能
- **リソース最適化**：不要アクセス削減のスマートスクロール制御

---

## 🔧 環境構築

### 前提条件

- Python 3.8 以上
- Google Chrome ブラウザ
- Chrome ドライバー（Chrome と同一バージョン）
- 有効な X アカウント
- Notion API 統合キー

### インストール手順

1. **リポジトリのクローン**:

   ```bash
   git clone https://github.com/your-username/scrape_and_save_tweets.git
   cd scrape_and_save_tweets
   ```

2. **Python 環境構築と必要ライブラリインストール**:

   ```bash
   # 仮想環境を作成（推奨）
   python -m venv venv

   # 仮想環境を有効化
   # Windows:
   venv\\Scripts\\activate
   # macOS/Linux:
   source venv/bin/activate

   # 必要なライブラリをインストール
   pip install selenium==4.11.2 openai==1.3.0 notion-client==2.0.0 requests==2.31.0 beautifulsoup4==4.12.2 Pillow==10.0.0
   ```

3. **Chrome ドライバーの準備**:

   - [ChromeDriver ダウンロードページ](https://chromedriver.chromium.org/downloads)から、インストールされている Chrome のバージョンに合ったドライバーをダウンロード
   - ダウンロードしたファイルを解凍し、システムパスの通った場所に配置するか、プロジェクトディレクトリに配置

4. **必要なディレクトリ構造の作成**:

   ```bash
   # 画像・動画保存用ディレクトリを作成
   mkdir -p images videos
   ```

5. **設定ファイルの準備**:
   - `config.json` および `accounts.json` を後述の説明に従い作成

---

## 📝 設定ファイル詳細

### config.json

```json
{
  "notion_token": "secret_abcdefghijklmnopqrstuvwxyz123456789",
  "database_id": "1234567890abcdef1234567890abcdef",
  "database_id_processed_posts": "abcdef1234567890abcdef1234567890",
  "extract_target": "elonmusk",
  "max_tweets": 30,
  "max_candidates_multiplier": 1.5,
  "pause_scroll_threshold": 3,
  "max_consecutive_scrolls": 15,
  "max_scrolls": 50,
  "scroll_pause_time": 1.0,
  "mode": "target_only",
  "filter_keywords_name_bio": ["テック", "エンジニア", "開発者"],
  "filter_keywords_tweet": ["Python", "AI", "機械学習"],
  "openai_api_key": "sk-abcdefghijklmnopqrstuvwxyz123456789",
  "skip_upload": false,
  "save_media": true,
  "ocr_enabled": true,
  "use_gpt": true,
  "max_retries": 3,
  "retry_delay": 5,
  "exclude_domains": ["shrtco.de", "bit.ly"]
}
```

#### 設定項目解説

| 設定項目                      | 説明                                         | デフォルト値  |
| ----------------------------- | -------------------------------------------- | ------------- |
| `notion_token`                | Notion の API 統合キー                       | 必須          |
| `database_id`                 | 投稿保存先の Notion データベース ID          | 必須          |
| `database_id_processed_posts` | 処理済み ID 保存用のデータベース ID          | 任意          |
| `extract_target`              | 収集対象のユーザー名/検索キーワード          | モードによる  |
| `max_tweets`                  | 1 回の実行で取得する最大投稿数               | 30            |
| `max_candidates_multiplier`   | 目標投稿数に対する候補 URL 収集数の倍率      | 1.5           |
| `pause_scroll_threshold`      | 新規投稿が見つからない時のスクロール継続回数 | 3             |
| `max_consecutive_scrolls`     | 一度の処理での最大連続スクロール数           | 15            |
| `max_scrolls`                 | 全体のスクロール上限回数                     | 50            |
| `scroll_pause_time`           | スクロール間の待機時間（秒）                 | 1.0           |
| `mode`                        | 収集モード（下記参照）                       | "target_only" |
| `filter_keywords_name_bio`    | 名前/プロフィールのフィルターキーワード      | []            |
| `filter_keywords_tweet`       | 投稿内容のフィルターキーワード               | []            |
| `openai_api_key`              | OpenAI API キー（OCR/GPT 要約用）            | 任意          |
| `skip_upload`                 | Notion へのアップロードをスキップするか      | false         |
| `save_media`                  | 画像・動画を保存するか                       | true          |
| `ocr_enabled`                 | 画像 OCR を有効にするか                      | false         |
| `use_gpt`                     | GPT による内容要約・カテゴリ判定を行うか     | false         |
| `max_retries`                 | エラー時の最大リトライ回数                   | 3             |
| `retry_delay`                 | リトライ間の待機時間（秒）                   | 5             |
| `exclude_domains`             | 除外する短縮 URL 等のドメイン                | []            |

### accounts.json

```json
{
  "email": "your_email@example.com",
  "username": "your_twitter_username",
  "password": "your_twitter_password"
}
```

**セキュリティ注意事項**:

- `accounts.json` と `config.json` は `.gitignore` に追加し、リポジトリに公開されないようにしてください
- `openai_api_key` や `notion_token` などの機密情報は環境変数で管理することも検討してください

---

## 🚀 コマンド実行方法

### 基本実行

```bash
python scrape_and_save_tweets.py
```

### コマンドラインオプション

```bash
python scrape_and_save_tweets.py --config custom_config.json --account custom_accounts.json --mode target_only --target elonmusk --max 50
```

| オプション      | 短縮形 | 説明                               | デフォルト       |
| --------------- | ------ | ---------------------------------- | ---------------- |
| `--config`      | `-c`   | 設定ファイルのパス                 | `config.json`    |
| `--account`     | `-a`   | アカウント情報ファイルのパス       | `accounts.json`  |
| `--mode`        | `-m`   | 実行モード（設定ファイルより優先） | 設定ファイルの値 |
| `--target`      | `-t`   | 抽出対象（設定ファイルより優先）   | 設定ファイルの値 |
| `--max`         | `-n`   | 最大取得数（設定ファイルより優先） | 設定ファイルの値 |
| `--skip-upload` | `-s`   | Notion アップロードをスキップ      | `False`          |
| `--debug`       | `-d`   | デバッグモードを有効化             | `False`          |
| `--help`        | `-h`   | ヘルプメッセージを表示             | -                |

### 実行例

```bash
# 基本実行（設定ファイルの内容で実行）
python scrape_and_save_tweets.py

# Twitterユーザー「elonmusk」の最新20件を取得
python scrape_and_save_tweets.py --mode target_only --target elonmusk --max 20

# キーワード「Python AI」で検索し、最大50件を取得してフィルタリング
python scrape_and_save_tweets.py --mode search_filtered --target "Python AI" --max 50

# アップロードせずにデータ取得のみ（テスト用）
python scrape_and_save_tweets.py --skip-upload
```

---

## 🎯 モード別詳細説明

### 1. `target_only` モード

特定の X ユーザーの投稿のみを取得します。

- **用途**: 特定インフルエンサーや企業の投稿モニタリング
- **手順**:

  1. 指定ユーザーのプロフィールページにアクセス
  2. 投稿一覧をスクロールして候補 URL 収集
  3. 各投稿の詳細ページから投稿内容と各種メトリクスを抽出
  4. スレッド・自リプライを関連投稿として抽出・マージ

- **設定例**:
  ```json
  {
    "mode": "target_only",
    "extract_target": "elonmusk",
    "max_tweets": 30
  }
  ```

### 2. `search_filtered` モード

キーワード検索結果からプロフィールや投稿内容でフィルタリングして取得します。

- **用途**: 特定キーワードに関する投稿の効率的発見と収集
- **手順**:

  1. 検索キーワードで X の検索ページにアクセス
  2. 検索結果からユーザーリストを抽出
  3. 各ユーザーのプロフィール（名前・bio）をフィルターキーワードと照合
  4. マッチしたユーザーの投稿をさらに内容フィルターキーワードで絞り込み
  5. 条件を満たす投稿を保存

- **設定例**:
  ```json
  {
    "mode": "search_filtered",
    "extract_target": "Python developer",
    "filter_keywords_name_bio": ["エンジニア", "プログラマー", "開発者"],
    "filter_keywords_tweet": ["採用", "求人", "募集中"]
  }
  ```

### 3. `search_all` モード

キーワード検索結果のすべての投稿を取得します（フィルタリングなし）。

- **用途**: 特定キーワードのすべての言及を網羅的に収集
- **手順**:

  1. 検索キーワードで X の検索ページにアクセス
  2. 検索結果からユーザーリストと投稿を抽出
  3. フィルタリングなしですべての投稿を保存

- **設定例**:
  ```json
  {
    "mode": "search_all",
    "extract_target": "新製品 発表",
    "max_tweets": 100
  }
  ```

### 4. `keyword_trend` モード

キーワードのトレンド/話題タブから投稿を取得します。

- **用途**: 特定キーワードの最新トレンドと人気投稿の収集
- **手順**:

  1. 検索キーワードで X の検索ページにアクセス
  2. 「話題」タブを選択
  3. トレンド投稿を抽出
  4. ユーザープロフィールでフィルタリング（オプション）

- **設定例**:
  ```json
  {
    "mode": "keyword_trend",
    "extract_target": "AI ニュース",
    "filter_keywords_name_bio": ["公式", "ニュース", "メディア"]
  }
  ```

---

## 📊 Notion 連携方法

### Notion API の設定

1. [Notion Developers](https://www.notion.so/my-integrations) ページでインテグレーション作成
2. インテグレーション名を入力し（例: `Tweet Collector`）、送信
3. 表示された `Internal Integration Token` を `config.json` の `notion_token` にコピー

### データベースの準備

1. Notion で新規データベースを作成（新規ページ → データベース → テーブル）
2. 以下のプロパティを追加:

| プロパティ名       | タイプ   | 説明                        |
| ------------------ | -------- | --------------------------- |
| `投稿ID`           | タイトル | ※必須。Tweet の一意の ID    |
| `本文`             | テキスト | 投稿の本文                  |
| `URL`              | URL      | 投稿の URL                  |
| `投稿日時`         | 日付     | 投稿された日時              |
| `ユーザー名`       | テキスト | 投稿者のユーザー名          |
| `アカウント名`     | テキスト | 投稿者の表示名              |
| `インプレッション` | 数値     | 閲覧数                      |
| `リポスト`         | 数値     | リポスト（RT）数            |
| `いいね`           | 数値     | いいね数                    |
| `ブックマーク`     | 数値     | ブックマーク数              |
| `リプライ`         | 数値     | 返信数                      |
| `メディア`         | URL      | 保存した画像・動画へのパス  |
| `親投稿ID`         | テキスト | スレッド時の親ツイート ID   |
| `OCR結果`          | テキスト | 画像から抽出したテキスト    |
| `GPT要約`          | テキスト | GPT による要約・カテゴリ    |
| `ステータス`       | セレクト | 処理状態（新規/確認済み等） |

3. `・・・` メニューから「接続を追加」で作成したインテグレーションとの接続を確立
4. データベースの URL から ID を取得:
   - URL の形式: `https://www.notion.so/{ワークスペース名}/{データベースID}?v=...`
   - この`{データベースID}`部分を`config.json`の`database_id`にコピー

### 処理済み ID データベースの設定（オプション）

1. 同様に新しいデータベースを作成
2. 以下のプロパティを追加:

| プロパティ名 | タイプ   | 説明                            |
| ------------ | -------- | ------------------------------- |
| `投稿ID`     | タイトル | ※必須。処理済みの TweetID       |
| `処理タイプ` | セレクト | 親投稿/リプライ/マージ済み等    |
| `処理日時`   | 日付     | 処理した日時                    |
| `親投稿ID`   | テキスト | 親ツイート ID（リプライの場合） |
| `URL`        | URL      | 投稿の URL                      |

3. データベース ID を`config.json`の`database_id_processed_posts`にコピー

---

## 🔄 URL 重複排除と最適化

スクリプトは以下の方法で効率的に重複を排除し、不要なページアクセスを削減します:

1. **URL ベースの事前フィルタリング**:

   - 収集段階で同一 URL を排除
   - 正規表現による投稿 ID の抽出と比較

2. **処理済み ID による最適化**:

   - 詳細ページアクセス前に処理済み ID と URL 内の ID を比較
   - 既知の ID はスキップし、不要なネットワークリクエストを削減

3. **収集上限の動的制御**:

   - 残りの必要投稿数に基づいて候補 URL 数を調整
   - `max_candidates_multiplier`で目標数に対する係数を設定可能

4. **インテリジェントスクロール制御**:

   - 新しい投稿が見つからない場合の動作をカスタマイズ可能
   - `pause_scroll_threshold`で新規投稿なしの許容回数を設定

5. **重複 ID グローバル管理**:
   - セッション内で処理済み ID を記録
   - 繰り返し実行時の効率向上

例:

```python
# 設定例: 残り必要数が少ない場合は少ない候補URLで処理
"max_candidates_multiplier": 1.2  # 必要数の1.2倍まで許容
"pause_scroll_threshold": 5       # 5回連続で新規投稿なしでも継続
```

---

## 📸 画像・動画の自動保存

### 保存される画像・動画

- 投稿に含まれる画像（最大 4 枚）
- 投稿に添付された動画（1 つのみ）
- GIF アニメーション

### 保存ディレクトリ構造

```
project/
├── images/
│   ├── 1234567890/           # 投稿IDごとのディレクトリ
│   │   ├── image_1.jpg
│   │   ├── image_2.jpg
│   │   └── ...
│   └── ...
└── videos/
    ├── 1234567890/
    │   └── video.mp4
    └── ...
```

### 保存設定

```json
{
  "save_media": true,           # メディア保存の有効/無効
  "image_min_width": 300,       # 保存する最小画像幅（ピクセル）
  "video_max_duration": 180,    # 保存する最大動画長（秒）
  "download_timeout": 30        # ダウンロードタイムアウト（秒）
}
```

### 画像フォーマット変換オプション

特定のフォーマットに変換して保存する場合:

```json
{
  "image_convert_format": "webp",  # webp/jpg/png等に変換
  "image_quality": 85              # 画質（1-100）
}
```

---

## 🔍 OCR 機能と自然言語処理

### 画像 OCR 機能

投稿画像からテキストを抽出する機能です。

- **使用技術**: OpenAI Vision API
- **対応言語**: 日本語、英語、その他多言語対応
- **設定方法**:
  ```json
  {
    "ocr_enabled": true,
    "openai_api_key": "sk-...",
    "ocr_model": "gpt-4-vision-preview"
  }
  ```

### 自然言語処理（分類・要約）

投稿内容と OCR 結果を分析し、カテゴリ分類や要約を行います。

- **使用技術**: OpenAI GPT API
- **可能な処理**:

  - 投稿カテゴリの自動分類
  - 要点の抽出
  - 商品情報の構造化
  - 感情分析

- **設定方法**:
  ```json
  {
    "use_gpt": true,
    "gpt_model": "gpt-4-1106-preview",
    "prompts_file": "prompt.txt",    # プロンプトテンプレートファイル
    "categorize_posts": true         # カテゴリ分類を有効化
  }
  ```

### サンプルプロンプトファイル

prompt.txt の例:

```
あなたはSNS投稿の本文と画像内の文字（OCR結果）の両方をもとに、投稿の内容を総合的に理解してください。

# 🎯 タスク

1. 以下の【投稿本文】と【画像OCR】を読み、投稿の内容を総合的に理解してください。
2. 投稿の内容から、最適なカテゴリ名（「求人情報」「商品紹介」「お知らせ」など）を判断してください。
3. 複数の画像OCR結果がある場合は、各OCR結果に❶❷❸などの番号を振り、内容を整理してください。
4. 画像が1枚のみの場合は番号を付けず、通常の文章として整形してください。
5. 意味不明な文字列（例：「104K 6.268」「wmmeuupurs」など）は削除して構いません。

出力形式:
---
カテゴリ: [判断したカテゴリ名]

[整形された内容]
---

# 📝 例

例1:
【投稿本文】求人情報です！詳細は画像をご確認ください。
【画像OCR】職種：Webエンジニア 給与：月30-50万円 勤務地：渋谷

出力:
---
カテゴリ: 求人情報

職種：Webエンジニア
給与：月30-50万円
勤務地：渋谷
---
```

---

## ❓ トラブルシューティング

### よくある問題と解決策

| 問題               | 原因                                                               | 解決策                                                                                        |
| ------------------ | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| ログインエラー     | ・アカウント情報の誤り<br>・X の仕様変更<br>・セキュリティチェック | ・accounts.json の情報を確認<br>・手動でログインし、Cookie を更新<br>・スクリプトの更新を確認 |
| スクロール停止     | ・新規投稿が見つからない<br>・ネットワークエラー                   | ・pause_scroll_threshold を増やす<br>・max_scrolls を増やす<br>・retry_delay を調整           |
| メディア取得エラー | ・ダウンロード失敗<br>・権限の問題                                 | ・download_timeout を増やす<br>・images/videos フォルダの権限確認                             |
| Notion 連携エラー  | ・トークン誤り<br>・データベース構造不一致                         | ・notion_token を確認<br>・データベースの列名とタイプを確認                                   |
| API 制限エラー     | ・X 側のレート制限<br>・OpenAI API 制限                            | ・実行間隔を空ける<br>・max_retries と retry_delay を調整                                     |

### デバッグモード

```bash
python scrape_and_save_tweets.py --debug
```

デバッグモードでは:

- 詳細なログが出力される
- 各ステップの中間データが保存される
- ブラウザが表示され操作が確認できる

### エラーログの確認

エラーが発生した場合は `log.txt` を確認してください。主なログメッセージ例:

```
🔍 スクロール 3/50 回目 (収集済み: 15/30)
🧊 このスクロールで新規投稿なし → pause_counter: 2/3
🚫 詳細ページアクセス前に重複排除: ID 1234567890 (残り対象: 25)
⚠️ 画像ダウンロード失敗: https://pbs.twimg.com/media/XXXXX - HTTPエラー 403
📊 現在の登録成功数: 12/30
```

---

## 📊 サンプル出力

### コンソール出力例

```
🔧 設定ファイル読み込み: config.json
📂 既存の処理済みIDをグローバルリストに読み込み中...
🔑 ログイン試行: アカウント xxx@gmail.com
✅ ログイン成功
✨ アクセス中: https://twitter.com/elonmusk
🔍 スクロール 1/50 回目 (収集済み: 0/30)
🔢 新規Tweet候補: 12件 (合計: 12件)
🔍 スクロール 2/50 回目 (収集済み: 12/30)
🔢 新規Tweet候補: 10件 (合計: 22件)
🔍 スクロール 3/50 回目 (収集済み: 22/30)
🔢 新規Tweet候補: 8件 (合計: 30件)
📈 収集候補のURL取得完了 → 合計: 30 件
ℹ️ extract_and_merge_tweets: 開始。処理対象URL候補数: 30, 目標登録数: 30, この関数内での候補収集上限: 45
🕵️ 投稿アクセス中: https://twitter.com/elonmusk/status/1234567890
✅ 投稿詳細取得完了: https://twitter.com/elonmusk/status/1234567890
🖼️ 画像ダウンロード: 2枚
📄 OCR実行中: ローカルパス /images/1234567890/image_1.jpg
📝 Notionにアップロード中: Tweet ID 1234567890
✅ アップロード成功: https://www.notion.so/xxxx
📊 現在の処理状況: 成功 1/30 | 処理済 1/30 | 残 29
...
📊 最終結果: 成功 28/30件 | 失敗 2/30件 | 処理時間: 153.2秒
✨ 処理完了しました
```

### Notion データベース表示例

| 投稿 ID    | 本文                    | URL                                  | 投稿日時   | いいね | GPT 要約                             |
| ---------- | ----------------------- | ------------------------------------ | ---------- | ------ | ------------------------------------ |
| 1234567890 | これは新しい製品...     | https://x.com/user/status/1234567890 | 2023-11-15 | 1,250  | 商品紹介: 新製品 X の発表について... |
| 2345678901 | 採用情報！エンジニア... | https://x.com/user/status/2345678901 | 2023-11-14 | 820    | 求人情報: Web エンジニア募集...      |

---

## 📝 更新履歴

### v1.3.0 (2023-11-15)

- URL 重複排除機能の強化
- 残り必要投稿数に応じた動的候補収集機能
- OCR 結果の番号付け表示機能
- 処理速度の最適化

### v1.2.0 (2023-11-01)

- Notion 処理済み ID データベースに URL 保存機能追加
- インテリジェントスクロール制御
- 処理時間測定機能

### v1.1.0 (2023-10-15)

- OCR 機能と GPT 要約機能の追加
- エラー耐性の強化
- キーワードフィルタリング機能の改善
