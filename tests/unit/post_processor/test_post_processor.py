import pytest
from io import BytesIO
from PIL import Image
from src.post_processor import PostProcessor

@pytest.fixture
def post_processor():
    return PostProcessor()

@pytest.fixture
def sample_text():
    return "これはテスト投稿です。#テスト"

@pytest.fixture
def sample_image():
    """サンプル画像を作成"""
    img = Image.new('RGB', (800, 600), color='blue')
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    return img_io.getvalue()

def test_text_length_within_limit(post_processor, sample_text):
    """文字数制限内のテキスト処理テスト"""
    processed_text = post_processor.process_text(sample_text)
    assert len(processed_text) <= 280  # Twitterの文字数制限
    assert processed_text == sample_text  # 制限内なので変更なし

def test_text_length_exceeding_limit(post_processor):
    """文字数制限超過のテキスト処理テスト"""
    long_text = "あ" * 300  # 制限を超える文字数
    processed_text = post_processor.process_text(long_text)
    assert len(processed_text) == 280
    assert processed_text.endswith("...")  # 末尾に省略記号が付加される

def test_hashtag_preservation(post_processor):
    """ハッシュタグ保持テスト"""
    text_with_hashtags = "これはテストです。#テスト1 #テスト2 #テスト3"
    processed_text = post_processor.process_text(text_with_hashtags)
    assert "#テスト1" in processed_text
    assert "#テスト2" in processed_text
    assert "#テスト3" in processed_text

def test_url_handling(post_processor):
    """URL処理テスト"""
    text_with_url = "テスト https://example.com/long/url/path これは後続テキスト"
    processed_text = post_processor.process_text(text_with_url)
    assert "https://example.com" in processed_text
    assert len(processed_text) <= 280

def test_image_size_within_limit(post_processor, sample_image):
    """画像サイズ制限内の処理テスト"""
    processed_image = post_processor.process_image(sample_image)
    img = Image.open(BytesIO(processed_image))
    assert img.size[0] <= 4096  # Twitter画像の最大幅
    assert img.size[1] <= 4096  # Twitter画像の最大高さ

def test_image_size_exceeding_limit(post_processor):
    """画像サイズ制限超過の処理テスト"""
    # 大きすぎる画像を作成
    large_img = Image.new('RGB', (5000, 5000), color='red')
    img_io = BytesIO()
    large_img.save(img_io, 'JPEG')
    img_io.seek(0)
    
    processed_image = post_processor.process_image(img_io.getvalue())
    img = Image.open(BytesIO(processed_image))
    assert img.size[0] <= 4096
    assert img.size[1] <= 4096
    assert img.size[0] / img.size[1] == 5000 / 5000  # アスペクト比が保持される

def test_image_format_conversion(post_processor):
    """画像フォーマット変換テスト"""
    # PNG画像を作成
    png_img = Image.new('RGB', (800, 600), color='green')
    img_io = BytesIO()
    png_img.save(img_io, 'PNG')
    img_io.seek(0)
    
    processed_image = post_processor.process_image(img_io.getvalue())
    img = Image.open(BytesIO(processed_image))
    assert img.format in ['JPEG', 'PNG']  # Twitterでサポートされているフォーマットであることをチェック

def test_multiple_image_handling(post_processor, sample_image):
    """複数画像の処理テスト"""
    images = [sample_image] * 5  # 5枚の画像
    processed_images = post_processor.process_multiple_images(images)
    assert len(processed_images) <= 4  # Twitterの画像制限は4枚
    
    for img_data in processed_images:
        img = Image.open(BytesIO(img_data))
        assert img.size[0] <= 4096
        assert img.size[1] <= 4096

def test_invalid_image_handling(post_processor):
    """無効な画像データの処理テスト"""
    invalid_data = b'invalid image data'
    with pytest.raises(ValueError):
        post_processor.process_image(invalid_data)

def test_empty_text_handling(post_processor):
    """空のテキスト処理テスト"""
    assert post_processor.process_text("") == ""
    assert post_processor.process_text(None) == "" 