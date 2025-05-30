# スマホ対応投稿フォーム完全セットアップガイド
**フォーム作成 → スプレッドシート連携 → 動画変換 完全版**

## 🎯 概要
スマホから簡単に複数投稿をストックできるGoogle Formsを作成し、既存スプレッドシートに自動追加、画像を1秒動画に変換する完全自動化システムの構築手順です。

### 📱 対応アカウント
- **🏪 都内メンエス** (@ZaikerLong)
- **🍷 都内セクキャバ** (@hinataMaking)

### 🔧 対象スプレッドシート
**ID**: `1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA`  
**URL**: https://docs.google.com/spreadsheets/d/1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA/edit

---

## 📋 STEP 1: Google Formsの作成

### 1-1. 新しいフォームを作成
1. **Google Forms** にアクセス: https://forms.google.com
2. 右下の **「+」** ボタンをクリック
3. フォームタイトルを設定:
   ```
   📱 投稿ストック入力フォーム
   ```
4. 説明欄に入力:
   ```
   スマホから簡単に複数投稿をストックできます
   ```

### 1-2. セクション1: アカウント選択
1. **最初の質問を編集**:
   - 質問: `投稿アカウントを選択`
   - タイプ: **ラジオボタン**
   - 選択肢:
     ```
     🏪 都内メンエス
     🍷 都内セクキャバ
     ```
   - **必須** にチェック

2. **条件分岐を設定**:
   - 質問の右下「⋮」→「回答に応じてセクションに移動」
   - 🏪 都内メンエス → セクション2に移動
   - 🍷 都内セクキャバ → セクション2に移動

### 1-3. セクション2: 投稿内容入力
1. **新しいセクションを追加**:
   - 左下「セクションを追加」をクリック
   - セクションタイトル: `📝 投稿内容を入力`

2. **投稿本文の質問**:
   - 質問: `投稿本文`
   - タイプ: **段落**
   - 説明: `投稿したい内容を入力してください`
   - **必須** にチェック

3. **画像/動画アップロード**:
   - 「+」ボタンで質問追加
   - 質問: `画像・動画ファイル`
   - タイプ: **ファイルのアップロード**
   - 設定:
     - ファイル数: 複数のファイル
     - ファイルタイプ: 画像、動画
     - 最大ファイル数: 10
     - 最大ファイルサイズ: 100MB

4. **次の投稿への分岐**:
   - 「+」ボタンで質問追加
   - 質問: `他にも投稿を追加しますか？`
   - タイプ: **ラジオボタン**
   - 選択肢:
     ```
     ✅ はい、もう1つ追加
     ❌ いいえ、送信する
     ```

5. **条件分岐設定**:
   - ✅ はい、もう1つ追加 → セクション3に移動
   - ❌ いいえ、送信する → フォームを送信

### 1-4. セクション3以降: 追加投稿（必要に応じて）
セクション2をコピーして、セクション3、4、5...を作成。最大10投稿まで対応可能にする。

### 1-5. フォーム全体設定
1. **設定ボタン（⚙️）** をクリック
2. **プレゼンテーション** タブ:
   - ✅ 進行状況バーを表示
   - ✅ リンクを短縮

3. **回答** タブ:
   - **回答** タブをクリック
   - 右上の **📊 スプレッドシートアイコン** をクリック
   - **「既存のスプレッドシートを選択」** を選択
   - スプレッドシートを検索またはURLで指定: 
     ```
     https://docs.google.com/spreadsheets/d/1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA/edit
     ```
   - **「選択」** をクリック

   **📝 見つからない場合の手順：**
   1. **回答** タブで **「スプレッドシートを作成」** をクリック
   2. 新しいスプレッドシートが作成される
   3. 後でそのスプレッドシートからデータを既存シートにコピー
   
   **🔄 または、スプレッドシート側から連携：**
   1. 対象スプレッドシートを開く
   2. **挿入** → **フォーム** → **新しいフォーム**
   3. 作成されたフォームを編集して設定

---

## 📊 STEP 2: スプレッドシート連携設定

### 2-1. スプレッドシートの確認
1. 対象スプレッドシートを開く
2. **ワークシート構成を確認**:
   - 都内メンエス
   - 都内セクキャバ

