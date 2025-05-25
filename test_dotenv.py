# test_dotenv.py
import os
from dotenv import load_dotenv, find_dotenv

print(f"--- test_dotenv.py execution ---")
print(f"Current working directory: {os.getcwd()}")

dotenv_path = find_dotenv(filename='.env', raise_error_if_not_found=False, usecwd=True)
print(f"find_dotenv() path: {dotenv_path}")

loaded_explicit_path = False
loaded_auto_search = False

if dotenv_path:
    print(f"Attempting to load .env from: {dotenv_path}")
    loaded_explicit_path = load_dotenv(dotenv_path=dotenv_path, verbose=True, override=True)
    print(f"load_dotenv(path='{dotenv_path}') result: {loaded_explicit_path}")
else:
    print(f"No .env file found by find_dotenv(). Attempting load_dotenv() with auto-search.")
    loaded_auto_search = load_dotenv(verbose=True, override=True)
    print(f"load_dotenv() (auto-search) result: {loaded_auto_search}")

print(f"--- Environment Variables After Loading ---")
token = os.getenv('TWITTER_BEARER_TOKEN')
print(f"TWITTER_BEARER_TOKEN: {token}")

notion_token_env = os.getenv('NOTION_TOKEN')
print(f"NOTION_TOKEN: {notion_token_env}")

# .env ファイルが最小構成 (TWITTER_BEARER_TOKEN="TestToken123" のみ) の場合、
# NOTION_TOKEN は None になるはずです。
# もし元の .env の内容でテストする場合は、NOTION_TOKEN も読み込めるか確認できます。 