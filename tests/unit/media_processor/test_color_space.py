import pytest
from PIL import Image
from io import BytesIO
import numpy as np
from src.media_processor import MediaProcessor

@pytest.fixture
def media_processor():
    return MediaProcessor()

@pytest.fixture
def sample_cmyk_image():
    """サンプルのCMYK画像を作成"""
    # CMYK画像の作成（PIL.Imageを使用）
    img = Image.new('CMYK', (100, 100))
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    return img_io

@pytest.fixture
def sample_rgb_image():
    """サンプルのRGB画像を作成"""
    img = Image.new('RGB', (100, 100), color='red')
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    return img_io

def test_cmyk_to_rgb_conversion(media_processor, sample_cmyk_image):
    """CMYKからRGBへの変換テスト"""
    # CMYK画像を処理
    processed_image_data = media_processor.convert_to_rgb(sample_cmyk_image.getvalue())
    
    # 処理後の画像を開く
    processed_img = Image.open(BytesIO(processed_image_data))
    
    # RGB形式になっていることを確認
    assert processed_img.mode == 'RGB'

def test_rgb_image_preservation(media_processor, sample_rgb_image):
    """RGB画像の保持テスト"""
    # RGB画像を処理
    processed_image_data = media_processor.convert_to_rgb(sample_rgb_image.getvalue())
    
    # 処理前後の画像を比較
    original_img = Image.open(sample_rgb_image)
    processed_img = Image.open(BytesIO(processed_image_data))
    
    # モードとサイズが変わっていないことを確認
    assert processed_img.mode == original_img.mode
    assert processed_img.size == original_img.size

def test_color_accuracy(media_processor, sample_rgb_image):
    """色精度の保持テスト"""
    # 赤色のRGB画像を処理
    processed_image_data = media_processor.convert_to_rgb(sample_rgb_image.getvalue())
    processed_img = Image.open(BytesIO(processed_image_data))
    
    # 画像の中心ピクセルの色を取得
    center_x = processed_img.size[0] // 2
    center_y = processed_img.size[1] // 2
    center_color = processed_img.getpixel((center_x, center_y))
    
    # 赤色が保持されていることを確認（R値が高く、G,B値が低い）
    assert center_color[0] > 200  # R
    assert center_color[1] < 50   # G
    assert center_color[2] < 50   # B

def test_handle_invalid_image(media_processor):
    """無効な画像データの処理テスト"""
    invalid_data = b'invalid image data'
    
    # 無効なデータを処理
    with pytest.raises(ValueError):
        media_processor.convert_to_rgb(invalid_data)

def test_handle_grayscale_image(media_processor):
    """グレースケール画像の処理テスト"""
    # グレースケール画像の作成
    img = Image.new('L', (100, 100), color=128)
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    
    # グレースケール画像を処理
    processed_image_data = media_processor.convert_to_rgb(img_io.getvalue())
    processed_img = Image.open(BytesIO(processed_image_data))
    
    # RGB形式に変換されていることを確認
    assert processed_img.mode == 'RGB' 