3. **列構成を確認**:
   ```
   【都内メンエス・都内セクキャバシート】
   A列: 行番号
   B列: 投稿内容
   C列: 文字数
   D列: ファイルID
   E列: 投稿可能（チェックボックス）
   F列: アカウント数
   G列: 番号
   
   【Form_Responses1シート】
   A列: タイムスタンプ
   B列: 書き込むシート
   C列: 1投稿の内容  
   D列: 画像をアップロード
   E列: 更に投稿を追加しますか
   ```

   **⚠️ 重要：B列削除前の対応**
   - 既存の「質問投稿」列（B列）を削除する前に、まずこのガイドのApps Scriptを設定してください
   - 削除後は列が1つずつ前にズレるため、既存の自動投稿システムに影響しません
   - `config_loader.py`はヘッダー名で列を識別するため、列位置が変わっても問題ありません

   **🚨 config.yml の列設定を更新する必要があります**
   
   `config/config.yml` の `columns` 設定から「投稿タイプ」を削除してください：
   
   **修正前：**
   ```yaml
   columns: ["ID", "投稿タイプ", "最終投稿日時", "文字数", "本文", "画像/動画URL", "投稿可能", "投稿済み回数"]
   ```
   
   **修正後：**
   ```yaml
   columns: ["ID", "最終投稿日時", "文字数", "本文", "画像/動画URL", "投稿可能", "投稿済み回数"]
   ```
   
   この設定は現在使用されていませんが、将来の機能拡張時に影響する可能性があります。

### 2-2. Google Apps Scriptの設定
1. スプレッドシートで **拡張機能** → **Apps Script**
2. 新しいプロジェクトを作成
3. 以下のコードを貼り付け:

```javascript
// フォーム送信時の自動処理
function onFormSubmit(e) {
  try {
    console.log('フォーム送信処理開始');
    
    // フォーム回答の取得
    const responses = e.values;
    console.log('フォーム回答:', responses);
    
    // 基本情報の取得
    const timestamp = responses[0];
    const account = responses[1]; // 書き込むシート（都内メンエス or 都内セクキャバ）
    
    console.log('タイムスタンプ:', timestamp);
    console.log('選択アカウント:', account);
    
    // アカウントに対応するシート名を決定
    let sheetName;
    if (account.includes('都内メンエス')) {
      sheetName = '都内メンエス';
    } else if (account.includes('都内セクキャバ')) {
      sheetName = '都内セクキャバ';
    } else {
      console.error('不明なアカウント:', account);
      return;
    }
    
    console.log('対象シート:', sheetName);
    
    // スプレッドシートとワークシートの取得
    const spreadsheet = SpreadsheetApp.openById('1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA');
    const sheet = spreadsheet.getSheetByName(sheetName);
    
    if (!sheet) {
      console.error('シートが見つかりません:', sheetName);
      return;
    }
    
    // 投稿データの処理
    let dataIndex = 2; // 3列目から投稿データ開始
    
    while (dataIndex < responses.length) {
      const postContent = responses[dataIndex]; // 投稿内容
      const fileUrls = responses[dataIndex + 1]; // 画像アップロード
      const morePost = responses[dataIndex + 2]; // 追加投稿の有無
      
      console.log('投稿内容:', postContent);
      console.log('ファイルURL:', fileUrls);
      
      if (postContent && postContent.trim() !== '') {
        
        // 次の行番号を取得
        const lastRow = sheet.getLastRow();
        const nextRowNumber = lastRow + 1;
        
        // 文字数をカウント
        const charCount = postContent.length;
        
        // ファイルIDを処理
        let fileId = '';
        if (fileUrls) {
          fileId = processFileUrls(fileUrls);
        }
        
        // 既存の構造に合わせて追加
        const newRow = [
          nextRowNumber - 1,          // A列: 行番号
          postContent,               // B列: 投稿内容
          charCount,                 // C列: 文字数
          fileId,                    // D列: ファイルID
          false,                     // E列: 投稿可能（チェックボックス、初期値false）
          2,                         // F列: アカウント数（デフォルト2）
          nextRowNumber - 1          // G列: 番号
        ];
        
        sheet.appendRow(newRow);
        console.log('データ追加完了:', newRow);
      }
      
      // 次の投稿に進む
      if (morePost && morePost.includes('いいえ')) {
        break;
      }
      
      dataIndex += 3; // 次の投稿セットに移動
    }
    
    console.log('フォーム送信処理完了');
    
  } catch (error) {
    console.error('エラー発生:', error);
  }
}

// ファイルURLの処理（ファイルIDのみ抽出）
function processFileUrls(fileUrls) {
  if (!fileUrls) return '';
  
  try {
    // ファイルURLを配列に変換
    let urls = [];
    if (typeof fileUrls === 'string') {
      // カンマ区切りまたは改行区切りで分割
      urls = fileUrls.split(/[,\n]/).map(url => url.trim());
    } else if (Array.isArray(fileUrls)) {
      urls = fileUrls;
    }
    
    const fileIds = [];
    
    for (let url of urls) {
      if (url && url.includes('drive.google.com')) {
        // Google DriveのURLからファイルIDを抽出
        const fileId = extractFileId(url);
        if (fileId) {
          fileIds.push(fileId);
        }
      }
    }
    
    // 複数ファイルの場合はカンマ区切りで結合
    return fileIds.join(',');
    
  } catch (error) {
    console.error('ファイルURL処理エラー:', error);
    return '';
  }
}

// ファイルIDの抽出
function extractFileId(url) {
  const match = url.match(/\/file\/d\/([a-zA-Z0-9-_]+)/);
  return match ? match[1] : null;
}

// 画像ファイルかどうかの判定
function isImageFile(url) {
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'];
  return imageExtensions.some(ext => url.toLowerCase().includes(ext));
}

// 画像を1秒動画に変換（オプション機能）
function convertImageToVideo(fileId) {
  try {
    console.log('動画変換開始:', fileId);
    
    // Google Driveからファイルを取得
    const file = DriveApp.getFileById(fileId);
    const blob = file.getBlob();
    
    // 画像ファイルの場合のみ変換処理
    if (!blob.getContentType().startsWith('image/')) {
      console.log('画像ファイルではありません:', blob.getContentType());
      return fileId; // 元のファイルIDを返す
    }
    
    // ここで実際の動画変換処理を実装
    // 現在は元のファイルIDを返す
    console.log('動画変換処理（未実装）');
    
    return fileId;
    
  } catch (error) {
    console.error('動画変換エラー:', error);
    return fileId;
  }
}

// トリガーのセットアップ
function setupTrigger() {
  // 既存のトリガーを削除
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === 'onFormSubmit') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  
  // 新しいトリガーを作成
  const form = FormApp.openByUrl('YOUR_FORM_URL_HERE'); // フォームURLに置き換え
  ScriptApp.newTrigger('onFormSubmit')
    .onFormSubmit()
    .create();
    
  console.log('トリガーセットアップ完了');
}

// テスト実行用関数
function testFormSubmit() {
  const testData = {
    values: [
      new Date().toISOString(),
      '都内メンエス',
      'テスト投稿内容です。これはテストの投稿です。',
      'https://drive.google.com/file/d/test123abc/view',
      'いいえ、送信する'
    ]
  };
  
  onFormSubmit(testData);
}
```

