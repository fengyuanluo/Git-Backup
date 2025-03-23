import os
import logging

logger = logging.getLogger('git_backup')

class AuthManager:
    def __init__(self):
        self.logger = logger
    
    def verify_password(self, password):
        """验证管理员密码"""
        return password == os.getenv('ADMIN_PASSWORD') 