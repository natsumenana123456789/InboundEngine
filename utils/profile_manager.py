import os
import shutil
from typing import Optional
from utils.logger import setup_logger

class ProfileManager:
    def __init__(self, base_dir: str = 'profiles', logger=None):
        self.base_dir = base_dir
        self.logger = logger or setup_logger(
            log_dir_name='logs',
            log_file_name='profile_manager.log',
            logger_name='ProfileManager'
        )
        os.makedirs(self.base_dir, exist_ok=True)

    def get_profile_path(self, account_id: str) -> str:
        """
        アカウントIDからプロファイルディレクトリのパスを取得
        """
        path = os.path.join(self.base_dir, account_id)
        self.logger.debug(f"プロファイルパス取得: {path}")
        return path

    def create_profile(self, account_id: str) -> str:
        """
        プロファイルディレクトリを作成（既存なら何もしない）
        """
        path = self.get_profile_path(account_id)
        os.makedirs(path, exist_ok=True)
        self.logger.info(f"プロファイル作成: {path}")
        return path

    def delete_profile(self, account_id: str) -> None:
        """
        プロファイルディレクトリを削除
        """
        path = self.get_profile_path(account_id)
        if os.path.exists(path):
            shutil.rmtree(path)
            self.logger.info(f"プロファイル削除: {path}")
        else:
            self.logger.warning(f"削除対象なし: {path}")

    def list_profiles(self) -> list:
        """
        管理下の全プロファイルディレクトリ一覧
        """
        profiles = [d for d in os.listdir(self.base_dir)
                    if os.path.isdir(os.path.join(self.base_dir, d))]
        self.logger.debug(f"プロファイル一覧: {profiles}")
        return profiles

    def profile_exists(self, account_id: str) -> bool:
        """
        プロファイルディレクトリの存在確認
        """
        path = self.get_profile_path(account_id)
        exists = os.path.exists(path)
        self.logger.debug(f"プロファイル存在確認: {path} => {exists}")
        return exists

if __name__ == '__main__':
    logger = setup_logger(log_dir_name='logs', log_file_name='profile_manager.log', logger_name='ProfileManager', level='DEBUG')
    pm = ProfileManager(logger=logger)
    test_id = 'test_account'
    pm.create_profile(test_id)
    print(pm.list_profiles())
    print(pm.profile_exists(test_id))
    pm.delete_profile(test_id)
    print(pm.list_profiles()) 