import datetime
import logging
import os
import traceback
from logging import StreamHandler

def setup_logger(log_dir_name='logs', log_file_name='app.log', logger_name=None, level=logging.INFO):
    """
    汎用的なロガーをセットアップする関数。
    指定されたディレクトリにログファイルを作成し、
    コンソールにも同じログレベルで出力する。
    """
    # ルートからの相対パスでログディレクトリを設定
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    log_dir = os.path.join(project_root, log_dir_name)

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file_path = os.path.join(log_dir, log_file_name)

    # ロガーを取得 (指定がなければルートロガー)
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # 既存のハンドラをクリア (重複を避けるため)
    if logger.hasHandlers():
        logger.handlers.clear()

    # 詳細なフォーマッター
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )

    # ファイルハンドラ（詳細なフォーマット）
    fh = logging.FileHandler(log_file_path, encoding='utf-8')
    fh.setLevel(level)
    fh.setFormatter(detailed_formatter)
    logger.addHandler(fh)

    # コンソールハンドラ（簡潔なフォーマット）
    ch = StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)
    
    # flushを即時実行するためのラッパー
    class FlushOnEmitHandler(logging.Handler):
        def __init__(self, handler):
            super().__init__()
            self.handler = handler
        def emit(self, record):
            self.handler.emit(record)
            self.handler.flush()
    # 既存のハンドラをflush即時化
    logger.handlers = [FlushOnEmitHandler(h) for h in logger.handlers]
    
    return logger

def get_logger(logger_name=None):
    """
    設定済みのロガーを取得する。まだ設定されていなければデフォルトでセットアップする。
    """
    logger = logging.getLogger(logger_name)
    if not logger.hasHandlers(): # まだハンドラがなければデフォルト設定
        return setup_logger(logger_name=logger_name)
    return logger

def log_error(logger, message, exc_info=True):
    """
    エラーログを出力する際のヘルパー関数。
    スタックトレースを含む詳細なエラー情報を出力する。
    """
    if exc_info:
        logger.error(f"{message}\n{traceback.format_exc()}")
    else:
        logger.error(message)

def log_debug_with_context(logger, message, **context):
    """
    デバッグログを出力する際のヘルパー関数。
    コンテキスト情報を含めて出力する。
    """
    context_str = " ".join([f"{k}={v}" for k, v in context.items()])
    logger.debug(f"{message} | Context: {context_str}")

def log_info_with_context(logger, message, **context):
    """
    情報ログを出力する際のヘルパー関数。
    コンテキスト情報を含めて出力する。
    """
    context_str = " ".join([f"{k}={v}" for k, v in context.items()])
    logger.info(f"{message} | Context: {context_str}")

if __name__ == '__main__':
    # 使用例
    logger1 = setup_logger(log_file_name='utils_test.log', logger_name='UtilLoggerTest')
    logger1.info("これはUtilLoggerTestからの情報ログです。")
    logger1.error("これはUtilLoggerTestからのエラーログです。")

    # コンテキスト付きログの使用例
    log_info_with_context(logger1, "処理開始", user_id="123", action="login")
    try:
        raise ValueError("テストエラー")
    except Exception as e:
        log_error(logger1, "エラーが発生しました", exc_info=True)

    # get_logger の使用例
    app_logger = get_logger('AppDefaultLogger')
    app_logger.info("これはAppDefaultLoggerからの情報ログです。")

    another_logger = get_logger('AnotherModule')
    another_logger.warning("これはAnotherModuleからの警告ログです。") 