import re
import logging

class GitUtils:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def validate_branch_name(branch_name: str) -> tuple[bool, str]:
        """
        验证Git分支名称是否合法
        
        Args:
            branch_name: 分支名称
            
        Returns:
            tuple: (是否合法, 错误信息)
        """
        if not branch_name:
            return False, "分支名称不能为空"
            
        # Git分支命名规则
        # 不能以'.'开头
        if branch_name.startswith('.'):
            return False, "分支名称不能以'.'开头"
            
        # 不能包含特殊字符
        invalid_chars = ['..', '~', '^', ':', '?', '*', '[', '\\', ' ', '\t', '\n', '\r']
        for char in invalid_chars:
            if char in branch_name:
                return False, f"分支名称不能包含字符: {char}"
                
        # 不能以'/'结尾
        if branch_name.endswith('/'):
            return False, "分支名称不能以'/'结尾"
            
        # 不能包含连续的'..'
        if '..' in branch_name:
            return False, "分支名称不能包含连续的'.'"
            
        # 使用正则表达式验证
        pattern = r'^[a-zA-Z0-9\-\_\/\.]+$'
        if not re.match(pattern, branch_name):
            return False, "分支名称只能包含字母、数字、横线、下划线、斜杠和点"
            
        return True, ""

    @staticmethod
    def is_valid_remote_url(url: str) -> bool:
        """
        验证远程仓库URL是否合法
        
        Args:
            url: 远程仓库URL
            
        Returns:
            bool: 是否合法
        """
        # 支持的URL格式
        patterns = [
            # HTTPS格式
            r'^https:\/\/[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(:[0-9]+)?\/[a-zA-Z0-9\-\.\_\~\:\/\?\#\[\]\@\!\$\&\'\(\)\*\+\,\;\=]*$',
            # SSH格式
            r'^git@[a-zA-Z0-9\-\.]+:[a-zA-Z0-9\-\.\_\/]+\.git$',
            # 文件系统路径
            r'^file:\/\/\/?[a-zA-Z0-9\-\.\_\/\\]+$'
        ]
        
        return any(re.match(pattern, url) for pattern in patterns)

    @staticmethod
    def normalize_branch_name(branch_name: str) -> str:
        """
        规范化分支名称
        
        Args:
            branch_name: 原始分支名称
            
        Returns:
            str: 规范化后的分支名称
        """
        # 移除首尾空白
        branch_name = branch_name.strip()
        
        # 替换空格为横线
        branch_name = branch_name.replace(' ', '-')
        
        # 移除不允许的字符
        branch_name = re.sub(r'[^\w\-\.\/]', '', branch_name)
        
        # 确保不以'.'开头
        if branch_name.startswith('.'):
            branch_name = 'branch-' + branch_name
            
        # 确保不以'/'结尾
        branch_name = branch_name.rstrip('/')
        
        return branch_name

    @staticmethod
    def get_default_branch() -> str:
        """
        获取默认分支名称
        
        Returns:
            str: 默认分支名称
        """
        return 'main'  # 可以根据需要修改为其他默认分支名称 