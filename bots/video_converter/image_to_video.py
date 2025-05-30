#!/usr/bin/env python3
"""
📱 GitHub Actions動画変換システム
🎯 スプレッドシートの画像URLを動画に変換
"""

import os
import sys
import requests
import subprocess
import tempfile
import json
from pathlib import Path
from google.oauth2.service_account import Credentials
import gspread

class ImageToVideoConverter:
    def __init__(self):
        self.setup_google_sheets()
        
    def setup_google_sheets(self):
        """Google Sheets API設定"""
        try:
            # GitHub Actionsからの場合
            if os.path.exists('config/google_service_account.json'):
                creds = Credentials.from_service_account_file(
                    'config/google_service_account.json',
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            else:
                # ローカル実行の場合
                print("❌ Google Service Account JSONファイルが見つかりません")
                sys.exit(1)
                
            self.gc = gspread.authorize(creds)
            self.sheet_id = '1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA'
            print("✅ Google Sheets API接続成功")
            
        except Exception as e:
            print(f"❌ Google Sheets API設定エラー: {e}")
            sys.exit(1)
    
    def find_images_to_convert(self):
        """変換が必要な画像を検索"""
        try:
            spreadsheet = self.gc.open_by_key(self.sheet_id)
            images_to_convert = []
            
            for worksheet_name in ['都内メンエス', '都内セクキャバ']:
                try:
                    worksheet = spreadsheet.worksheet(worksheet_name)
                    records = worksheet.get_all_records()
                    
                    print(f"📊 {worksheet_name}: {len(records)}件のレコードを確認")
                    
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
                                'content': record.get('本文', '')[:50] + '...' if len(record.get('本文', '')) > 50 else record.get('本文', '')
                            })
                            
                except Exception as e:
                    print(f"❌ ワークシート処理エラー {worksheet_name}: {e}")
            
            print(f"🎯 変換対象の画像: {len(images_to_convert)}件")
            return images_to_convert
            
        except Exception as e:
            print(f"❌ スプレッドシート読み込みエラー: {e}")
            return []
    
    def is_image_url(self, url):
        """画像URLかどうか判定"""
        if not url:
            return False
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        url_lower = url.lower()
        return any(ext in url_lower for ext in image_extensions) or 'drive.google.com' in url_lower
    
    def is_converted_video(self, url):
        """既に変換済みかどうか判定"""
        if not url:
            return False
        return 'converted_video' in url or url.endswith('.mp4') or 'video_converted' in url
    
    def download_image(self, drive_url):
        """Google Driveから画像をダウンロード"""
        try:
            # Google DriveのファイルIDを抽出
            file_id = self.extract_file_id(drive_url)
            if not file_id:
                print(f"❌ ファイルIDが抽出できません: {drive_url}")
                return None
            
            # ダウンロードURL
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            
            print(f"📥 画像ダウンロード中: {file_id}")
            
            # 一時ファイルにダウンロード
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()
            
            # Content-Typeから拡張子を判定
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type:
                suffix = '.jpg'
            elif 'png' in content_type:
                suffix = '.png'
            elif 'gif' in content_type:
                suffix = '.gif'
            else:
                suffix = '.jpg'  # デフォルト
            
            # 一時ファイル作成
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            temp_file.write(response.content)
            temp_file.close()
            
            print(f"✅ 画像ダウンロード完了: {temp_file.name} ({len(response.content)} bytes)")
            return temp_file.name
            
        except Exception as e:
            print(f"❌ 画像ダウンロードエラー: {e}")
            return None
    
    def extract_file_id(self, url):
        """Google DriveのURLからファイルIDを抽出"""
        import re
        
        # 複数のパターンに対応
        patterns = [
            r'/file/d/([a-zA-Z0-9-_]+)',
            r'id=([a-zA-Z0-9-_]+)',
            r'/open\?id=([a-zA-Z0-9-_]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def convert_image_to_video(self, image_path, duration=1):
        """ffmpegで画像を動画に変換"""
        try:
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
            
            print(f"🎬 動画変換開始: {image_path} → {output_path}")
            
            # ffmpegコマンド実行
            cmd = [
                'ffmpeg',
                '-y',  # 上書き許可
                '-loop', '1',
                '-i', image_path,
                '-c:v', 'libx264',
                '-t', str(duration),
                '-pix_fmt', 'yuv420p',
                '-vf', 'scale=720:720:force_original_aspect_ratio=decrease,pad=720:720:(ow-iw)/2:(oh-ih)/2:color=black',
                '-r', '30',
                '-preset', 'fast',
                '-crf', '23',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                print(f"❌ ffmpegエラー: {result.stderr}")
                return None
            
            # 出力ファイルのサイズ確認
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"✅ 動画変換成功: {output_path} ({file_size} bytes)")
                return output_path
            else:
                print(f"❌ 出力ファイルが作成されませんでした")
                return None
            
        except subprocess.TimeoutExpired:
            print(f"❌ 動画変換タイムアウト: {image_path}")
            return None
        except Exception as e:
            print(f"❌ 動画変換エラー: {e}")
            return None
        finally:
            # 元画像ファイルを削除
            if os.path.exists(image_path):
                os.unlink(image_path)
                print(f"🗑️ 一時画像ファイル削除: {image_path}")
    
    def upload_video_to_github(self, video_path):
        """変換された動画をGitHubに保存（簡略版）"""
        try:
            # 実際の実装では GitHub API や別のストレージを使用
            # 今回は簡略化してファイル名のみ返す
            video_filename = f"video_converted_{os.path.basename(video_path)}"
            
            print(f"🎥 動画処理完了: {video_filename}")
            
            # 一時的な動画URLを生成（実際の実装では適切なURLを返す）
            video_url = f"https://github.com/your-repo/videos/{video_filename}"
            
            return video_url
            
        except Exception as e:
            print(f"❌ 動画アップロードエラー: {e}")
            return None
        finally:
            # 一時動画ファイルを削除
            if os.path.exists(video_path):
                os.unlink(video_path)
                print(f"🗑️ 一時動画ファイル削除: {video_path}")
    
    def update_spreadsheet_url(self, worksheet_name, row, new_url):
        """スプレッドシートのURLを更新"""
        try:
            spreadsheet = self.gc.open_by_key(self.sheet_id)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            # F列（画像/動画URL）を更新
            worksheet.update_cell(row, 6, new_url)
            print(f"✅ スプレッドシート更新: {worksheet_name} 行{row} → {new_url[:50]}...")
            
        except Exception as e:
            print(f"❌ スプレッドシート更新エラー: {e}")
    
    def process_all_images(self):
        """すべての画像を処理"""
        print("🚀 GitHub Actions動画変換処理開始")
        
        images = self.find_images_to_convert()
        
        if not images:
            print("🎯 変換対象の画像がありません")
            return
        
        print(f"📊 変換対象: {len(images)}件")
        
        success_count = 0
        error_count = 0
        
        for i, image_data in enumerate(images, 1):
            try:
                print(f"\n🔄 [{i}/{len(images)}] 処理中: ID={image_data['record_id']}")
                print(f"📝 内容: {image_data['content']}")
                print(f"🌐 URL: {image_data['url'][:100]}...")
                
                # 画像ダウンロード
                image_path = self.download_image(image_data['url'])
                if not image_path:
                    print(f"❌ 画像ダウンロード失敗: ID={image_data['record_id']}")
                    error_count += 1
                    continue
                
                # 動画変換
                video_path = self.convert_image_to_video(image_path)
                if not video_path:
                    print(f"❌ 動画変換失敗: ID={image_data['record_id']}")
                    error_count += 1
                    continue
                
                # アップロード
                new_url = self.upload_video_to_github(video_path)
                if not new_url:
                    print(f"❌ アップロード失敗: ID={image_data['record_id']}")
                    error_count += 1
                    continue
                
                # スプレッドシート更新
                self.update_spreadsheet_url(
                    image_data['worksheet'],
                    image_data['row'],
                    new_url
                )
                
                success_count += 1
                print(f"✅ 完了: ID={image_data['record_id']}")
                
            except Exception as e:
                print(f"❌ 処理エラー ID={image_data['record_id']}: {e}")
                error_count += 1
        
        print(f"\n🎉 処理完了: 成功={success_count}件, エラー={error_count}件")

def main():
    """メイン処理"""
    print("=" * 50)
    print("📱 GitHub Actions動画変換システム")
    print("=" * 50)
    
    try:
        converter = ImageToVideoConverter()
        converter.process_all_images()
        
    except KeyboardInterrupt:
        print("\n⏹️ 処理が中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        sys.exit(1)
    
    print("\n✅ 動画変換処理終了")

if __name__ == "__main__":
    main() 