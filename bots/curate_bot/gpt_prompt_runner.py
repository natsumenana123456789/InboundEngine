import openai
import json
import os


def load_config(path):
    """設定ファイルを読み込む"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_gpt_api(prompt, text, api_key):
    """OpenAI APIを実行して結果を取得する"""
    client = openai.OpenAI(api_key=api_key)
    full_prompt = f"{prompt}\n\n{text}"  # プロンプトと入力テキストを結合

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # 最新モデル推奨、必要に応じて変更
            messages=[
                {
                    "role": "system",
                    "content": "あなたは有能な日本語アシスタントです。指示に従って、正確にタスクを実行してください。",
                },
                {"role": "user", "content": full_prompt},
            ],
            max_tokens=1500,  # 出力に応じて調整 (分類と本文で十分な長さを確保)
            temperature=0.2,  # 再現性を高めるために低めの温度設定
            # top_p=1.0,
            # frequency_penalty=0.0,
            # presence_penalty=0.0,
        )
        return response.choices[0].message.content.strip()
    except openai.APIConnectionError as e:
        print(f"❌ OpenAI API接続エラー: {e}")
    except openai.RateLimitError as e:
        print(f"❌ OpenAI APIレート制限エラー: {e}")
    except openai.APIStatusError as e:
        print(f"❌ OpenAI APIステータスエラー (HTTP {e.status_code}): {e.response}")
    except Exception as e:
        print(f"❌ OpenAI API呼び出し中に予期せぬエラー: {e}")
    return None  # エラー時はNoneを返す


def parse_gpt_output(gpt_response_text):
    """GPTの出力をパースして分類と整形済み本文を取得する"""
    final_classification = "案件投稿"  # デフォルトを「案件投稿」とする
    formatted_text = ""

    if not gpt_response_text:
        return {
            "classification": final_classification,
            "formatted_text": formatted_text,
        }

    lines = [
        line.strip() for line in gpt_response_text.strip().split("\n") if line.strip()
    ]

    classification_tag_found = False  # 【分類】：タグが見つかったか
    text_tag_found = False  # 【整形後OCR】：タグが見つかったか

    parsed_classification_value_from_gpt = None  # GPTが返した分類の値を一時的に保持

    # まず【分類】：を探す
    for i, line in enumerate(lines):
        if line.startswith("【分類】："):
            classification_tag_found = True
            classification_content = line.replace("【分類】：", "").strip()

            # 【分類】：と【整形後OCR】：が同じ行にある場合
            if "【整形後OCR】：" in classification_content:
                parts = classification_content.split("【整形後OCR】：", 1)
                parsed_classification_value_from_gpt = parts[0].strip()
                if len(parts) > 1:
                    formatted_text = parts[1].strip()
                text_tag_found = True
                break  # 両方見つかったので、このブロックの処理は終了
            else:
                parsed_classification_value_from_gpt = classification_content
                # 分類が見つかったので、残りの行から整形後OCRを探す
                text_lines_collector = []
                ocr_tag_started_in_this_block = False
                for j in range(i + 1, len(lines)):
                    sub_line = lines[j]
                    if sub_line.startswith("【整形後OCR】："):
                        text_lines_collector.append(
                            sub_line.replace("【整形後OCR】：", "").strip()
                        )
                        ocr_tag_started_in_this_block = True
                        text_tag_found = True
                    elif ocr_tag_started_in_this_block:  # 整形後OCRが開始された後の行
                        if sub_line.startswith(
                            "【分類】："
                        ):  # 次の分類が始まったら終了
                            break
                        text_lines_collector.append(sub_line)
                    elif not ocr_tag_started_in_this_block and sub_line.startswith(
                        "【分類】："
                    ):
                        # この分類に対応する整形後OCRが見つかる前に次の分類が始まった
                        break
                if text_lines_collector:
                    formatted_text = "\n".join(text_lines_collector).strip()
                break  # 【分類】：行の処理が終わったらループを抜ける

    # 【分類】：タグが見つからなかったか、または【整形後OCR】：がまだ見つかっていない場合、
    # 【整形後OCR】：タグを独立して探す
    if not text_tag_found:
        text_lines_collector = []
        ocr_tag_started_independently = False
        for i, line in enumerate(lines):  # 再度全行をチェック
            if line.startswith("【整形後OCR】："):
                text_lines_collector.append(line.replace("【整形後OCR】：", "").strip())
                ocr_tag_started_independently = True
                text_tag_found = True  # 【整形後OCR】：タグが見つかったことを記録
            elif ocr_tag_started_independently:
                # 整形後OCRが開始された後で、次の【分類】：や【整形後OCR】：が来たら、そこまでが整形後OCR
                if line.startswith("【分類】：") or line.startswith("【整形後OCR】："):
                    break
                text_lines_collector.append(line)
        if text_lines_collector:
            formatted_text = "\n".join(text_lines_collector).strip()

    # GPTから取得した分類の値に基づいて最終的な分類を決定
    if parsed_classification_value_from_gpt == "質問回答":
        final_classification = "質問回答"
    elif (
        parsed_classification_value_from_gpt
        and parsed_classification_value_from_gpt not in ["質問回答", "案件投稿"]
    ):
        # 「スルーデータ」やその他の予期しない分類が返ってきた場合
        print(
            f"⚠️ GPTによる分類結果 '{parsed_classification_value_from_gpt}' は「案件投稿」として扱います。"
        )
        # final_classification は既にデフォルトで "案件投稿"
    # parsed_classification_value_from_gpt が "案件投稿" または None の場合、final_classification は "案件投稿" のまま

    # どうしてもパースできない場合（タグが全く見つからない場合）、GPTの出力をそのまま整形後OCRとして扱う
    if not classification_tag_found and not text_tag_found and gpt_response_text:
        # プロンプトの出力形式に合致しないが、何らかのテキストはある場合
        # これが整形済み整形後OCRであると仮定する（リスクあり）
        # ただし、"【分類】"や"【整形後OCR】"という文字列自体を含まないことを確認
        if (
            "【分類】" not in gpt_response_text
            and "【整形後OCR】" not in gpt_response_text
        ):
            formatted_text = gpt_response_text  # そのまま整形後OCRとする
            # final_classification は "案件投稿" のまま
            print(
                "⚠️ GPT出力のパースに失敗。出力をそのまま整形後OCRとして扱います（分類は「案件投稿」）。"
            )

    # 以前の valid_classifications チェックは、この新しいロジックでは不要になります。
    # final_classification は常に "質問回答" または "案件投稿" のいずれかになるため。

    return {"classification": final_classification, "formatted_text": formatted_text}


def main():
    config_path = "config.json"
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        print(f"エラー: 設定ファイル {config_path} が見つかりません。")
        return
    except json.JSONDecodeError:
        print(f"エラー: 設定ファイル {config_path} のJSON形式が正しくありません。")
        return

    api_key = config.get("openai_api_key")
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")  # 環境変数からも試す
        if not api_key:
            print(
                f"エラー: {config_path}に 'openai_api_key' を追加するか、環境変数 OPENAI_API_KEY を設定してください。"
            )
            return

    prompt_file_path = "prompt.txt"
    try:
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            prompt_text_from_file = f.read()
    except FileNotFoundError:
        print(
            f"エラー: プロンプトファイル {prompt_file_path} が見つかりません。"
            "スクリプトと同じディレクトリに作成してください。"
        )
        return
    except Exception as e:
        print(f"エラー: {prompt_file_path} の読み込み中に問題が発生しました: {e}")
        return

    scraped_post_text = ""
    scraped_ocr_text = ""
    input_data_path = (
        "tweet_for_gpt.json"  # scrape_and_save_tweets.py が出力するファイル
    )
    try:
        with open(input_data_path, "r", encoding="utf-8") as f_scraped_data:
            data = json.load(f_scraped_data)
            scraped_post_text = data.get("post_text", "")  # 見つからない場合は空文字
            scraped_ocr_text = data.get("ocr_text", "")  # 見つからない場合は空文字
        print(f"📝 {input_data_path} からデータを読み込みました。")
    except FileNotFoundError:
        print(
            f"エラー: 入力データファイル {input_data_path} が見つかりません。"
            "scrape_and_save_tweets.py を実行して、先にデータファイルを作成してください。"
        )
        return  # このファイルがないと処理できないので終了
    except json.JSONDecodeError:
        print(f"エラー: {input_data_path} の内容が正しいJSON形式ではありません。")
        return
    except Exception as e:
        print(f"エラー: {input_data_path} の読み込み中に問題が発生しました: {e}")
        return

    # GPTへの入力テキストを動的に構築
    # プロンプト内で {{投稿本文をここに入れてください}} や {{画像から抽出した文字起こしをここに入れてください}}
    # といったプレースホルダーを使っている場合は、ここで置換する形式も考えられる。
    # 現在のプロンプトは末尾に入力フォーマット例があり、それに続けて本文とOCRを渡す形式。
    dynamic_input_text = f"""【投稿本文】:
{scraped_post_text}

