import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from git import Repo, GitCommandError
from flask_socketio import emit
import time
import git

class RestoreManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.logger = logging.getLogger('git_backup.restore')
        self.socketio = None
        self.logger.info(f"初始化还原管理器，基础目录: {base_dir}")

    def set_socketio(self, socketio):
        """设置WebSocket实例"""
        self.socketio = socketio
        self.logger.info("WebSocket实例已设置")

    def emit_status(self, task_id: int, status: str, message: str):
        """发送状态更新到WebSocket"""
        if self.socketio:
            try:
                self.logger.debug(f"发送状态更新 - 任务ID: {task_id}, 状态: {status}, 消息: {message}")
                self.socketio.emit('restore_status', {
                    'task_id': task_id,
                    'status': status,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"发送WebSocket消息失败: {str(e)}")

    def get_task_info(self, task_id: int) -> Dict:
        """获取任务信息的辅助方法"""
        from modules.config import Config
        config = Config()
        task = config.get_task(task_id)
        
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        source_path = task.get('source_path')
        if not source_path:
            raise ValueError(f"任务 {task_id} 缺少源目录路径")
        
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"源目录不存在: {source_path}")
            
        return task

    def init_repo(self, source_path: str) -> Repo:
        """初始化Git仓库的辅助方法"""
        try:
            repo = Repo(source_path)
            if not repo.git_dir:
                raise ValueError(f"无效的Git仓库: {source_path}")
            return repo
        except Exception as e:
            raise ValueError(f"初始化Git仓库失败: {str(e)}")

    def get_commit_history(self, task_id: int, page: int = 1, per_page: int = 10) -> Dict:
        """获取提交历史"""
        try:
            self.logger.info(f"开始获取任务 {task_id} 的提交历史 (页码: {page}, 每页数量: {per_page})")
            self.emit_status(task_id, 'info', '开始获取提交历史...')

            task = self.get_task_info(task_id)
            repo = self.init_repo(task['source_path'])
            commits = []

            # 更新远程仓库
            try:
                self.logger.info("正在从远程仓库获取更新...")
                self.emit_status(task_id, 'info', '正在从远程仓库获取更新...')
                repo.git.fetch('--all')
                self.logger.info("远程仓库更新成功")
            except GitCommandError as e:
                self.logger.warning(f"获取远程更新失败: {str(e)}")
                self.emit_status(task_id, 'warning', '获取远程更新失败，将使用本地提交历史')

            # 获取任务配置的分支
            target_branch = task.get('branch', 'main')
            
            # 获取提交历史
            try:
                # 优先尝试获取远程分支的提交历史
                remote_ref = f'origin/{target_branch}'
                if remote_ref in repo.refs:
                    commit_iter = repo.iter_commits(remote_ref)
                    branch_name = target_branch
                else:
                    # 如果远程分支不存在，尝试获取本地分支
                    if target_branch in repo.heads:
                        commit_iter = repo.iter_commits(target_branch)
                        branch_name = target_branch
                    else:
                        self.logger.warning(f"分支 {target_branch} 不存在，无法获取提交历史")
                        self.emit_status(task_id, 'warning', f'分支 {target_branch} 不存在')
                        return {"commits": [], "total_pages": 0, "current_page": page, "total_commits": 0, "per_page": per_page}
                
                for commit in commit_iter:
                    commit_info = {
                        "hash": commit.hexsha,
                        "message": commit.message.strip(),
                        "date": commit.committed_datetime.isoformat(),
                        "author": commit.author.name,
                        "branch": branch_name,
                        "stats": {
                            "files": len(commit.stats.files),
                            "insertions": commit.stats.total["insertions"],
                            "deletions": commit.stats.total["deletions"]
                        }
                    }
                    commits.append(commit_info)

            except GitCommandError as e:
                self.logger.error(f"获取分支 {target_branch} 的提交历史失败: {str(e)}")
                self.emit_status(task_id, 'error', f'获取分支 {target_branch} 的提交历史失败')
                return {"commits": [], "total_pages": 0, "current_page": page, "total_commits": 0, "per_page": per_page}

            # 分页处理
            total_commits = len(commits)
            total_pages = (total_commits + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page

            result = {
                "commits": commits[start_idx:end_idx],
                "total_pages": total_pages,
                "current_page": page,
                "total_commits": total_commits,
                "per_page": per_page,
                "branch": branch_name
            }

            self.logger.info(f"成功获取分支 {branch_name} 的提交历史，当前页: {page}/{total_pages}, 总提交数: {total_commits}")
            self.emit_status(task_id, 'success', f'成功获取分支 {branch_name} 的提交历史，共 {total_commits} 个提交')

            return result

        except Exception as e:
            error_msg = f"获取提交历史失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.emit_status(task_id, 'error', error_msg)
            raise

    def restore_commit(self, task_id, commit_hash, branch=None):
        """还原到指定的提交版本"""
        try:
            task = self.get_task_info(task_id)
            if not task:
                raise ValueError(f"任务 {task_id} 不存在")

            self.logger.info(f"开始还原任务 {task_id} 到提交 {commit_hash}")
            self.emit_status(task_id, 'info', f'开始还原到提交 {commit_hash[:8]}...')

            # 获取目标分支，优先使用参数指定的分支，其次是任务配置的分支
            target_branch = branch or task.get('branch', 'main')
            self.logger.info(f"目标分支: {target_branch}")
            
            # 获取或创建临时分支名称
            temp_branch = f'restore_{int(time.time())}'
            
            # 设置Git凭据
            self._setup_git_credentials(task)
            
            repo = self.init_repo(task['source_path'])
            remote = repo.remote('origin')
            
            # 确保本地有最新的远程分支信息
            try:
                self.logger.info("正在获取远程仓库更新...")
                remote.fetch()
                self.logger.info("成功获取远程仓库更新")
            except git.GitCommandError as e:
                self.logger.warning(f"获取远程更新失败: {str(e)}")
            
            # 验证提交是否存在
            try:
                commit = repo.commit(commit_hash)
                self.logger.info(f"找到目标提交: {commit.message.strip()}")
            except git.GitCommandError:
                error_msg = f"提交 {commit_hash} 不存在"
                self.logger.error(error_msg)
                self.emit_status(task_id, 'error', error_msg)
                return False
            
            # 创建并切换到临时分支
            self.logger.info(f"创建临时分支: {temp_branch}")
            self.emit_status(task_id, 'info', '正在创建临时分支...')
            
            if temp_branch in repo.heads:
                repo.delete_head(temp_branch, force=True)
            temp = repo.create_head(temp_branch, commit_hash)
            temp.checkout()
            
            try:
                # 执行还原
                self.logger.info("正在执行还原操作...")
                self.emit_status(task_id, 'info', '正在执行还原操作...')
                
                # 强制检出指定提交
                repo.git.reset('--hard', commit_hash)
                
                # 处理目标分支
                try:
                    # 检查远程是否存在目标分支
                    remote_branch_exists = False
                    for ref in remote.refs:
                        if ref.name == f'origin/{target_branch}':
                            remote_branch_exists = True
                            break

                    if target_branch in repo.heads:
                        # 本地分支存在
                        self.logger.info(f"切换到本地分支: {target_branch}")
                        current_branch = repo.heads[target_branch]
                        current_branch.checkout()
                    elif remote_branch_exists:
                        # 从远程创建本地分支
                        self.logger.info(f"从远程创建本地分支: {target_branch}")
                        repo.create_head(target_branch, f'origin/{target_branch}').checkout()
                    else:
                        # 创建新的本地分支
                        self.logger.info(f"创建新的本地分支: {target_branch}")
                        repo.create_head(target_branch, commit_hash).checkout()

                    # 合并临时分支
                    try:
                        self.logger.info(f"合并临时分支到 {target_branch}")
                        repo.git.merge(temp_branch, '--no-ff', m=f'还原到提交 {commit_hash[:8]}')
                        
                        # 推送到远程仓库
                        self.logger.info(f"推送更改到远程分支 {target_branch}")
                        remote.push(f'{target_branch}:{target_branch}', force=True)
                        
                        success_msg = f"成功还原到提交 {commit_hash[:8]} 并同步到远程仓库"
                        self.logger.info(success_msg)
                        self.emit_status(task_id, 'success', success_msg)
                        return True
                        
                    except git.GitCommandError as merge_error:
                        # 合并冲突处理
                        warning_msg = f"还原成功但存在合并冲突，更改已保存在分支 {temp_branch} 中"
                        self.logger.warning(warning_msg)
                        self.emit_status(task_id, 'warning', warning_msg)
                        return True
                        
                except git.GitCommandError as branch_error:
                    error_msg = f"切换到目标分支 {target_branch} 失败: {str(branch_error)}"
                    self.logger.error(error_msg)
                    self.emit_status(task_id, 'error', error_msg)
                    return False
                    
            except git.GitCommandError as restore_error:
                error_msg = f"还原操作失败: {str(restore_error)}"
                self.logger.error(error_msg)
                self.emit_status(task_id, 'error', error_msg)
                return False
                
            finally:
                # 清理临时分支
                if temp_branch in repo.heads:
                    current = repo.active_branch.name
                    if current != temp_branch:
                        repo.delete_head(temp_branch, force=True)
            
        except Exception as e:
            error_msg = f"还原失败: {str(e)}"
            self.logger.error(error_msg)
            self.emit_status(task_id, 'error', error_msg)
            return False

    def get_commit_details(self, task_id: int, commit_hash: str) -> Optional[Dict]:
        """获取提交详细信息"""
        try:
            self.logger.info(f"正在获取提交 {commit_hash} 的详细信息")
            self.emit_status(task_id, 'info', f'正在获取提交 {commit_hash[:8]} 的详细信息...')

            task = self.get_task_info(task_id)
            repo = self.init_repo(task['source_path'])

            try:
                commit = repo.commit(commit_hash)
                details = {
                    "hash": commit.hexsha,
                    "message": commit.message.strip(),
                    "date": commit.committed_datetime.isoformat(),
                    "author": commit.author.name,
                    "stats": {
                        "files_changed": len(commit.stats.files),
                        "insertions": commit.stats.total["insertions"],
                        "deletions": commit.stats.total["deletions"]
                    },
                    "files": [
                        {
                            "path": path,
                            "changes": stats["lines"],
                            "insertions": stats["insertions"],
                            "deletions": stats["deletions"]
                        }
                        for path, stats in commit.stats.files.items()
                    ]
                }

                self.logger.info(f"成功获取提交详情: {details['hash'][:8]}")
                self.emit_status(task_id, 'success', '成功获取提交详情')
                return details

            except GitCommandError:
                error_msg = f"提交不存在: {commit_hash}"
                self.logger.error(error_msg)
                self.emit_status(task_id, 'error', error_msg)
                return None

        except Exception as e:
            error_msg = f"获取提交详情失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.emit_status(task_id, 'error', error_msg)
            raise 