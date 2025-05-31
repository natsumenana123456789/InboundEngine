import pytest
from PIL import Image
from PIL.ExifTags import TAGS
from io import BytesIO
import piexif
from src.media_processor import MediaProcessor

@pytest.fixture
def media_processor():
    return MediaProcessor()

@pytest.fixture
def sample_jpeg_with_exif():
    """EXIFデータを含むサンプルJPEG画像を作成"""
    # サンプル画像の作成
    img = Image.new('RGB', (100, 100), color='red')
    img_io = BytesIO()
    
    # EXIFデータの作成
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: "Test Camera".encode(),
            piexif.ImageIFD.Model: "Test Model".encode(),
            piexif.ImageIFD.Software: "Test Software".encode()
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: "2024:03:20 12:00:00".encode(),
            piexif.ExifIFD.LensMake: "Test Lens".encode()
        },
        "GPS": {
            piexif.GPSIFD.GPSLatitude: ((35, 1), (40, 1), (0, 1)),
            piexif.GPSIFD.GPSLongitude: ((139, 1), (45, 1), (0, 1))
        }
    }
    exif_bytes = piexif.dump(exif_dict)
    
    # EXIFデータを含む画像の保存
    img.save(img_io, 'JPEG', exif=exif_bytes)
    img_io.seek(0)
    return img_io

def test_remove_exif(media_processor, sample_jpeg_with_exif):
    """EXIFデータの削除テスト"""
    # EXIFデータを削除
    processed_image_data = media_processor.remove_exif(sample_jpeg_with_exif.getvalue())
    
    # 処理後の画像をPILで開く
    processed_img = Image.open(BytesIO(processed_image_data))
    
    # EXIFデータが存在しないことを確認
    assert not hasattr(processed_img, '_getexif') or processed_img._getexif() is None

def test_preserve_image_quality(media_processor, sample_jpeg_with_exif):
    """画像品質の保持テスト"""
    # 元画像のサイズを取得
    original_img = Image.open(sample_jpeg_with_exif)
    original_size = original_img.size
    
    # EXIFデータを削除
    processed_image_data = media_processor.remove_exif(sample_jpeg_with_exif.getvalue())
    processed_img = Image.open(BytesIO(processed_image_data))
    
    # 画像サイズが変わっていないことを確認
    assert processed_img.size == original_size
    
    # 画像モードが変わっていないことを確認
    assert processed_img.mode == original_img.mode

def test_handle_non_jpeg(media_processor):
    """非JPEG画像の処理テスト"""
    # PNG画像の作成
    img = Image.new('RGB', (100, 100), color='blue')
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    # PNG画像の処理
    processed_image_data = media_processor.remove_exif(img_io.getvalue())
    
    # 処理後もPNGとして開けることを確認
    processed_img = Image.open(BytesIO(processed_image_data))
    assert processed_img.format == 'PNG'

def test_handle_invalid_image(media_processor):
    """無効な画像データの処理テスト"""
    invalid_data = b'invalid image data'
    
    # 無効なデータを処理
    with pytest.raises(ValueError):
        media_processor.remove_exif(invalid_data) 