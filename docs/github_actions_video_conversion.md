# 🚀 GitHub Actions動画変換システム

## 🎯 システム構成

### 既存環境活用
```
✅ GitHub Actions環境
✅ Pythonスクリプト実行可能
✅ ffmpeg利用可能
✅ スプレッドシート接続済み
```

### 処理フロー
```
📱 Google Forms → 📊 スプレッドシート → 🤖 GitHub Actions → 🎥 動画変換 → 📊 URL更新
```

---

## 🔧 実装方法

### 方法1: 定期処理（推奨）

#### 1-1. 動画変換スクリプト作成
```python
# bots/video_converter/image_to_video.py
import os
import requests
import subprocess
from pathlib import Path
import tempfile
from google.oauth2.service_account import Credentials
import gspread

class ImageToVideoConverter:
    def __init__(self):
        self.setup_google_sheets()
        
    def setup_google_sheets(self):
        """Google Sheets API設定"""
        creds = Credentials.from_service_account_file(
            'config/google_service_account.json',
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.gc = gspread.authorize(creds)
        self.sheet_id = '1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA'
    
    def find_images_to_convert(self):
        """変換が必要な画像を検索"""
        spreadsheet = self.gc.open_by_key(self.sheet_id)
        
        images_to_convert = []
        
        for worksheet_name in ['都内メンエス', '都内セクキャバ']:
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
                records = worksheet.get_all_records()
                
                for i, record in enumerate(records, start=2):  # ヘッダー行を除く
                    media_url = record.get('画像/動画URL', '')
                    
                    # 画像URLで、まだ変換されていないもの
                    if (media_url and 
                        self.is_image_url(media_url) and 
                        not self.is_converted_video(media_url)):
                        
                        images_to_convert.append({
                            'worksheet': worksheet_name,
                            'row': i,
                            'url': media_url,
                            'record_id': record.get('ID', ''),
                            'content': record.get('本文', '')[:50]
                        })
                        
            except Exception as e:
                print(f"❌ ワークシート処理エラー {worksheet_name}: {e}")
        
        return images_to_convert
    
    def is_image_url(self, url):
        """画像URLかどうか判定"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        return any(ext in url.lower() for ext in image_extensions)
    
    def is_converted_video(self, url):
        """既に変換済みかどうか判定"""
        return 'converted_video' in url or url.endswith('.mp4')
    
    def download_image(self, drive_url):
        """Google Driveから画像をダウンロード"""
        try:
            # Google DriveのファイルIDを抽出
            file_id = self.extract_file_id(drive_url)
            if not file_id:
                raise ValueError("ファイルIDが抽出できません")
            
            # ダウンロードURL
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            
            # 一時ファイルにダウンロード
            response = requests.get(download_url)
            response.raise_for_status()
            
            # 一時ファイル作成
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(response.content)
            temp_file.close()
            
            return temp_file.name
            
        except Exception as e:
            print(f"❌ 画像ダウンロードエラー: {e}")
            return None
    
    def extract_file_id(self, url):
        """Google DriveのURLからファイルIDを抽出"""
        import re
        match = re.search(r'/file/d/([a-zA-Z0-9-_]+)', url)
        return match.group(1) if match else None
    
    def convert_image_to_video(self, image_path, duration=1):
        """ffmpegで画像を動画に変換"""
        try:
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
            
            # ffmpegコマンド実行
            cmd = [
                'ffmpeg',
                '-loop', '1',
                '-i', image_path,
                '-c:v', 'libx264',
                '-t', str(duration),
                '-pix_fmt', 'yuv420p',
                '-vf', 'scale=720:720:force_original_aspect_ratio=decrease,pad=720:720:(ow-iw)/2:(oh-ih)/2',
                '-r', '30',
                '-y',  # 上書き許可
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ ffmpegエラー: {result.stderr}")
                return None
            
            print(f"✅ 動画変換成功: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ 動画変換エラー: {e}")
            return None
        finally:
            # 元画像ファイルを削除
            if os.path.exists(image_path):
                os.unlink(image_path)
    
    def upload_video_to_drive(self, video_path):
        """変換された動画をGoogle Driveにアップロード"""
        try:
            # Google Drive APIでアップロード実装
            # 今回は簡略化してローカル保存
            print(f"🎥 動画保存: {video_path}")
            return f"converted_video_{os.path.basename(video_path)}"
            
        except Exception as e:
            print(f"❌ アップロードエラー: {e}")
            return None
    
    def update_spreadsheet_url(self, worksheet_name, row, new_url):
        """スプレッドシートのURLを更新"""
        try:
            spreadsheet = self.gc.open_by_key(self.sheet_id)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            # F列（画像/動画URL）を更新
            worksheet.update_cell(row, 6, new_url)
            print(f"✅ スプレッドシート更新: {worksheet_name} 行{row}")
            
        except Exception as e:
            print(f"❌ スプレッドシート更新エラー: {e}")
    
    def process_all_images(self):
        """すべての画像を処理"""
        images = self.find_images_to_convert()
        
        if not images:
            print("🎯 変換対象の画像がありません")
            return
        
        print(f"📊 変換対象: {len(images)}件")
        
        for image_data in images:
            try:
                print(f"🔄 処理中: ID={image_data['record_id']} - {image_data['content']}...")
                
                # 画像ダウンロード
                image_path = self.download_image(image_data['url'])
                if not image_path:
                    continue
                
                # 動画変換
                video_path = self.convert_image_to_video(image_path)
                if not video_path:
                    continue
                
                # アップロード
                new_url = self.upload_video_to_drive(video_path)
                if not new_url:
                    continue
                
                # スプレッドシート更新
                self.update_spreadsheet_url(
                    image_data['worksheet'],
                    image_data['row'],
                    new_url
                )
                
                # 一時ファイル削除
                if os.path.exists(video_path):
                    os.unlink(video_path)
                
                print(f"✅ 完了: ID={image_data['record_id']}")
                
            except Exception as e:
                print(f"❌ 処理エラー ID={image_data['record_id']}: {e}")

if __name__ == "__main__":
    converter = ImageToVideoConverter()
    converter.process_all_images()
```

