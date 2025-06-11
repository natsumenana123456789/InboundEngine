import logging
import sys

def get_logger(name: str, level=logging.INFO) -> logging.Logger:
    """
    指定された名前でロガーを取得し、基本的な設定を適用する。
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 既にハンドラが設定されている場合は追加しない
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger 