import google.generativeai as genai
import requests
from PIL import Image
import io
import os
import yaml
from typing import Union
import random

def get_gemini_api_key():
    """
    環境変数または設定ファイルからGemini APIキーを取得する（今回はconfig.ymlから直接渡す想定なので簡略化）
    実際にはconfig_loaderなどを使うべきだが、まずはシンプルに。
    """
    # ここでは config.yml から直接読み込まず、呼び出し元でキーを渡すことを想定
    # return os.getenv("GEMINI_API_KEY") # 環境変数の場合
    pass # 呼び出し元でキーを渡す

def ocr_with_gemini_vision(api_key: str, image_url: str) -> Union[str, None]:
    """
    指定された画像URLからGemini Visionモデルを使ってテキストを抽出する。

    Args:
        api_key: Gemini APIキー
        image_url: OCR対象の画像URL

    Returns:
        抽出されたテキスト。エラー時はNone。
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro-vision')

        # --- User-Agentの設定を追加 ---
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36" # デフォルト
        try:
            # config.ymlから読み込む (ocr_utils.pyから見て ../config/config.yml)
            config_path_for_ua = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yml')
            with open(config_path_for_ua, 'r') as f:
                config_data_ua = yaml.safe_load(f)
            user_agents_list = config_data_ua.get("common", {}).get("default_user_agents", [])
            if user_agents_list:
                user_agent = random.choice(user_agents_list)
        except Exception as e:
            print(f"User-Agent設定の読み込み中にエラーが発生しました（デフォルト値を使用）: {e}")
            pass # 読み込めなくてもデフォルトで続行
        
        headers = {'User-Agent': user_agent}
        # --- ここまで追加 ---

        # 画像をダウンロード
        print(f"画像をダウンロード中: {image_url} (User-Agent: {user_agent})") # ログ追加
        response = requests.get(image_url, stream=True, headers=headers) # headersを追加
        response.raise_for_status() # HTTPエラーがあれば例外を発生
        
        # PILで画像を開く
        img = Image.open(io.BytesIO(response.content))

        # Gemini APIに画像を送信してテキストを生成
        # プロンプトは必要に応じて調整
        # 単純なOCRなので、プロンプトは「この画像からテキストを読み取ってください。」などで十分
        generation_config = genai.types.GenerationConfig(temperature=0) # 確実性を高めるためtemperatureを0に
        response = model.generate_content(
            ["この画像からテキストを読み取ってください。", img],
            generation_config=generation_config,
            stream=False # OCRなのでストリーミングは不要
        )
        
        # response.text でテキスト部分を取得
        if response.candidates and response.candidates[0].content.parts:
            extracted_text = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
            return extracted_text.strip()
        else:
            print("Geminiからのレスポンスにテキストが含まれていませんでした。")
            return None

    except requests.exceptions.RequestException as e:
        print(f"画像のダウンロード中にエラーが発生しました: {image_url}, {e}")
        return None
    except Exception as e:
        print(f"Gemini Vision APIでのOCR処理中にエラーが発生しました: {e}")
        return None

if __name__ == '__main__':
    # 簡単なテスト用
    # config.yml からAPIキーを読み込む
    # ocr_utils.py の一つ上のディレクトリの config/config.yml を指す
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yml') 

    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        test_api_key = config_data.get("gemini_api", {}).get("api_key")
    except FileNotFoundError:
        print(f"設定ファイルが見つかりません: {config_path}")
        test_api_key = None
    except Exception as e:
        print(f"config.yml の読み込み中にエラーが発生しました: {e}")
        test_api_key = None

    if not test_api_key:
        print("テスト用のAPIキーが config.yml から取得できませんでした。")
    else:
        # テスト用の画像URL (Wikipediaのロゴなど、文字が含まれる画像)
        # test_image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png" # SVGはPILで直接開けない可能性あり
        test_image_url_png = "https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/220px-Wikipedia-logo-v2.svg.png" # PNG版
        # test_image_url_jpg = "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png" # Googleロゴ (OCRには不向きかも)
        
        print(f"Gemini APIキーを config.yml から読み込みました。")
        print(f"テスト画像URL: {test_image_url_png}")
        ocr_result = ocr_with_gemini_vision(test_api_key, test_image_url_png)

        if ocr_result:
            print("\nOCR結果:")
            print(ocr_result)
        else:
            print("\nOCR処理に失敗しました。") 