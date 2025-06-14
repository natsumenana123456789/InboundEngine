# トラブルシューティングとFAQ

このセクションでは、アプリケーションの利用中に発生する可能性のある一般的な問題とその解決策、よくある質問への回答を提供します。

## よくある質問（FAQ）

### Q: 投稿が実行されないのですが？
**A**: 以下を確認してください：
1.  **設定ファイル**: `config/config.yml` が正しく設定されているか確認してください。特に、APIキーやスプレッドシートIDが正確であるか確認します。
2.  **スプレッドシート**: 
    *   投稿データがスプレッドシートに正しく入力されているか（「本文」が空でないか、「投稿可能」が `TRUE` になっているかなど）。
    *   スプレッドシートの共有設定が正しく、サービスアカウントに編集権限が付与されているか。
3.  **スケジュール**: 
    *   `python main.py --generate-schedule` を実行してスケジュールが生成されているか確認してください。生成されたスケジュールは `logs/schedule.json` （または設定ファイルで指定したパス）に保存されます。
    *   スケジュールファイル内の投稿時刻が適切か確認してください。
4.  **ログファイル**: `logs/app.log` （または設定ファイルで指定したパス）にエラーメッセージが出力されていないか確認してください。
5.  **認証情報**: Google Cloud Platformのサービスアカウントキー (`gspread-key.json`) が有効で、正しい場所に配置されているか確認してください。

### Q: 同じ投稿が何度も実行されます
**A**: 
*   `logs/executed_posts.log` ファイル（または設定ファイルで指定した実行済みログファイル名）を確認してください。ここに投稿済みの情報が記録され、再投稿を防ぎます。
*   スプレッドシートの「最終投稿日時」列と「投稿済み回数」列がボットによって正しく更新されているか確認してください。更新されていない場合、Google Sheets APIの権限設定に問題がある可能性があります。
*   複数のプロセスやワークフローが同時に `main.py --process-now` を実行していないか確認してください。

### Q: 動画投稿でエラーが出ます
**A**: 
1.  **FFmpeg**: 動画の処理（特にTwitter API v1.1で必要な場合がある形式変換など）のためにFFmpegがシステムにインストールされ、PATHが通っているか確認してください。GitHub Actions環境では、ワークフロー内でインストールステップが実行されているか確認します。
2.  **ファイルサイズと形式**: TwitterのAPIにはアップロードできる動画のファイルサイズや形式に制限があります。これらを確認してください。
3.  **URLの有効性**: `画像/動画URL` 列に記載されたURLが直接アクセス可能で、有効な動画ファイルを指しているか確認してください。

### Q: Discord通知が来ません
**A**: 
1.  `config/config.yml` 内の `auto_post_bot.discord_notification.webhook_url` が正しく設定されているか確認してください。
2.  Discordサーバー側でWebhookが無効になっていないか確認してください。
3.  ネットワーク接続やファイアウォールの設定がDiscordへのアクセスをブロックしていないか確認してください。

### Q: スケジュールが生成されません / 意図した通りに生成されません
**A**: 
1.  `config/config.yml` の `schedule_settings` を確認してください。特に `start_hour`, `end_hour`, `min_interval_minutes` の設定が適切か確認します。
2.  スプレッドシートに投稿可能な（「投稿可能」がTRUE）かつ未投稿または十分に時間が経過した投稿があるか確認してください。
3.  ログファイル (`logs/app.log`) でエラーや警告が出ていないか確認してください。

### Q: PCを移動したり、環境を変更したら動作しなくなりました
**A**: 
1.  **Python環境**: 新しい環境にもPythonが正しくインストールされ、必要なバージョン（3.8以上推奨）であることを確認してください。
2.  **仮想環境**: 仮想環境を使用している場合は、新しい環境で再度作成・有効化し、依存関係をインストール (`pip install -r requirements.txt`) し直してください。
3.  **ファイルパス**: `config/config.yml` 内のファイルパス（特に `logs_directory` や `google_key_file`）が新しい環境でも正しいか確認してください。絶対パスではなく相対パスを使用している場合、実行時のカレントディレクトリに注意してください。
4.  **認証情報**: `config/gspread-key.json` が正しい場所にあり、内容が破損していないか確認してください。
5.  **既存ファイル**: `logs/schedule.json` や `logs/executed_posts.log` などのデータファイルが新しい環境に正しく移行されているか確認してください。

### Q: 投稿順序を変更したい
**A**: スプレッドシートの「最終投稿日時」列を編集することで、投稿順序を制御できます。この列の日付が古い投稿、または空欄の投稿が優先的に選択されます。

### Q: 複数アカウントを同時実行したい
**A**: 現在のスクリプト (`main.py`) は、設定されたアカウントの投稿を順次処理します。複数のアカウントの投稿を厳密に同時に（並列で）実行する機能は標準では提供されていません。そのような機能が必要な場合は、スクリプトの改修や、複数のインスタンスを異なる設定で実行するなどの対応が必要です。

## ログの確認

問題が発生した場合、まずログファイルを確認することが重要です。

*   **アプリケーションログ**: `logs/app.log` (または `config.yml` で指定されたパス) に記録されます。エラーメッセージや処理の詳細な情報が含まれます。
*   **GitHub Actionsログ**: GitHub Actionsでジョブが失敗した場合、ワークフローの実行ログを確認してください。各ステップの出力やエラーメッセージが表示されます。

## その他の問題

上記以外で問題が解決しない場合は、以下の情報を添えてIssueを作成するか、開発者に連絡してください。

*   実行環境 (OS、Pythonバージョンなど)
*   エラーメッセージの全文 (ログファイルからの抜粋など)
*   問題が発生した際の具体的な手順
*   `config.yml` の関連する設定内容 (APIキーなどの機密情報はマスキングしてください) 