【画像OCR】：
{scraped_ocr_text}
"""

    print("\n--- GPTへの入力 ---")
    # print(f"Prompt: \n{prompt_text_from_file}") # プロンプトが長いので全部表示は控える
    print(f"Input Text: \n{dynamic_input_text}")
    print("-------------------\n")

    gpt_raw_output = run_gpt_api(prompt_text_from_file, dynamic_input_text, api_key)

    if gpt_raw_output is None:
        print("❌ GPTからの応答がありませんでした。処理を中断します。")
        # エラー発生時は gpt_output.json に空またはエラー情報を含めて保存することも検討
        error_output = {
            "classification": "エラー",
            "formatted_text": "GPT API呼び出し失敗",
        }
        output_file_path = "gpt_output.json"
        try:
            with open(output_file_path, "w", encoding="utf-8") as f_out:
                json.dump(error_output, f_out, ensure_ascii=False, indent=2)
            print(f"ℹ️ エラー情報を {output_file_path} に保存しました。")
        except Exception as e_save:
            print(f"❌ エラー情報のファイル保存中にエラーが発生しました: {e_save}")
        return

    print("=== GPT Raw Output ===")
    print(gpt_raw_output)
    print("====================\n")

    parsed_gpt_result = parse_gpt_output(gpt_raw_output)

    print("=== Parsed GPT Result ===")
    print(json.dumps(parsed_gpt_result, ensure_ascii=False, indent=2))
    print("=======================\n")

    output_file_path = "gpt_output.json"  # scrape_and_save_tweets.py が読み込むファイル
    try:
        with open(output_file_path, "w", encoding="utf-8") as f_out:
            json.dump(parsed_gpt_result, f_out, ensure_ascii=False, indent=2)
        print(f"✅ GPTの処理結果を {output_file_path} に保存しました。")
    except Exception as e:
        print(f"❌ GPTの処理結果のファイル保存中にエラーが発生しました: {e}")


if __name__ == "__main__":
    main()
