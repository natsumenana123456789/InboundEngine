'''
import os
import yaml
import re

def get_env_or_raise(env_var_name):
    """環境変数を取得するか、見つからない場合は例外を発生させます。"""
    value = os.environ.get(env_var_name)
    if value is None:
        raise ValueError(f"環境変数 {env_var_name} が設定されていません。")
    return value

def main():
    """
    config.template.yml と環境変数から config.yml を生成します。
    """
    template_path = "config/config.template.yml"
    output_path = "config/config.yml"

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()
    except FileNotFoundError:
        print(f"エラー: テンプレートファイル {template_path} が見つかりません。")
        return

    # プレースホルダーを環境変数の値で置換
    # {{ VAR_NAME }} の形式のプレースホルダーを検索
    def replace_placeholder(match):
        placeholder_name = match.group(1).strip() # VAR_NAME を取得
        try:
            return get_env_or_raise(placeholder_name)
        except ValueError as e:
            print(f"警告: {e}")
            # 環境変数が見つからない場合はプレースホルダーをそのまま残すか、
            # エラーにするかを選択できます。ここでは警告を出して空文字を返すか、
            # もしくはプレースホルダーをそのまま返すようにします。
            # GitHub ActionsのSecretが設定されていない場合のエラーハンドリングとして重要です。
            # ここでは、見つからない場合はプレースホルダーのままにしておき、
            # YAMLのパースエラーや後続処理でのエラーとして検知されるようにします。
            # return ""
            return f"{{{{ {placeholder_name} }}}}" # 元のプレースホルダー形式に戻す

    # template_content の {{ PLACEHOLDER }} を環境変数の値で置換
    # re.sub() を使用して、すべてのプレースホルダーを一度に処理
    config_content_str = re.sub(r"\{\{\s*(.*?)\s*\}\}", replace_placeholder, template_content)

    try:
        config_data = yaml.safe_load(config_content_str)
        if config_data is None:
            print(f"エラー: {template_path} からconfig.ymlを生成できませんでした。置換後の内容が不正です。")
            print("置換後の内容:")
            print(config_content_str)
            return
    except yaml.YAMLError as e:
        print(f"エラー: 生成されたconfigの内容が不正なYAML形式です。 {e}")
        print("置換後の内容:")
        print(config_content_str)
        return


    # gspread.credentials_json が文字列として設定されている場合、JSONとしてパースし直す
    # GitHub ActionsのSecretにはJSON文字列全体を登録するため、
    # それをYAML内でJSONオブジェクトとして解釈させる必要がある。
    if isinstance(config_data.get("gspread", {}).get("credentials_json"), str):
        try:
            # 文字列なので、それがJSON形式であることを期待してパース
            # YAMLはJSONのスーパーセットなので、正しく解釈されるはず
            # ただし、クォートが二重になっている場合など、一手間必要な場合がある
            # ここでは、環境変数から直接文字列として読み込まれることを想定
            # generate_config.py の置換処理で文字列として埋め込まれるので、
            # config_data["gspread"]["credentials_json"] は単なる文字列になっている。
            # これを `gspread` ライブラリが直接使えるようにするには、
            # この文字列をパースして辞書オブジェクトにする必要がある。
            # しかし、 `Config` クラスの `_load_gspread_credentials` で
            # `json.loads()` を行うのであれば、ここでは何もしなくて良い。
            # `Config`クラスが文字列のまま受け取って `json.loads` する前提で進める。
            pass # Configクラス側でjson.loadsするので、ここでは何もしない
        except Exception as e:
            print(f"警告: gspread.credentials_json のパースに失敗しました。{e}")
            print("gspread.credentials_json の内容:", config_data.get("gspread", {}).get("credentials_json"))
            # パースに失敗した場合でも、そのまま文字列として保持しておく。
            # Configクラス側でのエラーハンドリングに任せる。


    try:
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
        print(f"{output_path} を生成しました。")
    except Exception as e:
        print(f"エラー: {output_path} の書き込みに失敗しました。 {e}")

if __name__ == "__main__":
    main()
''' 