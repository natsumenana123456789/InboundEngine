# curate_bot/ocr_utils.py

import requests
from PIL import Image
import pytesseract
import io

def ocr_image_from_url(image_url):
    """
    画像URLから画像をダウンロードし、OCR処理を実行してテキストを抽出する。
    """
    if not image_url:
        return None
    try:
        response = requests.get(image_url, stream=True, timeout=10) # タイムアウト設定
        response.raise_for_status() # エラーがあれば例外を発生させる

        # メモリ上で画像を扱う
        image_bytes = io.BytesIO(response.content)
        img = Image.open(image_bytes)
        
        # OCR処理 (言語は日本語と英語を試みる)
        # Tesseractがインストールされているパスを環境変数や設定ファイルから読み込むか、
        # 必要に応じて pytesseract.pytesseract.tesseract_cmd に直接指定する必要があります。
        # ここでは、パスが通っているか、デフォルトの場所にあることを期待します。
        # 例: pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract' # macOSの場合の例
        # 例: pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' # Windowsの場合の例

        text = pytesseract.image_to_string(img, lang='jpn+eng') # 日本語と英語で試す
        return text.strip()
    except requests.exceptions.RequestException as e:
        print(f"画像ダウンロード失敗 ({image_url}): {e}")
        return None
    except pytesseract.TesseractNotFoundError:
        print("❌ Tesseract OCRエンジンが見つかりません。インストールされているか、パスが通っているか確認してください。")
        # ここでプログラムを終了させるか、エラーを伝播させるか検討。今回はNoneを返す。
        return None
    except Exception as e:
        print(f"OCR処理中にエラーが発生しました ({image_url}): {e}")
        return None

def ocr_images_from_urls(image_urls):
    """
    複数の画像URLを受け取り、それぞれOCR処理を行い、抽出されたテキストを結合して返す。
    """
    if not image_urls or not isinstance(image_urls, list):
        return None
    
    all_ocr_texts = []
    for url in image_urls:
        ocr_text = ocr_image_from_url(url)
        if ocr_text:
            all_ocr_texts.append(ocr_text)
    
    if not all_ocr_texts:
        return None
    
    return "\n\n---\n\n".join(all_ocr_texts) # 各画像のテキストを区切り文字で結合

if __name__ == '__main__':
    # テスト用
    test_urls_with_text = [
        "https://www.bannerbatterien.com/upload/filecache/Banner-Batterien-Logo-jpg_0x0_100_c53520092348a5ce143f9a11da8e1376.jpg", # Banner (英語)
        # 日本語の文字が含まれる画像のURLがあれば追加してテスト
    ]
    test_urls_no_text = ["https://via.placeholder.com/150"]

    print("--- 文字あり画像のテスト ---")
    result_with_text = ocr_images_from_urls(test_urls_with_text)
    if result_with_text:
        print("抽出されたテキスト:")
        print(result_with_text)
    else:
        print("テキストは抽出されませんでした。")

    print("\n--- 文字なし画像のテスト ---")
    result_no_text = ocr_images_from_urls(test_urls_no_text)
    if result_no_text:
        print("抽出されたテキスト:")
        print(result_no_text)
    else:
        print("テキストは抽出されませんでした。")

    # 単一URLテスト
    print("\n--- 単一URLテスト (Banner) ---")
    single_url_text = ocr_image_from_url("https://www.bannerbatterien.com/upload/filecache/Banner-Batterien-Logo-jpg_0x0_100_c53520092348a5ce143f9a11da8e1376.jpg")
    if single_url_text:
        print(single_url_text)
    else:
        print("テキスト抽出失敗") 