from pathlib import Path

def get_project_root() -> Path:
    """
    このファイルが存在する場所を基準にプロジェクトのルートディレクトリを取得する。
    想定: project_root/engine_core/utils/file_utils.py
    """
    return Path(__file__).parent.parent.parent 