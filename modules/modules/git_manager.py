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
    
    def init_git_repo(self, repo_path, remote_url):
        """初始化Git仓库"""
        try:
            if not os.path.exists(os.path.join(repo_path, '.git')):
                self.logger.info(f"初始化新仓库: {repo_path}")
                repo = git.Repo.init(repo_path)
                
                # 设置默认分支为main
                default_branch = 'main'
                repo.git.branch('-M', default_branch)
                
                # 设置远程仓库
                if 'origin' in repo.remotes:
                    repo.delete_remote('origin')
                repo.create_remote('origin', remote_url)
                
                return repo, default_branch, True  # True表示是新仓库
            else:
                repo = git.Repo(repo_path)
                
                # 获取当前分支
                try:
                    default_branch = repo.active_branch.name
                except TypeError:
                    default_branch = 'main'
                    repo.git.branch('-M', default_branch)
                
                # 更新远程仓库URL
                if 'origin' in repo.remotes:
                    if repo.remotes.origin.url != remote_url:
                        repo.delete_remote('origin')
                        repo.create_remote('origin', remote_url)
                else:
                    repo.create_remote('origin', remote_url)
                
                return repo, default_branch, False
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
            
            # 初始化或打开仓库
            try:
                repo, default_branch, is_new_repo = self.init_git_repo(repo_path, remote_url)
                
                # 添加所有更改
                repo.git.add(A=True)
                
                # 检查是否有更改需要提交
                if repo.is_dirty() or len(repo.untracked_files) > 0:
                    commit_message = f"Backup at {time.strftime('%Y-%m-%d %H:%M:%S')}"
                    repo.index.commit(commit_message)
                    self.logger.info(f"创建提交: {commit_message}")
                    
                    # 尝试推送更改
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            self.logger.info(f"尝试推送更改 (尝试 {attempt + 1}/{max_retries})")
                            repo.git.push('origin', default_branch, '--force')
                            self.logger.info("成功推送到远程仓库")
                            return True, f"✅ 备份成功\n\n📝 提交信息：{commit_message}"
                        except git.exc.GitCommandError as e:
                            if attempt == max_retries - 1:
                                raise
                            self.logger.warning(f"推送失败，将重试: {str(e)}")
                            time.sleep(2)  # 等待2秒后重试
                else:
                    self.logger.info("没有检测到需要备份的更改")
                    return True, "没有检测到需要备份的更改"
                    
            except git.exc.InvalidGitRepositoryError:
                error_msg = f"无效的Git仓库: {repo_path}"
                self.logger.error(error_msg)
                return False, error_msg
            except git.exc.NoSuchPathError:
                error_msg = f"路径不存在: {repo_path}"
                self.logger.error(error_msg)
                return False, error_msg
            except Exception as e:
                error_msg = f"Git操作失败: {str(e)}"
                self.logger.error(error_msg)
                return False, error_msg
        except Exception as e:
            error_msg = f"备份失败: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg 