import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from git import Repo, GitCommandError
from flask_socketio import emit

class RestoreManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.logger = logging.getLogger(__name__)
        self.socketio = None  # 将在初始化时设置

    def set_socketio(self, socketio):
        """设置WebSocket实例"""
        self.socketio = socketio

    def emit_status(self, task_id: int, status: str, message: str):
        """发送状态更新到WebSocket"""
        if self.socketio:
            self.socketio.emit('restore_status', {
                'task_id': task_id,
                'status': status,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })

    def get_commit_history(self, task_id: int, page: int = 1, per_page: int = 10) -> Dict:
        """
        从远程仓库获取指定任务的提交历史
        
        Args:
            task_id: 任务ID
            page: 页码
            per_page: 每页数量
            
        Returns:
            Dict: 包含提交历史和分页信息的字典
        """
        try:
            self.logger.info(f"开始获取任务 {task_id} 的提交历史")
            self.emit_status(task_id, 'info', '开始获取提交历史...')

            task_dir = os.path.join(self.base_dir, f"task_{task_id}")
            if not os.path.exists(task_dir):
                self.logger.warning(f"任务目录不存在: {task_dir}")
                self.emit_status(task_id, 'error', '任务目录不存在')
                return {"commits": [], "total_pages": 0}

            repo = Repo(task_dir)
            commits = []
            
            # 确保远程仓库已更新
            try:
                self.logger.info(f"正在从远程仓库获取更新...")
                self.emit_status(task_id, 'info', '正在从远程仓库获取更新...')
                repo.git.fetch('--all')
                self.logger.info("远程仓库更新成功")
            except GitCommandError as e:
                self.logger.warning(f"获取远程仓库更新失败: {str(e)}")
                self.emit_status(task_id, 'warning', f'获取远程仓库更新失败: {str(e)}')
            
            # 获取默认分支
            try:
                default_branch = repo.active_branch.name
                self.logger.info(f"当前分支: {default_branch}")
            except Exception as e:
                self.logger.warning(f"获取当前分支失败，使用默认分支main: {str(e)}")
                default_branch = 'main'
            
            # 获取远程分支的提交历史
            try:
                self.logger.info(f"正在获取远程分支 {default_branch} 的提交历史...")
                self.emit_status(task_id, 'info', f'正在获取远程分支 {default_branch} 的提交历史...')
                remote_ref = f'origin/{default_branch}'
                for commit in repo.iter_commits(remote_ref):
                    commits.append({
                        "hash": commit.hexsha,
                        "message": commit.message.strip(),
                        "date": commit.committed_datetime.isoformat(),
                        "author": commit.author.name,
                        "branch": default_branch
                    })
                self.logger.info(f"成功获取到 {len(commits)} 个提交")
            except GitCommandError as e:
                self.logger.error(f"获取远程提交历史失败: {str(e)}")
                self.emit_status(task_id, 'warning', f'获取远程提交历史失败，尝试获取本地提交历史: {str(e)}')
                # 如果远程获取失败，尝试获取本地提交历史
                for commit in repo.iter_commits():
                    commits.append({
                        "hash": commit.hexsha,
                        "message": commit.message.strip(),
                        "date": commit.committed_datetime.isoformat(),
                        "author": commit.author.name,
                        "branch": default_branch
                    })
                self.logger.info(f"成功获取到 {len(commits)} 个本地提交")

            # 计算分页
            total_commits = len(commits)
            total_pages = (total_commits + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            
            result = {
                "commits": commits[start_idx:end_idx],
                "total_pages": total_pages,
                "current_page": page,
                "total_commits": total_commits
            }
            
            self.logger.info(f"成功获取提交历史，当前页: {page}/{total_pages}, 总提交数: {total_commits}")
            self.emit_status(task_id, 'success', f'成功获取提交历史，共 {total_commits} 个提交')
            
            return result

        except Exception as e:
            error_msg = f"获取提交历史失败: {str(e)}"
            self.logger.error(error_msg)
            self.emit_status(task_id, 'error', error_msg)
            raise

    def restore_to_commit(self, task_id: int, commit_hash: str) -> bool:
        """
        还原到指定的提交版本
        
        Args:
            task_id: 任务ID
            commit_hash: 提交哈希值
            
        Returns:
            bool: 是否还原成功
        """
        try:
            self.logger.info(f"开始还原任务 {task_id} 到提交 {commit_hash}")
            self.emit_status(task_id, 'info', f'开始还原到提交 {commit_hash[:8]}...')

            task_dir = os.path.join(self.base_dir, f"task_{task_id}")
            if not os.path.exists(task_dir):
                error_msg = f"任务目录不存在: {task_dir}"
                self.logger.error(error_msg)
                self.emit_status(task_id, 'error', error_msg)
                raise FileNotFoundError(error_msg)

            repo = Repo(task_dir)
            
            # 检查提交是否存在
            try:
                commit = repo.commit(commit_hash)
                self.logger.info(f"找到提交: {commit.message.strip()}")
            except GitCommandError:
                error_msg = f"提交不存在: {commit_hash}"
                self.logger.error(error_msg)
                self.emit_status(task_id, 'error', error_msg)
                raise ValueError(error_msg)

            # 执行还原
            self.logger.info("正在执行还原操作...")
            self.emit_status(task_id, 'info', '正在执行还原操作...')
            repo.git.reset("--hard", commit_hash)
            
            # 清理未跟踪的文件
            self.logger.info("正在清理未跟踪的文件...")
            self.emit_status(task_id, 'info', '正在清理未跟踪的文件...')
            repo.git.clean("-fd")
            
            success_msg = f"成功还原到提交 {commit_hash}"
            self.logger.info(success_msg)
            self.emit_status(task_id, 'success', success_msg)
            return True

        except Exception as e:
            error_msg = f"还原失败: {str(e)}"
            self.logger.error(error_msg)
            self.emit_status(task_id, 'error', error_msg)
            raise

    def get_commit_details(self, task_id: int, commit_hash: str) -> Optional[Dict]:
        """
        获取指定提交的详细信息
        
        Args:
            task_id: 任务ID
            commit_hash: 提交哈希值
            
        Returns:
            Optional[Dict]: 提交详细信息，如果不存在则返回None
        """
        try:
            self.logger.info(f"正在获取提交 {commit_hash} 的详细信息")
            self.emit_status(task_id, 'info', f'正在获取提交 {commit_hash[:8]} 的详细信息...')

            task_dir = os.path.join(self.base_dir, f"task_{task_id}")
            if not os.path.exists(task_dir):
                self.logger.warning(f"任务目录不存在: {task_dir}")
                return None

            repo = Repo(task_dir)
            
            try:
                commit = repo.commit(commit_hash)
                details = {
                    "hash": commit.hexsha,
                    "message": commit.message.strip(),
                    "date": commit.committed_datetime.isoformat(),
                    "author": commit.author.name,
                    "files_changed": len(commit.stats.files),
                    "insertions": commit.stats.total["insertions"],
                    "deletions": commit.stats.total["deletions"]
                }
                self.logger.info(f"成功获取提交详情: {details}")
                self.emit_status(task_id, 'success', '成功获取提交详情')
                return details
            except GitCommandError:
                error_msg = f"提交不存在: {commit_hash}"
                self.logger.error(error_msg)
                self.emit_status(task_id, 'error', error_msg)
                return None

        except Exception as e:
            error_msg = f"获取提交详情失败: {str(e)}"
            self.logger.error(error_msg)
            self.emit_status(task_id, 'error', error_msg)
            raise 