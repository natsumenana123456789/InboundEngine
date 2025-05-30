import os
import subprocess
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

class VideoProcessor:
    def __init__(self, logger=None):
        """
        動画処理用のユーティリティクラス
        
        Args:
            logger: ロガーインスタンス（オプション）
        """
        self.logger = logger or logging.getLogger(__name__)

    def get_video_metadata(self, video_path: str) -> Dict:
        """
        動画ファイルのメタデータを取得
        
        Args:
            video_path: 動画ファイルのパス
            
        Returns:
            Dict: メタデータ情報
        """
        try:
            # ffprobeを使用してメタデータを取得
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"ffprobe実行エラー: {result.stderr}")
            
            metadata = json.loads(result.stdout)
            
            # 必要な情報を抽出
            video_info = {
                'duration': float(metadata['format'].get('duration', 0)),
                'size': int(metadata['format'].get('size', 0)),
                'bitrate': int(metadata['format'].get('bit_rate', 0)),
                'format': metadata['format'].get('format_name', ''),
                'streams': []
            }
            
            # ストリーム情報を抽出
            for stream in metadata.get('streams', []):
                if stream['codec_type'] in ['video', 'audio']:
                    stream_info = {
                        'type': stream['codec_type'],
                        'codec': stream.get('codec_name', ''),
                        'width': stream.get('width', 0),
                        'height': stream.get('height', 0),
                        'fps': eval(stream.get('r_frame_rate', '0/1')),
                        'bitrate': int(stream.get('bit_rate', 0))
                    }
                    video_info['streams'].append(stream_info)
            
            return video_info
            
        except Exception as e:
            self.logger.error(f"メタデータ取得エラー: {str(e)}")
            raise

    def calculate_video_hash(self, video_path: str) -> str:
        """
        動画ファイルのハッシュ値を計算
        
        Args:
            video_path: 動画ファイルのパス
            
        Returns:
            str: ハッシュ値
        """
        try:
            # ファイルの最初の1MBと最後の1MBを読み込んでハッシュを計算
            file_size = os.path.getsize(video_path)
            chunk_size = 1024 * 1024  # 1MB
            
            hasher = hashlib.sha256()
            
            with open(video_path, 'rb') as f:
                # 最初の1MB
                hasher.update(f.read(chunk_size))
                
                # 最後の1MB
                if file_size > chunk_size * 2:
                    f.seek(file_size - chunk_size)
                    hasher.update(f.read(chunk_size))
            
            return hasher.hexdigest()
            
        except Exception as e:
            self.logger.error(f"ハッシュ値計算エラー: {str(e)}")
            raise

    def optimize_video(self, input_path: str, output_path: str, 
                      target_size_mb: Optional[int] = None,
                      max_duration: Optional[int] = None) -> Tuple[str, Dict]:
        """
        動画を最適化（圧縮、リサイズ、トリミングなど）
        
        Args:
            input_path: 入力動画のパス
            output_path: 出力動画のパス
            target_size_mb: 目標ファイルサイズ（MB）
            max_duration: 最大動画時間（秒）
            
        Returns:
            Tuple[str, Dict]: (出力ファイルのパス, メタデータ)
        """
        try:
            # 入力動画のメタデータを取得
            input_metadata = self.get_video_metadata(input_path)
            
            # 基本のffmpegコマンド
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', 'libx264',  # H.264コーデック
                '-preset', 'medium',  # エンコード速度と品質のバランス
                '-crf', '23',  # 品質設定（0-51、低いほど高品質）
                '-c:a', 'aac',  # 音声コーデック
                '-b:a', '128k',  # 音声ビットレート
                '-movflags', '+faststart'  # ストリーミング最適化
            ]
            
            # 最大時間の制限
            if max_duration and input_metadata['duration'] > max_duration:
                cmd.extend(['-t', str(max_duration)])
            
            # アスペクト比を16:9に調整（必要に応じて）
            video_stream = next((s for s in input_metadata['streams'] if s['type'] == 'video'), None)
            if video_stream:
                width = video_stream['width']
                height = video_stream['height']
                if width / height != 16/9:
                    cmd.extend([
                        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,'
                              'pad=1920:1080:(ow-iw)/2:(oh-ih)/2'
                    ])
            
            # 出力パスを追加
            cmd.append(output_path)
            
            # コマンド実行
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"ffmpeg実行エラー: {result.stderr}")
            
            # 出力ファイルのメタデータを取得
            output_metadata = self.get_video_metadata(output_path)
            
            # 目標サイズに合わせて再エンコード（必要な場合）
            if target_size_mb:
                current_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                if current_size_mb > target_size_mb:
                    # ビットレートを調整して再エンコード
                    target_bitrate = int((target_size_mb * 8 * 1024) / output_metadata['duration'])
                    cmd = [
                        'ffmpeg',
                        '-i', output_path,
                        '-c:v', 'libx264',
                        '-preset', 'medium',
                        '-b:v', f'{target_bitrate}k',
                        '-c:a', 'aac',
                        '-b:a', '128k',
                        '-movflags', '+faststart',
                        output_path + '.temp'
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        os.replace(output_path + '.temp', output_path)
                        output_metadata = self.get_video_metadata(output_path)
            
            return output_path, output_metadata
            
        except Exception as e:
            self.logger.error(f"動画最適化エラー: {str(e)}")
            raise

    def validate_video(self, video_path: str) -> bool:
        """
        動画ファイルの検証
        
        Args:
            video_path: 動画ファイルのパス
            
        Returns:
            bool: 検証結果
        """
        try:
            # メタデータを取得
            metadata = self.get_video_metadata(video_path)
            
            # 基本的な検証
            if not metadata['streams']:
                self.logger.error("動画ストリームが見つかりません")
                return False
            
            # 動画ストリームの検証
            video_stream = next((s for s in metadata['streams'] if s['type'] == 'video'), None)
            if not video_stream:
                self.logger.error("動画ストリームが見つかりません")
                return False
            
            # 音声ストリームの検証
            audio_stream = next((s for s in metadata['streams'] if s['type'] == 'audio'), None)
            if not audio_stream:
                self.logger.warning("音声ストリームが見つかりません")
            
            # ファイルサイズの検証
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            if file_size_mb > 512:  # 512MB制限
                self.logger.error(f"ファイルサイズが大きすぎます: {file_size_mb:.1f}MB")
                return False
            
            # 動画時間の検証
            if metadata['duration'] > 140:  # 140秒制限
                self.logger.error(f"動画時間が長すぎます: {metadata['duration']}秒")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"動画検証エラー: {str(e)}")
            return False

if __name__ == '__main__':
    # テスト用のロガー設定
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # テスト用のVideoProcessorインスタンス
    processor = VideoProcessor(logger)
    
    # テスト用の動画パス
    test_video = "path/to/test/video.mp4"
    
    try:
        # メタデータ取得テスト
        metadata = processor.get_video_metadata(test_video)
        logger.info(f"メタデータ: {json.dumps(metadata, indent=2)}")
        
        # ハッシュ値計算テスト
        video_hash = processor.calculate_video_hash(test_video)
        logger.info(f"動画ハッシュ値: {video_hash}")
        
        # 動画最適化テスト
        output_path = "path/to/output/optimized.mp4"
        optimized_path, optimized_metadata = processor.optimize_video(
            test_video,
            output_path,
            target_size_mb=50,
            max_duration=60
        )
        logger.info(f"最適化後のメタデータ: {json.dumps(optimized_metadata, indent=2)}")
        
        # 動画検証テスト
        is_valid = processor.validate_video(optimized_path)
        logger.info(f"動画検証結果: {'有効' if is_valid else '無効'}")
        
    except Exception as e:
        logger.error(f"テスト実行エラー: {str(e)}") 