### 2-3. トリガーの設定
1. Apps Scriptで **トリガー** をクリック
2. **+ トリガーを追加**
3. 設定:
   - 実行する関数: `onFormSubmit`
   - イベントのソース: `フォームから`
   - イベントの種類: `フォーム送信時`

---

## 🛠️ STEP 2.5: GAS Git管理（clasp）の設定

### 2.5-1. 事前準備

#### Node.js のインストール確認
```bash
# Node.js がインストールされているか確認
node --version
npm --version
```

Node.js がインストールされていない場合:
- [Node.js公式サイト](https://nodejs.org/) からダウンロードしてインストール

#### clasp のインストール
```bash
# clasp（Command Line Apps Script Projects）をグローバルインストール
npm install -g @google/clasp

# インストール確認
clasp --version
```

### 2.5-2. clasp の初期設定

#### Google Apps Script API を有効化
1. [Google Apps Script API](https://script.google.com/home/usersettings) にアクセス
2. **Google Apps Script API** を **オン** に設定

#### clasp にログイン
```bash
# Googleアカウントでログイン
clasp login
```
ブラウザが開くので、Googleアカウントでログインして認証を完了

### 2.5-3. 既存GASプロジェクトをローカルに取得

#### プロジェクトIDの確認
1. Apps Script エディタを開く
2. 左サイドバーの **プロジェクトの設定** をクリック
3. **スクリプトID** をコピー

#### ローカルディレクトリの作成と初期化
```bash
# プロジェクト用ディレクトリを作成
mkdir gas-form-automation
cd gas-form-automation

# Git初期化
git init

# .gitignore 作成
echo "node_modules/
.clasprc.json
.clasp.json" > .gitignore

# clasp でプロジェクトをクローン
clasp clone YOUR_SCRIPT_ID_HERE
```

### 2.5-4. ローカル開発環境の構築

#### TypeScript 設定（推奨）
```bash
# TypeScript設定ファイルを作成
cat > tsconfig.json << EOL
{
  "compilerOptions": {
    "target": "ES2019",
    "module": "ES2020",
    "lib": ["ES2019"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules"]
}
EOL

# package.json 作成
cat > package.json << EOL
{
  "name": "gas-form-automation",
  "version": "1.0.0",
  "description": "Google Apps Script for form automation",
  "scripts": {
    "push": "clasp push",
    "pull": "clasp pull",
    "deploy": "clasp deploy",
    "logs": "clasp logs",
    "open": "clasp open"
  },
  "devDependencies": {
    "@google/clasp": "^2.4.2",
    "@types/google-apps-script": "^1.0.0",
    "typescript": "^5.0.0"
  }
}
EOL

# 依存関係をインストール
npm install
```

#### ディレクトリ構造の整理
```bash
# src ディレクトリを作成
mkdir src

# 既存の .gs ファイルを src に移動
mv *.gs src/ 2>/dev/null || true

# メインファイルを整理
cat > src/main.ts << 'EOL'
// ... existing code ...
EOL
```

### 2.5-5. Git でのバージョン管理

#### 初回コミット
```bash
# README.md 作成
cat > README.md << 'EOL'
# 📱 投稿フォーム自動化 GAS

Google Formsからスプレッドシートへの自動投稿システム

## 🚀 セットアップ

1. Dependencies をインストール:
   ```bash
   npm install
   ```

2. GAS にプッシュ:
   ```bash
   npm run push
   ```

3. ログ確認:
   ```bash
   npm run logs
   ```

## 📝 開発

- `src/` ディレクトリで TypeScript コードを編集
- `npm run push` でGASにデプロイ
- `npm run pull` で最新版を取得

## 🔧 設定

必要な環境変数:
- スプレッドシートID: `1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA`
- フォームURL: （設定後に更新）
EOL

# Git にファイルを追加
git add .
git commit -m "🎉 Initial commit: GAS form automation setup"
```

#### ブランチ戦略の設定
```bash
# 開発ブランチを作成
git checkout -b development

# 機能別ブランチ例
git checkout -b feature/form-integration
git checkout -b feature/image-processing
git checkout -b feature/video-conversion
```

### 2.5-6. 開発ワークフロー

#### ローカル開発の流れ
```bash
# 1. 最新版を取得
clasp pull

# 2. Git で変更を管理
git add .
git commit -m "📝 Update: form processing logic"

# 3. GAS にプッシュ
clasp push

# 4. デプロイ（本番反映）
clasp deploy --description "Form automation v1.1"
```

#### 自動化スクリプト（推奨）
```bash
# deploy.sh 作成
cat > deploy.sh << 'EOL'
#!/bin/bash

echo "🚀 GAS デプロイメント開始..."

# ローカル変更をコミット
echo "📝 Git コミット..."
git add .
read -p "コミットメッセージを入力: " commit_msg
git commit -m "$commit_msg"

# GAS にプッシュ
echo "📤 GAS にプッシュ..."
clasp push

# デプロイ
echo "🌍 本番デプロイ..."
read -p "デプロイ説明を入力: " deploy_desc
clasp deploy --description "$deploy_desc"

echo "✅ デプロイ完了！"
clasp open
EOL

# 実行権限を付与
chmod +x deploy.sh
```

### 2.5-7. GitHub 連携（オプション）

#### GitHub リポジトリ作成
```bash
# GitHub CLI を使用（事前にインストールが必要）
gh repo create gas-form-automation --private --description "Google Apps Script for form automation"

# または手動でGitHubにリポジトリを作成後
git remote add origin https://github.com/YOUR_USERNAME/gas-form-automation.git
git branch -M main
git push -u origin main
```

#### GitHub Actions で自動デプロイ（高度）
```bash
# .github/workflows ディレクトリを作成
mkdir -p .github/workflows

# 自動デプロイワークフローを作成
cat > .github/workflows/deploy-gas.yml << 'EOL'
name: Deploy to Google Apps Script

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
        
    - name: Install dependencies
      run: npm install
      
    - name: Setup clasp
      run: |
        echo '${{ secrets.CLASP_CREDENTIALS }}' > ~/.clasprc.json
        echo '${{ secrets.CLASP_PROJECT }}' > .clasp.json
        
    - name: Deploy to GAS
      run: |
        npx clasp push
        npx clasp deploy --description "Auto deploy from GitHub Actions"
EOL
```

### 2.5-8. 本番運用のポイント

#### 環境分離
```bash
# 開発環境と本番環境を分離
cat > .clasp.json << EOL
{
  "scriptId": "YOUR_DEVELOPMENT_SCRIPT_ID",
  "rootDir": "./src"
}
EOL

cat > .clasp.production.json << EOL
{
  "scriptId": "YOUR_PRODUCTION_SCRIPT_ID", 
  "rootDir": "./src"
}
EOL
```

#### デプロイコマンド
```bash
# 開発環境にデプロイ
clasp push

# 本番環境にデプロイ
clasp push --project .clasp.production.json
clasp deploy --project .clasp.production.json --description "Production release v1.0"
```

#### ログ監視
```bash
# リアルタイムログ監視
clasp logs --watch

# 特定の時間範囲のログ
clasp logs --since "2024-01-01" --until "2024-01-02"
```

### 2.5-9. チーム開発（オプション）

#### 共有設定
```bash
# 他の開発者がクローンできるよう設定
cat > setup.sh << 'EOL'
#!/bin/bash

echo "🛠️ 開発環境セットアップ..."

# 依存関係をインストール
npm install

# clasp ログイン
clasp login

# 最新版を取得
clasp pull

echo "✅ セットアップ完了！"
echo "📝 開発を開始してください:"
echo "  - コード編集: src/ ディレクトリ"
echo "  - プッシュ: npm run push" 
echo "  - ログ確認: npm run logs"
EOL

chmod +x setup.sh
```

---

## 🎬 STEP 3: 画像→動画変換システム

### 3-1. 変換方式の選択

#### オプション1: 画像そのまま運用 ⭐ **推奨**
```javascript
// シンプルな画像URL処理（変換なし）
function processImageUrls(fileUrls) {
  if (!fileUrls) return '';
  
  const urls = fileUrls.split(',').map(url => url.trim());
  const processedUrls = [];
  
  for (let url of urls) {
    if (url && url.includes('drive.google.com')) {
      const fileId = extractFileId(url);
      if (fileId) {
        processedUrls.push(`https://drive.google.com/file/d/${fileId}/view?usp=sharing`);
      }
    }
  }
  
  return processedUrls.join('\n');
}
```

#### オプション2: CloudConvert API（有料）
```javascript
// CloudConvert APIを使用した動画変換
function convertImageToVideoWithCloudConvert(fileId) {
  const API_KEY = 'YOUR_CLOUDCONVERT_API_KEY';
  
  try {
    // CloudConvert API実装
    // 月25回まで無料、それ以降は有料
    
  } catch (error) {
    console.error('CloudConvert変換エラー:', error);
    return null;
  }
}
```

### 3-2. ローカルPython変換（オプション）
プロジェクトディレクトリに以下のファイルを作成:

#### `bots/video_converter/image_to_video.py`
```python
import os
from moviepy.editor import ImageClip, CompositeVideoClip
from PIL import Image
import tempfile

