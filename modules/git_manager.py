import git
import os
import logging
import time

logger = logging.getLogger('git_backup')

class GitManager:
    def __init__(self):
        self.logger = logger
    
    def check_git_available(self):
        """检查Git是否可用"""
        try:
            git_version = git.Git().version()
            self.logger.info(f"Git version: {git_version}")
            return True
        except Exception as e:
            self.logger.error(f"Git not available: {str(e)}")
            return False
    
    def setup_git_auth(self, task):
        """配置Git认证"""
        auth_type = task.get('auth_type', 'token')
        remote_url = task['remote_url']
        
        try:
            if auth_type == 'token':
                if task.get('access_token'):
                    # 确保使用HTTPS URL格式
                    if remote_url.startswith('git@'):
                        remote_url = remote_url.replace('git@github.com:', 'https://github.com/')
                    if not remote_url.startswith('https://'):
                        remote_url = f'https://github.com/{remote_url.split("github.com/")[1]}'
                    token = task['access_token']
                    remote_url = remote_url.replace('https://', f'https://{token}@')
                    self.logger.info("已配置Personal Access Token认证")
                else:
                    self.logger.error("未提供Personal Access Token")
                    return None
            elif auth_type == 'ssh':
                if task.get('ssh_key_path'):
                    if os.path.exists(task['ssh_key_path']):
                        # 检查并修复SSH密钥权限
                        try:
                            current_mode = os.stat(task['ssh_key_path']).st_mode & 0o777
                            if current_mode != 0o600:
                                os.chmod(task['ssh_key_path'], 0o600)
                                self.logger.info(f"已修复SSH密钥权限: {task['ssh_key_path']}")
                        except Exception as e:
                            self.logger.error(f"修复SSH密钥权限失败: {str(e)}")
                            return None
                        
                        # 设置SSH命令，添加StrictHostKeyChecking=no选项
                        ssh_command = f"ssh -i {task['ssh_key_path']} -o StrictHostKeyChecking=no"
                        os.environ['GIT_SSH_COMMAND'] = ssh_command
                        self.logger.info(f"已配置SSH密钥: {task['ssh_key_path']}")
                        
                        # 确保使用SSH URL格式
                        if remote_url.startswith('https://'):
                            remote_url = remote_url.replace('https://', 'git@')
                            remote_url = remote_url.replace('github.com/', 'github.com:')
                            self.logger.info(f"已转换为SSH格式URL: {remote_url}")
                    else:
                        self.logger.error(f"SSH密钥文件不存在: {task['ssh_key_path']}")
                        return None
                elif task.get('ssh_key_content'):
                    # 如果提供了SSH密钥内容，创建临时密钥文件
                    try:
                        ssh_key_path = os.path.join(os.path.expanduser('~'), '.ssh', 'temp_key')
                        os.makedirs(os.path.dirname(ssh_key_path), exist_ok=True)
                        with open(ssh_key_path, 'w') as f:
                            f.write(task['ssh_key_content'])
                        os.chmod(ssh_key_path, 0o600)
                        
                        # 设置SSH命令
                        ssh_command = f"ssh -i {ssh_key_path} -o StrictHostKeyChecking=no"
                        os.environ['GIT_SSH_COMMAND'] = ssh_command
                        self.logger.info("已配置临时SSH密钥")
                        
                        # 确保使用SSH URL格式
                        if remote_url.startswith('https://'):
                            remote_url = remote_url.replace('https://', 'git@')
                            remote_url = remote_url.replace('github.com/', 'github.com:')
                    except Exception as e:
                        self.logger.error(f"配置SSH密钥内容失败: {str(e)}")
                        return None
                else:
                    self.logger.error("未提供SSH密钥")
                    return None
            
            return remote_url
        except Exception as e:
            self.logger.error(f"配置Git认证失败: {str(e)}")
            return None
    
    def init_git_repo(self, repo_path, remote_url, branch='main'):
        """初始化Git仓库"""
        try:
            if not os.path.exists(os.path.join(repo_path, '.git')):
                self.logger.info(f"初始化新仓库: {repo_path}")
                repo = git.Repo.init(repo_path)
                
                # 使用指定的分支名称
                repo.git.branch('-M', branch)
                
                # 设置远程仓库
                if 'origin' in repo.remotes:
                    repo.delete_remote('origin')
                repo.create_remote('origin', remote_url)
                
                return repo, branch, True  # True表示是新仓库
            else:
                repo = git.Repo(repo_path)
                
                # 获取当前分支，如果失败则使用指定的分支
                try:
                    current_branch = repo.active_branch.name
                except (TypeError, AttributeError):
                    current_branch = branch
                    repo.git.branch('-M', branch)
                
                # 更新远程仓库URL
                if 'origin' in repo.remotes:
                    if repo.remotes.origin.url != remote_url:
                        repo.delete_remote('origin')
                        repo.create_remote('origin', remote_url)
                else:
                    repo.create_remote('origin', remote_url)
                
                # 确保分支存在并切换到指定分支
                if branch not in repo.heads:
                    # 检查远程是否有这个分支
                    repo.git.fetch('origin')
                    remote_branch = f'origin/{branch}'
                    if remote_branch in repo.refs:
                        # 从远程分支创建本地分支
                        repo.create_head(branch, remote_branch)
                    else:
                        # 创建新的本地分支
                        repo.create_head(branch)
                
                # 切换到指定分支
                repo.heads[branch].checkout()
                
                return repo, branch, False
        except Exception as e:
            self.logger.error(f"初始化Git仓库失败: {str(e)}")
            raise
    
    def handle_git_conflicts(self, repo):
        """处理Git冲突"""
        try:
            # 检查是否有初始提交
            try:
                repo.head.reference
                has_commits = True
            except (TypeError, AttributeError):
                has_commits = False
                return  # 如果没有提交，直接返回
            
            if has_commits:
                # 获取默认分支
                try:
                    default_branch = repo.active_branch.name
                except TypeError:
                    default_branch = 'main'
                    repo.git.branch('-M', default_branch)
                
                # 检查是否有未提交的更改
                if repo.is_dirty():
                    self.logger.info("检测到未提交的更改")
                    self.logger.info("尝试暂存更改")
                    repo.git.stash()
                
                # 尝试拉取远程更改
                try:
                    # 先尝试获取远程分支信息
                    repo.git.remote('update')
                    remote_refs = repo.remote().refs
                    
                    # 检查远程分支是否存在
                    remote_branch_exists = False
                    for ref in remote_refs:
                        if ref.name == f'origin/{default_branch}':
                            remote_branch_exists = True
                            break
                    
                    if not remote_branch_exists:
                        self.logger.info(f"远程分支 {default_branch} 不存在，创建新分支")
                        # 创建并推送到远程main分支
                        repo.git.push('origin', f'{default_branch}:{default_branch}', '--set-upstream')
                        return
                    
                    # 强制拉取远程分支
                    self.logger.info(f"正在拉取远程 {default_branch} 分支")
                    repo.git.pull('origin', default_branch, '--force')
                    self.logger.info("成功拉取远程更改")
                except git.exc.GitCommandError as e:
                    if "CONFLICT" in str(e):
                        self.logger.warning("检测到冲突，尝试解决")
                        # 获取冲突文件
                        conflicts = repo.git.diff('--name-only', '--diff-filter=U')
                        if conflicts:
                            for file in conflicts.split('\n'):
                                # 对于每个冲突文件，尝试使用本地版本
                                repo.git.checkout('--ours', file)
                                repo.git.add(file)
                            # 完成合并
                            repo.git.commit('--no-edit')
                            self.logger.info("成功解决冲突")
                    else:
                        self.logger.warning(f"拉取远程更改失败: {str(e)}")
                
                # 如果有暂存的更改，尝试重新应用
                if repo.git.stash('list'):
                    try:
                        repo.git.stash('pop')
                        self.logger.info("成功恢复暂存的更改")
                    except git.exc.GitCommandError:
                        self.logger.error("恢复暂存的更改失败")
                        repo.git.stash('drop')
        except Exception as e:
            self.logger.error(f"处理Git冲突时出错: {str(e)}")
            raise
    
    def git_backup(self, task):
        """执行Git备份"""
        if not self.check_git_available():
            error_msg = "Git不可用，备份失败"
            self.logger.error(error_msg)
            return False, error_msg
        
        try:
            self.logger.info(f"开始备份任务: {task.get('name', '')} ({task['source_path']})")
            repo_path = task['source_path']
            branch = task.get('branch', 'main')  # 获取指定的分支
            
            # 检查源文件夹是否存在
            if not os.path.exists(repo_path):
                error_msg = f"源文件夹不存在: {repo_path}"
                self.logger.error(error_msg)
                return False, error_msg
            
            # 配置Git认证
            remote_url = self.setup_git_auth(task)
            if not remote_url:
                error_msg = "Git认证配置失败"
                self.logger.error(error_msg)
                return False, error_msg
            
            # 初始化或获取Git仓库
            try:
                repo, current_branch, is_new = self.init_git_repo(repo_path, remote_url, branch)
            except Exception as e:
                error_msg = f"初始化Git仓库失败: {str(e)}"
                self.logger.error(error_msg)
                return False, error_msg
            
            try:
                # 处理子目录中的Git仓库
                for root, dirs, files in os.walk(repo_path):
                    # 跳过.git目录
                    if '.git' in dirs:
                        dirs.remove('.git')
                    
                    # 检查是否有其他Git仓库
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        if os.path.exists(os.path.join(dir_path, '.git')):
                            # 将子目录中的Git仓库添加到.gitignore
                            relative_path = os.path.relpath(dir_path, repo_path)
                            gitignore_path = os.path.join(repo_path, '.gitignore')
                            
                            # 读取现有的.gitignore文件
                            ignored_paths = set()
                            if os.path.exists(gitignore_path):
                                with open(gitignore_path, 'r', encoding='utf-8') as f:
                                    ignored_paths = set(line.strip() for line in f if line.strip())
                            
                            # 添加新的路径到.gitignore
                            if relative_path not in ignored_paths:
                                with open(gitignore_path, 'a', encoding='utf-8') as f:
                                    f.write(f"\n{relative_path}/")
                                self.logger.info(f"已将子目录Git仓库添加到.gitignore: {relative_path}")
                
                # 添加所有文件到暂存区
                try:
                    repo.git.add('-A')
                except git.exc.GitCommandError as e:
                    if "does not have a commit checked out" in str(e):
                        # 如果遇到子目录Git仓库的问题，使用更安全的方式添加文件
                        for root, dirs, files in os.walk(repo_path):
                            # 跳过.git目录和.gitignore中指定的目录
                            if '.git' in dirs:
                                dirs.remove('.git')
                            if '.gitignore' in files:
                                with open(os.path.join(root, '.gitignore'), 'r', encoding='utf-8') as f:
                                    ignored = set(line.strip() for line in f if line.strip())
                                dirs[:] = [d for d in dirs if d not in ignored]
                            
                            # 添加当前目录下的文件
                            for file in files:
                                if file != '.gitignore':
                                    file_path = os.path.join(root, file)
                                    try:
                                        repo.git.add(file_path)
                                    except git.exc.GitCommandError:
                                        self.logger.warning(f"无法添加文件: {file_path}")
                    else:
                        raise
                
                # 检查是否有更改需要提交
                if repo.is_dirty() or repo.untracked_files:
                    # 创建提交
                    commit_message = f"Git备份 - {time.strftime('%Y-%m-%d %H:%M:%S')}"
                    repo.index.commit(commit_message)
                    self.logger.info("已创建新的提交")
                
                # 推送到远程仓库
                try:
                    repo.git.push('origin', current_branch, '--force')
                    self.logger.info(f"已推送到远程仓库: {current_branch}")
                    return True, "备份成功"
                except git.exc.GitCommandError as e:
                    error_msg = f"推送到远程仓库失败: {str(e)}"
                    self.logger.error(error_msg)
                    return False, error_msg
                
            except Exception as e:
                error_msg = f"Git操作失败: {str(e)}"
                self.logger.error(error_msg)
                return False, error_msg
            
        except Exception as e:
            error_msg = f"备份过程出错: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg 