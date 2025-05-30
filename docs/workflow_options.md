# ワークフロー運用オプション - 2アカウント vs 6アカウント

## 📊 現在のワークシート構成
```
1. 都内メンエス
2. 都内セクキャバ  
3. 大阪メンエス
4. 名古屋メンエス
5. 広島風俗
6. 銀座キャバ
```

## 💰 オプション1: 2アカウント運用（コスト重視）

### 🔧 設定方法
既存の `jadiAngkat` と `hinataHHHHHH` で全ワークシートを管理

```yaml
twitter_accounts:
  - account_id: "jadiAngkat"
    username: "jadiAngkat"
    email: "${{ secrets.ACCOUNT1_EMAIL }}"
    consumer_key: "${{ secrets.ACCOUNT1_CONSUMER_KEY }}"
    consumer_secret: "${{ secrets.ACCOUNT1_CONSUMER_SECRET }}"
    access_token: "${{ secrets.ACCOUNT1_ACCESS_TOKEN }}"
    access_token_secret: "${{ secrets.ACCOUNT1_ACCESS_TOKEN_SECRET }}"
    google_sheets_source:
      enabled: true
      worksheet_names: ["都内メンエス", "大阪メンエス", "名古屋メンエス"]
  - account_id: "hinataHHHHHH"
    username: "hinataHHHHHH"
    email: "${{ secrets.ACCOUNT2_EMAIL }}"
    consumer_key: "${{ secrets.ACCOUNT2_CONSUMER_KEY }}"
    consumer_secret: "${{ secrets.ACCOUNT2_CONSUMER_SECRET }}"
    access_token: "${{ secrets.ACCOUNT2_ACCESS_TOKEN }}"
    access_token_secret: "${{ secrets.ACCOUNT2_ACCESS_TOKEN_SECRET }}"
    google_sheets_source:
      enabled: true
      worksheet_names: ["都内セクキャバ", "広島風俗", "銀座キャバ"]
```

### ✅ メリット
- **必要なSecrets**: 2セットのみ（ACCOUNT1_*, ACCOUNT2_*）
- **コスト削減**: Twitter API利用料が2アカウント分
- **管理簡単**: アカウント数が少ない

### ❌ デメリット
- **投稿頻度制限**: 1アカウントで3ワークシート分の投稿
- **リスク集中**: アカウント停止時の影響が大きい

---

## 🎯 オプション2: 6アカウント運用（専門性重視）

### 🔧 設定方法
各ワークシートに専用のTwitterアカウントを設定

```yaml
twitter_accounts:
  - account_id: "jadiAngkat"
    worksheet_name: "都内メンエス"
  - account_id: "hinataHHHHHH"
    worksheet_name: "都内セクキャバ"
  - account_id: "osaka_mens"
    worksheet_name: "大阪メンエス"
  - account_id: "nagoya_mens"
    worksheet_name: "名古屋メンエス"
  - account_id: "hiroshima_fuzoku"
    worksheet_name: "広島風俗"
  - account_id: "ginza_kyaba"
    worksheet_name: "銀座キャバ"
```

### ✅ メリット
- **専門性**: 各エリア/業種に特化したアカウント
- **投稿頻度**: 各アカウントで独立した投稿スケジュール
- **リスク分散**: 1アカウント停止の影響が限定的

### ❌ デメリット
- **必要なSecrets**: 6セット（ACCOUNT1_*〜ACCOUNT6_*）
- **コスト増**: Twitter API利用料が6アカウント分
- **管理複雑**: アカウント管理の手間

---

## 🔧 コード修正版（2アカウント運用）

### auto_post_bot.pyの修正が必要
現在のコードは1アカウント1ワークシートの設計のため、1アカウントで複数ワークシートを処理するには修正が必要です。

```python
# 修正例: 1アカウントで複数ワークシートを処理
for account in accounts:
    worksheet_names = account.get('worksheet_names', [account.get('worksheet_name')])
    for worksheet_name in worksheet_names:
        # 各ワークシートを処理
        process_worksheet(account, worksheet_name)
```

---

## 💡 推奨運用方法

### 🎯 段階的導入アプローチ
```
Phase 1: 2アカウント運用でスタート
- jadiAngkat: 都内メンエス、大阪メンエス、名古屋メンエス
- hinataHHHHHH: 都内セクキャバ、広島風俗、銀座キャバ

Phase 2: 必要に応じて専用アカウント追加
- 投稿量が多いワークシートから専用アカウント化
- 段階的に6アカウント体制に移行
```

### 🔍 判断基準
```
2アカウント運用が適している場合：
✅ 投稿頻度が少ない（1日3-5投稿/ワークシート）
✅ コスト重視
✅ 管理リソースが限られている

6アカウント運用が適している場合：
✅ 投稿頻度が高い（1日10投稿以上/ワークシート）
✅ エリア/業種ごとの専門性重視
✅ リスク分散重視
```

---

## ⚙️ 実装手順

### 2アカウント運用を選択する場合
1. 現在のワークフローのアカウント設定を2つに削減
2. auto_post_bot.pyを複数ワークシート対応に修正
3. 必要なSecretsを2セットのみ設定

### 6アカウント運用を選択する場合
1. 現在のワークフロー設定をそのまま利用
2. 追加の4アカウントのAPIキーを取得
3. 必要なSecretsを6セット設定

どちらの運用方法を選択されますか？ 