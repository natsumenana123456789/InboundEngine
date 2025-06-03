import pytest
from src.text_processor import TextProcessor

@pytest.fixture
def text_processor():
    return TextProcessor()

def test_normalize_text(text_processor):
    """テキストの正規化テスト"""
    # 全角文字の変換
    assert text_processor.normalize("１２３ＡＢＣ") == "123ABC"
    # 空白文字の正規化
    assert text_processor.normalize("  test   text  ") == "test text"
    # 改行の正規化
    assert text_processor.normalize("line1\r\nline2\rline3\n") == "line1\nline2\nline3"

def test_special_chars(text_processor):
    """特殊文字の処理テスト"""
    # 絵文字の保持
    assert text_processor.normalize("Hello 👋 World 🌍") == "Hello 👋 World 🌍"
    # 制御文字の除去
    assert text_processor.normalize("test\u0000text\u001F") == "testtext"
    # URLの保持
    assert text_processor.normalize("Check https://example.com") == "Check https://example.com"

def test_text_length(text_processor):
    """テキスト長制限のテスト"""
    # 最大文字数以内
    short_text = "a" * 280
    assert len(text_processor.normalize(short_text)) == 280
    # 最大文字数超過
    long_text = "a" * 300
    result = text_processor.normalize(long_text)
    assert len(result) == 280
    assert result.endswith("...") 