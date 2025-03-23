import os
from datetime import datetime
import git

class BackupManager:
    def backup_task(self, task_id):
        """执行备份任务"""
        task = self.get_task(task_id)
        if not task:
            self.logger.error(f"任务 {task_id} 不存在")
            return False

        self.logger.info(f"开始执行任务 {task_id}: {task['name']}")
        
        # 确保task包含webhook_url
        if 'webhook_url' not in task:
            task['webhook_url'] = os.environ.get('WEBHOOK_URL')
            if not task['webhook_url']:
                self.logger.warning("未配置webhook URL，将不会发送通知")
        
        try:
            repo = git.Repo(task['source_path'])
            
            # 获取目标分支
            target_branch = task.get('branch', 'main')  # 确保有默认值
            self.logger.info(f"目标分支: {target_branch}")
            
            # 检查远程仓库配置
            remote_name = 'origin'
            try:
                remote = repo.remote(remote_name)
                # 检查并更新远程URL
                current_url = remote.url
                if current_url != task['remote_url']:
                    self.logger.info(f"更新远程仓库URL: {task['remote_url']}")
                    remote.set_url(task['remote_url'])
            except ValueError:
                self.logger.info(f"创建远程仓库配置: {task['remote_url']}")
                remote = repo.create_remote(remote_name, task['remote_url'])
            
            # 设置Git凭据
            self._setup_git_credentials(task)
            
            # 获取当前分支状态
            try:
                current_branch = repo.active_branch.name
                self.logger.info(f"当前所在分支: {current_branch}")
            except (TypeError, AttributeError):
                self.logger.warning("当前处于HEAD分离状态")
                current_branch = None
            
            # 获取远程分支信息
            try:
                self.logger.info("正在获取远程仓库信息...")
                remote.fetch()
                remote_branches = [ref.name.split('/')[-1] for ref in remote.refs]
                self.logger.info(f"远程分支列表: {remote_branches}")
                
                # 检查远程是否存在目标分支
                remote_has_branch = target_branch in remote_branches
                self.logger.info(f"远程{'存在' if remote_has_branch else '不存在'}分支: {target_branch}")
            except git.GitCommandError as e:
                self.logger.warning(f"获取远程信息失败: {str(e)}")
                remote_has_branch = False
            
            # 处理本地分支
            if current_branch != target_branch:
                self.logger.info(f"需要切换到目标分支: {target_branch}")
                
                # 保存当前工作区更改
                if repo.is_dirty(untracked_files=True):
                    self.logger.info("保存当前工作区更改...")
                    repo.git.stash('save', f'自动保存更改 - 切换到分支 {target_branch}')
                
                try:
                    if target_branch in repo.heads:
                        # 本地已有此分支
                        self.logger.info(f"切换到已有的本地分支: {target_branch}")
                        branch = repo.heads[target_branch]
                    elif remote_has_branch:
                        # 从远程创建本地分支
                        self.logger.info(f"从远程创建本地分支: {target_branch}")
                        branch = repo.create_head(target_branch, f'origin/{target_branch}')
                        branch.set_tracking_branch(repo.refs[f'origin/{target_branch}'])
                    else:
                        # 创建全新的本地分支
                        self.logger.info(f"创建新的本地分支: {target_branch}")
                        branch = repo.create_head(target_branch)
                    
                    # 执行分支切换
                    self.logger.info(f"正在切换到分支: {target_branch}")
                    branch.checkout()
                    
                    # 恢复之前的更改
                    try:
                        if repo.git.stash('list'):
                            self.logger.info("恢复已保存的更改...")
                            repo.git.stash('pop')
                    except git.GitCommandError as e:
                        self.logger.warning(f"恢复更改失败: {str(e)}")
                    
                    # 验证分支切换结果
                    actual_branch = repo.active_branch.name
                    if actual_branch != target_branch:
                        raise git.GitCommandError("checkout", 
                            f"分支切换验证失败 - 当前: {actual_branch}, 目标: {target_branch}")
                    
                    self.logger.info(f"✅ 已成功切换到分支: {target_branch}")
                except git.GitCommandError as e:
                    error_msg = f"分支切换失败: {str(e)}"
                    self.logger.error(error_msg)
                    return self._handle_backup_error(task, error_msg)
            else:
                self.logger.info(f"已在目标分支 {target_branch} 上")
            
            # 再次验证当前分支
            try:
                actual_branch = repo.active_branch.name
                if actual_branch != target_branch:
                    raise git.GitCommandError("branch", 
                        f"分支状态异常 - 当前: {actual_branch}, 应该在: {target_branch}")
                self.logger.info(f"✅ 分支状态正确: {actual_branch}")
            except git.GitCommandError as e:
                return self._handle_backup_error(task, str(e))
            
            # 同步远程分支（如果存在）
            if remote_has_branch:
                try:
                    self.logger.info(f"尝试同步远程分支 {target_branch} ...")
                    repo.git.merge(f'origin/{target_branch}', '--ff-only')
                    self.logger.info("✅ 成功同步远程分支")
                except git.GitCommandError as e:
                    self.logger.warning(f"同步远程分支失败: {str(e)}")
                    self.logger.info("继续使用本地分支状态")
            
            # 检查是否有更改需要提交
            if repo.is_dirty(untracked_files=True):
                try:
                    # 添加所有更改
                    self.logger.info("添加更改到暂存区...")
                    repo.git.add(A=True)
                    
                    # 创建提交
                    commit_message = f"自动备份 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    self.logger.info(f"创建提交: {commit_message}")
                    commit = repo.index.commit(commit_message)
                    self.logger.info(f"✅ 提交成功: {commit.hexsha[:8]}")
                except git.GitCommandError as e:
                    return self._handle_backup_error(task, f"创建提交失败: {str(e)}")
            
            # 推送更改
            try:
                self.logger.info(f"推送更改到远程 {target_branch} 分支...")
                # 使用git命令直接推送
                try:
                    repo.git.push('origin', f'{target_branch}:{target_branch}', '--porcelain', v=True)
                    self.logger.info("✅ 推送成功")
                except git.GitCommandError as e:
                    if "non-fast-forward" in str(e):
                        self.logger.warning("检测到非快进推送，尝试使用force选项")
                        repo.git.push('origin', f'{target_branch}:{target_branch}', 
                                    '--force-with-lease', '--porcelain', v=True)
                        self.logger.info("✅ 强制推送成功")
                    else:
                        raise
                
                # 验证推送结果
                remote.fetch()
                if f'origin/{target_branch}' in repo.refs:
                    remote_commit = repo.refs[f'origin/{target_branch}'].commit
                    local_commit = repo.head.commit
                    if remote_commit.hexsha == local_commit.hexsha:
                        self.logger.info("✅ 推送验证成功")
                    else:
                        self.logger.warning("⚠️ 推送后远程分支状态与本地不一致")
                
                # 发送成功通知
                self.notification_manager.notify_backup_result(
                    task, True, 
                    commit_info=repo.head.commit.message
                )
                return True
                
            except git.GitCommandError as e:
                error_msg = f"推送失败: {str(e)}"
                self.logger.error(error_msg)
                self.notification_manager.notify_backup_result(
                    task, False,
                    error_message=error_msg
                )
                return False
                
        except git.GitCommandError as e:
            return self._handle_backup_error(task, f"Git操作失败: {str(e)}")
        except Exception as e:
            return self._handle_backup_error(task, f"备份失败: {str(e)}")

    def _handle_backup_error(self, task, error_message):
        """统一处理备份错误"""
        self.logger.error(error_message)
        self.notification_manager.notify_backup_result(
            task,
            False,
            error_message=error_message
        )
        return False 