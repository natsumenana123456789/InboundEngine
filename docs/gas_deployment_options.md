# 📱 Google Apps Script デプロイ方法

## 🎯 現在の状態と選択肢

### 現在の方式：手動コピペ
```
Git Repository (src/google_apps_script/form_processor.js)
         ↓ (手動コピペ)
Google Apps Script Editor
         ↓
実行環境
```

### 自動化の選択肢
1. **clasp CLI使用**（推奨）
2. **GitHub Actions自動デプロイ**
3. **Apps Script API使用**

---

## 🔧 Option 1: clasp CLI使用（推奨）

### claspとは
```
✅ GoogleのGoogle Apps Script公式CLI
✅ ローカル開発環境とGASを同期
✅ `clasp push`で自動デプロイ
✅ `clasp pull`でGASから取得
```

### 1-1. clasp初期設定

```bash
# Node.js環境でclaspをインストール
npm install -g @google/clasp

# Googleアカウントでログイン
clasp login

# 既存のGASプロジェクトと連携
clasp clone <SCRIPT_ID>
```

### 1-2. プロジェクト構成
```
InboundEngine/
├── src/google_apps_script/
│   ├── .clasp.json          # clasp設定ファイル
│   ├── appsscript.json      # GAS設定ファイル
│   └── form_processor.js    # メインコード
└── ...
```

### 1-3. .clasp.json設定
```json
{
  "scriptId": "あなたのGASプロジェクトID",
  "rootDir": "./src/google_apps_script",
  "projectId": "あなたのGCPプロジェクトID"
}
```

### 1-4. デプロイコマンド
```bash
# コードをGASにプッシュ
cd src/google_apps_script
clasp push

# 自動でGASエディタに反映される
```

---

## 🤖 Option 2: GitHub Actions自動デプロイ

### 2-1. ワークフローファイル作成
```yaml
# .github/workflows/deploy-gas.yml
name: 🚀 Deploy Google Apps Script

on:
  push:
    branches: [main]
    paths: ['src/google_apps_script/**']
  workflow_dispatch:

jobs:
  deploy-gas:
    runs-on: ubuntu-latest
    
    steps:
    - name: 📥 Checkout
      uses: actions/checkout@v4
    
    - name: 🟢 Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'
    
    - name: 📦 Install clasp
      run: npm install -g @google/clasp
    
    - name: 🔐 Setup Google credentials
      run: |
        echo '${{ secrets.CLASP_CREDENTIALS }}' > ~/.clasprc.json
    
    - name: 🚀 Deploy to Google Apps Script
      run: |
        cd src/google_apps_script
        clasp push --force
      env:
        SCRIPT_ID: ${{ secrets.GAS_SCRIPT_ID }}
```

### 2-2. 必要なSecrets
```bash
# GitHub Secrets に追加
CLASP_CREDENTIALS='{"token":{"access_token":"...","refresh_token":"...",...}}'
GAS_SCRIPT_ID='あなたのGASプロジェクトID'
```

### 2-3. 動作フロー
```
Git push → GitHub Actions → clasp push → GAS自動更新
```

---

## 🔧 Option 3: Apps Script API使用

### 3-1. カスタムデプロイスクリプト
```python
# deploy_gas.py
import requests
import json
import os

def deploy_to_gas():
    # Apps Script APIを使用してデプロイ
    script_id = os.getenv('GAS_SCRIPT_ID')
    access_token = os.getenv('GOOGLE_ACCESS_TOKEN')
    
    with open('src/google_apps_script/form_processor.js', 'r') as f:
        code_content = f.read()
    
    # API経由でコード更新
    # 実装詳細は省略
```

---

## 🎯 推奨アプローチ：段階的導入

### Phase 1: 手動コピペ（現在）
```
✅ すぐに開始可能
✅ 設定が簡単
❌ 手動作業が必要
❌ ヒューマンエラーの可能性
```

### Phase 2: clasp導入
```bash
# ローカルでclaspセットアップ
npm install -g @google/clasp
clasp login
clasp clone <SCRIPT_ID>

# 以降は clasp push でデプロイ
```

### Phase 3: GitHub Actions自動化
```yaml
# 完全自動化
# Git push → 自動でGAS更新
```

---

## 🛠️ 実際の導入手順（clasp版）

### Step 1: claspインストール
```bash
# Node.js環境が必要
npm install -g @google/clasp
```

### Step 2: Google認証
```bash
# ブラウザでGoogle認証
clasp login
```

### Step 3: 既存GASプロジェクトと連携
```bash
# あなたのGASプロジェクトIDを取得
# GASエディタのURL: https://script.google.com/d/{SCRIPT_ID}/edit
clasp clone 1BxKxvRF_pRo2oEoGs6...（あなたのSCRIPT_ID）
```

### Step 4: ファイル構成調整
```bash
# claspが生成したファイルを移動
mv Code.js src/google_apps_script/form_processor.js
mv appsscript.json src/google_apps_script/
mv .clasp.json src/google_apps_script/
```

### Step 5: デプロイテスト
```bash
cd src/google_apps_script
clasp push
```

### Step 6: 確認
```bash
# GASエディタで更新されているか確認
clasp open
```

---

## 📋 現在のおすすめ運用

### 🚀 今すぐ始める場合
```
1. 手動コピペでスタート
2. 動作確認後にclasp導入検討
3. 慣れてきたらGitHub Actions自動化
```

### 💡 理由
```
✅ 学習コストを段階的に分散
✅ 動作確認を最優先
✅ 後から自動化追加が可能
✅ 初期の複雑性を回避
```

---

## 🔄 各方式の比較

| 方式 | 設定難易度 | 自動化 | メンテナンス | 推奨度 |
|------|------------|--------|--------------|--------|
| 手動コピペ | ⭐ 簡単 | ❌ なし | ⭐ 簡単 | 🥉 初期 |
| clasp CLI | ⭐⭐ 中程度 | ⭐⭐ 手動実行 | ⭐⭐ 中程度 | 🥇 推奨 |
| GitHub Actions | ⭐⭐⭐ 複雑 | ⭐⭐⭐ 完全自動 | ⭐⭐⭐ 複雑 | 🥈 上級者 |

## 🎉 結論

**現在は手動コピペで問題ありません！**

動作確認が完了し、運用が安定してきたらclaspを導入することをお勧めします。Git管理の利点は既に享受できているので、デプロイの自動化は次のステップとして考えましょう。 