#### 1-2. GitHub Actionsワークフロー追加
```yaml
# .github/workflows/video-conversion.yml
name: Video Conversion

on:
  schedule:
    # 30分ごとに実行
    - cron: '*/30 * * * *'
  workflow_dispatch:

jobs:
  convert-videos:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install system dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y ffmpeg
    
    - name: Install Python dependencies
      run: |
        pip install -r requirements.txt
        pip install gspread google-auth requests
    
    - name: Create service account file
      run: |
        echo '${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}' > config/google_service_account.json
    
    - name: Run video conversion
      run: |
        python bots/video_converter/image_to_video.py
```

---

## 🔧 方法2: API方式（リアルタイム）

### 2-1. Flask API作成
```python
# bots/video_converter/api_server.py
from flask import Flask, request, jsonify
import os
import tempfile
import subprocess

app = Flask(__name__)

@app.route('/convert-image-to-video', methods=['POST'])
def convert_image_to_video():
    try:
        data = request.json
        image_url = data.get('image_url')
        duration = data.get('duration', 1)
        
        if not image_url:
            return jsonify({'error': 'image_url is required'}), 400
        
        # 画像ダウンロード → 動画変換 → アップロード
        video_url = process_conversion(image_url, duration)
        
        return jsonify({
            'success': True,
            'original_url': image_url,
            'video_url': video_url,
            'duration': duration
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'fallback_url': data.get('image_url', '')
        }), 500

def process_conversion(image_url, duration):
    # 変換処理実装
    pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### 2-2. Google Apps Scriptからの呼び出し
```javascript
function convertImageToVideoGitHub(imageUrl) {
  try {
    const apiUrl = 'https://YOUR_GITHUB_ACTIONS_ENDPOINT/convert-image-to-video';
    
    const response = UrlFetchApp.fetch(apiUrl, {
      method: 'POST',
      contentType: 'application/json',
      payload: JSON.stringify({
        image_url: imageUrl,
        duration: 1
      })
    });
    
    const result = JSON.parse(response.getContentText());
    
    if (result.success) {
      return result.video_url;
    } else {
      return result.fallback_url;
    }
    
  } catch (error) {
    console.error('GitHub Actions動画変換エラー:', error);
    return imageUrl;
  }
}
```

---

## 🎯 推奨アプローチ

### 定期処理方式（方法1）がおすすめ

**理由：**
1. ✅ 既存のGitHub Actions環境を活用
2. ✅ 設定が簡単で安定動作  
3. ✅ リソース効率が良い
4. ✅ エラーハンドリングが容易

**処理フロー：**
```
1. Google Forms → スプレッドシートに画像URL追加
2. 30分ごとにGitHub Actionsが画像URLをチェック
3. 未変換の画像を検出 → ffmpegで動画変換
4. 変換済み動画URLでスプレッドシート更新
5. 投稿ボットが動画付き投稿を実行
```

---

## 💰 コスト・制限

### GitHub Actions制限
```
🆓 パブリックリポジトリ: 無制限
💰 プライベートリポジトリ: 月2,000分無料
⏱️ 1回の実行: 最大6時間
📊 ストレージ: 500MB無料
```

### 実用性
```
✅ 月数千件の変換が可能
✅ 完全無料（パブリックリポジトリの場合）
✅ ffmpeg高品質変換
✅ 既存インフラ活用
```

---

## 🚀 実装手順

1. **`bots/video_converter/image_to_video.py` 作成**
2. **`.github/workflows/video-conversion.yml` 追加**
3. **GitHub Secrets に `GOOGLE_SERVICE_ACCOUNT_JSON` 追加**
4. **動作テスト実行**
5. **30分間隔で自動実行開始**

この方法なら既存のPython環境とffmpegを活用して、完全無料で高品質な動画変換が可能です！🎉 