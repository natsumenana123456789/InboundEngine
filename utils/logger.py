import datetime
import logging
import os

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

    # フォーマッター
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # ファイルハンドラ
    fh = logging.FileHandler(log_file_path)
    fh.setLevel(level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # コンソールハンドラ
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger

def get_logger(logger_name=None):
    """
    設定済みのロガーを取得する。まだ設定されていなければデフォルトでセットアップする。
    """
    logger = logging.getLogger(logger_name)
    if not logger.hasHandlers(): # まだハンドラがなければデフォルト設定
        # ここでの log_dir_name は呼び出し元のスクリプトの位置に依存しないように注意
        # 各ボットの main.py などから呼び出されることを想定し、
        # setup_logger に渡す log_dir_name はプロジェクトルートからの相対パスが良い
        # もしくは、各ボットの main で setup_logger を呼び出す際、
        # ボットごとのログディレクトリを指定する。
        # ここではシンプルにプロジェクト直下の logs を想定
        return setup_logger(logger_name=logger_name)
    return logger

# auto_post_bot から移動してきた log 関数 (get_logger を使うように変更も可能)
def simple_log(message):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}")

if __name__ == '__main__':
    # 使用例
    logger1 = setup_logger(log_file_name='utils_test.log', logger_name='UtilLoggerTest')
    logger1.info("これはUtilLoggerTestからの情報ログです。")
    logger1.error("これはUtilLoggerTestからのエラーログです。")

    # 既存のauto_post_botのlog関数の呼び出し例
    simple_log("これはsimple_logからのメッセージです。")

    # get_logger の使用例
    app_logger = get_logger('AppDefaultLogger')
    app_logger.info("これはAppDefaultLoggerからの情報ログです。")

    another_logger = get_logger('AnotherModule') # 同じ名前で取得すれば同じインスタンス
    another_logger.warning("これはAnotherModuleからの警告ログです。") 