def create_animated_video(image_path, output_path, duration=1.0):
    """
    画像を1秒のアニメーション動画に変換
    """
    try:
        # 画像を読み込み
        img = Image.open(image_path)
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            img.save(temp_file.name, 'PNG')
            temp_path = temp_file.name
        
        # MoviePyで動画作成
        clip = ImageClip(temp_path, duration=duration)
        
        # アニメーション効果を追加（ズームイン）
        def make_frame(t):
            # 時間に応じてズーム効果
            zoom_factor = 1 + (t / duration) * 0.1  # 10%ズームイン
            return clip.get_frame(t)
        
        # 最終動画として出力
        clip.write_videofile(
            output_path,
            fps=30,
            codec='libx264',
            audio=False,
            verbose=False,
            logger=None
        )
        
        # 一時ファイルを削除
        os.unlink(temp_path)
        
        return True
        
    except Exception as e:
        print(f"動画変換エラー: {e}")
        return False

def convert_images_in_folder(input_folder, output_folder):
    """
    フォルダ内の全画像を動画に変換
    """
    os.makedirs(output_folder, exist_ok=True)
    
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            input_path = os.path.join(input_folder, filename)
            output_filename = os.path.splitext(filename)[0] + '.mp4'
            output_path = os.path.join(output_folder, output_filename)
            
            print(f"変換中: {filename} → {output_filename}")
            success = create_animated_video(input_path, output_path)
            
            if success:
                print(f"✅ 変換完了: {output_filename}")
            else:
                print(f"❌ 変換失敗: {filename}")

