# InboundEngine プロジェクト

## 概要

このプロジェクトは、複数の自動化ボット（キュレーション、自動投稿など）を管理・実行するためのシステムです。

## プロジェクト構成

主要なコンポーネントは以下の通りです。

- **bots**: 各種ボットのソースコードが格納されています。
    - **curate_bot**: コンテンツのキュレーションを行うボットです。詳細は `bots/curate_bot/README.md` を参照してください。
    - **auto_post_bot**: 自動でSNSなどに投稿を行うボットです。詳細は `bots/auto_post_bot/README.md` を参照してください。
    - **analyze_bot**: 分析関連の処理を行うボットです。詳細は `bots/analyze_bot/README.md` を参照してください。（現在、内容は未実装または確認中です）
- **config**: プロジェクト全体及び各ボットの設定ファイルを管理します。
    - `settings.json`: 主要な設定ファイル。詳細は後述します。
    - `gspread-key.json`: Google Sheets API連携用の認証キーファイル。（このファイル名は `settings.json` 内で指定可能）
- **utils**: ボット間で共通利用されるユーティリティ関数（ロガー、WebDriver操作など）を格納します。
- **tests**: 各モジュールのユニットテストを格納します。
- **docker**: Docker関連の設定ファイル（Dockerfileなど）を管理します。

## 設定ファイル (`config/settings.json`) について

このプロジェクトの動作は、主に `config/settings.json` ファイルによって制御されます。以下に主要な設定項目を示します。詳細な設定オプションについては、各ボットのREADMEやソースコード内のコメントも参照してください。

### `common` セクション (全ボット共通設定)
- `log_level`: ログ出力のレベル (例: "INFO", "DEBUG")。
- `file_paths`:
    - `google_key_file`: Google API関連の認証キーファイル名 (例: "gspread-key.json")。`config` ディレクトリ内に配置します。
- `default_user_agents`: WebDriverが使用するデフォルトのUser-Agent文字列のリスト。ここからランダムに選択されます。

### `curate_bot` セクション (キュレーションボット設定)
- `enabled`: ボットの有効/無効 (true/false)。
- `twitter_accounts`: Twitterアカウント情報のリスト。
    - `account_id`: アカウントの一意なID。
    - `email`, `username`, `password`: Twitterの認証情報。
    - `profile_name_suffix`: WebDriverのプロファイル名に使われる接尾辞。
- `active_curation_account_id`: `twitter_accounts` の中から実際に使用するアカウントのID。
- `user_agents`: `curate_bot` 専用のUser-Agentリスト。指定がない場合は `common.default_user_agents` を使用。
- `scraping`: スクレイピング関連の設定。
    - `extract_target`: 収集対象の識別子 (例: "YahooNewsTopics")。
    - `max_tweets`: 一度に収集する最大ツイート数。
    - `save_media_to_gdrive`: Google Driveへのメディア保存の有効/無効。
    - `ocr_enabled`: 画像内文字のOCR処理の有効/無効。
- `notion`: Notion連携設定。
    - `token`: Notion APIトークン。
    - `databases`: 使用するNotionデータベースIDのマッピング (例: `{"curation_main": "YOUR_DB_ID"}` )。
- `google_drive`: Google Drive連携設定。
    - `enabled`: Google Drive利用の有効/無効。
    - `folder_id`: 保存先のGoogle DriveフォルダID。

### `auto_post_bot` セクション (自動投稿ボット設定)
- `enabled`: ボットの有効/無効 (true/false)。
- `source`: 投稿データの取得元 ("google_sheets", "direct_input" など)。
- `twitter_accounts`: Twitterアカウント情報のリスト ( `curate_bot` と同様の構造)。
- `active_autopost_account_id`: 使用するTwitterアカウントのID。
- `user_agents`: `auto_post_bot` 専用のUser-Agentリスト。
- `posting_settings`: 投稿に関する設定。
    - `char_limit`: 投稿文字数制限 (min, max)。
    - `video_download_filename`: 一時保存する動画ファイル名。
    - `min_interval_seconds`, `max_interval_seconds`: 連続投稿時の待機時間（秒）。
    - `use_selenium_fallback`: APIでの投稿失敗時にSelenium経由で再試行するかの設定。
- `google_sheets_source`: `source` が "google_sheets" の場合の設定。
    - `enabled`: Google Sheets利用の有効/無効。
    - `sheet_name`: スプレッドシート名。
    - `worksheet_name`: ワークシート名。
    - `columns`: 読み込む列名のリスト。
- `scheduler` (現在 `auto_post_bot` 内では直接使用されていませんが、将来的な定期実行用設定)

### `analyze_bot` セクション (分析ボット設定)
- `enabled`: ボットの有効/無効。 (現在は機能未実装の想定)

**注意:**
- `YOUR_...` となっている箇所は、実際の値に置き換える必要があります。
- 特にAPIトークンやパスワードなどの機密情報は慎重に扱ってください。

## セットアップ

基本的なセットアップ手順は以下の通りです。（詳細は各ボットのREADMEを参照してください）

1. リポジトリをクローンします。
2. 必要な依存関係をインストールします。（ルート及び各ボットディレクトリの `requirements.txt` を参照）
3. `config/settings.json` をサンプルや上記のガイドを参考に作成・編集します。特にAPIキーや認証情報を正しく設定してください。
4. (オプション) Google DriveやGoogle Sheets連携を利用する場合は、`config/gspread-key.json` を `config` ディレクトリに配置してください。 (ファイル名は `settings.json` で指定したものに合わせます)

## 注意事項

- 各ボットは独立して実行されることを想定しています。
- 設定ファイルや認証情報の取り扱いには十分注意してください。 