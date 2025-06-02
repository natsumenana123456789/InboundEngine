# GitHub Actions による自動実行

このプロジェクトは、GitHub Actions を利用して投稿のスケジューリングと実行を自動化できます。

## ワークフローファイル

自動化の定義は `.github/workflows/auto-post-bot.yml` に記述されています。
このワークフローは主に以下のジョブを実行します。

*   **`notify-update`**: `main` ブランチにプッシュがあった場合に、Discordへ更新通知を送信します。
*   **`schedule`**: 定期的に（デフォルトでは毎日JST午前8時）翌日の投稿スケジュールを生成します。
    *   実行コマンド: `python main.py --generate-schedule --date $(date -u -d "+1 day" +%Y-%m-%d) --info`
*   **`schedule-now`**: 手動実行時専用。現在の時刻を基準にその日の投稿スケジュールを強制的に再生成します。
    *   実行コマンド: `python main.py --generate-schedule --date $(date -u +%Y-%m-%d) --force-regenerate --info`
*   **`post`**: 定期的に（デフォルトでは毎日JST 10時, 14時, 18時, 21時）スケジュールされた投稿を実行します。
    *   実行コマンド: `python main.py --process-now --date $(date -u +%Y-%m-%d) --info`

各ジョブでは、まずリポジトリをチェックアウトし、Python環境をセットアップ、依存関係をインストールした後、`config/config.template.yml` とGitHub Secretsに設定された環境変数を使って `config/config.yml` を生成し、`gspread-key.json` を作成してから `main.py` を実行します。

## 必要なSecrets

ワークフローが正しく動作するためには、リポジトリの `Settings > Secrets and variables > Actions` で以下のSecretsを設定する必要があります。
詳細は [CONFIGURATION.md](./CONFIGURATION.md) を参照してください。

## 自動実行スケジュール 📅

デフォルトのスケジュールは以下の通りです（JST基準）：

*   **スケジュール生成**: 毎日午前8時 (UTC 23:00)
    *   コマンド: `python main.py --generate-schedule --date $(date -u -d "+1 day" +%Y-%m-%d)`
*   **投稿実行**: 毎日午前10時, 午後2時, 午後6時, 午後9時 (UTC 1:00, 5:00, 9:00, 12:00)
    *   コマンド: `python main.py --process-now --date $(date -u +%Y-%m-%d)`

これらのスケジュールは `.github/workflows/auto-post-bot.yml` 内の `on.schedule.cron` 設定で変更可能です。

## 手動実行オプション 🔧

GitHubリポジトリの「Actions」タブから `Auto Post Bot with Scheduler` ワークフローを選択し、「Run workflow」ボタンをクリックすることで、手動で特定のジョブをトリガーできます。

手動実行時には、以下のいずれかのアクションを選択できます:
*   `post`: 現在のスケジュールに基づいて投稿を実行します。
*   `schedule`: 翌日のスケジュールを生成します。
*   `schedule-now`: 現在の時刻を基準に、その日のスケジュールを強制的に再生成します。

## Discord通知の詳細 📱

設定されたDiscord Webhook URLを通じて、以下のような通知が送信されます。

**📢 Git Push通知:**
```
🔄 スクリプトが更新されました。
Repository: [リポジトリ名]
Commit: [コミットメッセージ]
Author: [コミット作成者]
Branch: [ブランチ名]
```

**📅 スケジュール生成通知:**
```text
📝 スケジュール生成完了 (YYYY-MM-DD)
次の投稿予定:
- Account_A: YYYY-MM-DD HH:MM
- Account_B: YYYY-MM-DD HH:MM
```

**✅ 投稿完了通知:**
```text
✅ 投稿完了: Account_X
投稿内容: 「ここにツイートの冒頭部分...」
```

**⚠️ エラー通知:**
```text
❌ エラー発生: Account_Y
処理: [例: ツイート投稿]
エラー内容: [エラーメッセージの詳細]
```
*注意: 上記の通知メッセージのフォーマットは、実際のスクリプト内の通知ロジックによって異なる場合があります。* 