if __name__ == "__main__":
    # テスト実行
    input_folder = "test_images"
    output_folder = "test_videos"
    
    convert_images_in_folder(input_folder, output_folder)
```

#### `requirements.txt`に追加
```txt
moviepy>=1.0.3
pillow>=9.0.0
```

---

## 🚀 STEP 4: セットアップ手順

### 4-1. 事前準備
1. **Google アカウント** でログイン
2. **Google Drive** に十分な容量があることを確認
3. **対象スプレッドシート** へのアクセス権限確認

### 4-2. フォーム作成
1. STEP 1の手順に従ってフォームを作成
2. 各セクションの条件分岐を正確に設定
3. スプレッドシート連携を有効化

### 4-3. Apps Scriptセットアップ
1. STEP 2-2のコードを貼り付け
2. **YOUR_FORM_URL_HERE** を実際のフォームURLに置き換え
3. トリガーを設定
4. テスト実行で動作確認

### 4-4. 動作テスト
1. フォームから実際に投稿
2. スプレッドシートに正しく追加されるか確認
3. ファイルURLが正しく処理されるか確認

---

## 📱 STEP 5: スマホでの使用方法

### 5-1. フォームのアクセス
1. 作成したフォームの **送信** ボタンをクリック
2. **リンクをコピー** で短縮URLを取得
3. スマホのブックマークに保存

### 5-2. 投稿の流れ
1. **アカウント選択**: 🏪都内メンエス または 🍷都内セクキャバ
2. **投稿内容入力**: 本文を入力
3. **ファイル選択**: 画像・動画をアップロード
4. **追加投稿**: 必要に応じて追加
5. **送信**: フォームを送信

### 5-3. 投稿管理
1. スプレッドシートで投稿内容を確認
2. **投稿可能** 列にチェックを入れて承認
3. 自動投稿システムが承認済み投稿を処理

---

## 🔧 トラブルシューティング

### よくある問題と解決策

#### 1. フォーム送信エラー
```
エラー: スプレッドシートに追加されない
解決策: 
- Apps Scriptのトリガーが正しく設定されているか確認
- スプレッドシートIDが正しいか確認
- 実行ログでエラー内容を確認
```

#### 2. ファイルアップロードエラー
```
エラー: 画像がアップロードできない
解決策:
- Google Driveの容量を確認
- ファイルサイズが100MB以下か確認
- 対応ファイル形式か確認
```

#### 3. 動画変換エラー
```
エラー: 画像が動画に変換されない
解決策:
- CloudConvert APIキーが正しいか確認
- API使用量制限に達していないか確認
- 画像形式が対応しているか確認
```

### デバッグ方法
1. **Apps Script** → **実行数** でログを確認
2. **フォーム** → **回答** で送信データを確認
3. **スプレッドシート** で最終結果を確認

---

## 📈 運用のポイント

### 効率的な使い方
1. **まとめて投稿**: 複数の投稿を一度に作成
2. **時間指定**: 投稿したい時間帯を考慮
3. **承認フロー**: 投稿前に内容をチェック

### メンテナンス
1. **定期的なログ確認**: エラーが発生していないかチェック
2. **容量管理**: Google Driveの使用量を監視
3. **API制限確認**: 変換APIの使用量をチェック

---

## 🎯 最終チェックリスト

- [ ] Google Formsが正しく作成されている
- [ ] 2つのアカウント選択肢が設定されている
- [ ] スプレッドシート連携が動作している
- [ ] Apps Scriptのトリガーが設定されている
- [ ] ファイルアップロード機能が動作している
- [ ] 投稿データが正しいシートに追加されている
- [ ] スマホからアクセスできる
- [ ] 実際の投稿フローでテスト完了

---

## 📞 サポート

質問や問題が発生した場合は、以下の情報を含めてお知らせください：

1. **実行環境**: ブラウザ、デバイス情報
2. **エラーメッセージ**: 正確なエラー内容
3. **実行手順**: どの段階で問題が発生したか
4. **スクリーンショット**: 可能であれば画面キャプチャ

以上で、スマホ対応投稿フォームから動画変換まで含む完全自動化システムのセットアップが完了です！🎉 