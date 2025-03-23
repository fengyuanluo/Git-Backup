import os
import hashlib
import logging
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

logger = logging.getLogger('git_backup')

class TaskManager:
    def __init__(self, config, git_manager, notification_manager, scheduler):
        self.config = config
        self.git_manager = git_manager
        self.notification_manager = notification_manager
        self.scheduler = scheduler
        self.logger = logger
        self.tasks = {}
        self.load_tasks()
    
    def remove_job_safe(self, job_id):
        """安全地移除调度任务"""
        try:
            self.scheduler.remove_job(job_id)
        except Exception as e:
            self.logger.debug(f"移除任务调度失败 {job_id}: {str(e)}")
    
    def load_tasks(self):
        """从配置中加载所有任务并设置调度"""
        try:
            tasks = self.config.get_all_tasks()
            for task in tasks:
                task_id = task.get('id')
                if task_id:
                    self.tasks[task_id] = task
                    # 如果任务启用且有调度设置，添加到调度器
                    if task.get('enabled', True) and task.get('schedule'):
                        try:
                            self.scheduler.add_job(
                                self.git_backup_wrapper,
                                CronTrigger.from_crontab(task['schedule']),
                                args=[task_id],
                                id=f'task_{task_id}',
                                replace_existing=True
                            )
                        except Exception as e:
                            self.logger.error(f"添加任务调度失败 {task_id}: {str(e)}")
            self.logger.info(f"成功加载 {len(tasks)} 个任务")
        except Exception as e:
            self.logger.error(f"加载任务失败: {str(e)}")
            raise
    
    def is_duplicate_task(self, task_data, exclude_id=None):
        """检查是否存在重复任务"""
        tasks = self.config.get_all_tasks()
        for task in tasks:
            if exclude_id and task.get('id') == exclude_id:
                continue
            if (task.get('source_path') == task_data.get('source_path') and 
                task.get('remote_url') == task_data.get('remote_url')):
                return True
        return False
    
    def add_task(self, task_data):
        """添加新任务"""
        try:
            if self.is_duplicate_task(task_data):
                raise ValueError("已存在相同配置的任务")

            # 确保认证类型正确
            auth_type = task_data.get('auth_type', 'token')
            if auth_type not in ['token', 'ssh']:
                raise ValueError("不支持的认证类型")

            # 验证必要字段
            required_fields = ['name', 'source_path', 'remote_url']
            if auth_type == 'token':
                required_fields.append('access_token')
            elif auth_type == 'ssh':
                if not task_data.get('ssh_key_path') and not task_data.get('ssh_key_content'):
                    raise ValueError("SSH认证方式需要提供密钥文件路径或密钥内容")

            for field in required_fields:
                if not task_data.get(field):
                    raise ValueError(f"缺少必要字段: {field}")

            # 处理Webhook URL
            webhook_url = task_data.get('webhook_url', '').strip()
            if webhook_url:
                task_data['webhook_url'] = webhook_url
            else:
                task_data.pop('webhook_url', None)  # 如果没有Webhook URL，确保移除该字段

            # 生成任务ID
            task = self.config.add_task(task_data)
            task_id = task['id']

            # 如果设置了定时任务，添加到调度器
            if task.get('enabled', True) and task.get('schedule'):
                try:
                    self.scheduler.add_job(
                        self.git_backup_wrapper,
                        CronTrigger.from_crontab(task['schedule']),
                        args=[task_id],
                        id=f'task_{task_id}',
                        replace_existing=True
                    )
                except Exception as e:
                    self.logger.error(f"添加任务调度失败 {task_id}: {str(e)}")

            self.tasks[task_id] = task
            return task
        except Exception as e:
            self.logger.error(f"添加任务失败: {str(e)}")
            raise
    
    def update_task(self, task_id, task_data):
        """更新任务"""
        try:
            if self.is_duplicate_task(task_data, task_id):
                raise ValueError("已存在相同配置的任务")

            # 处理Webhook URL
            webhook_url = task_data.get('webhook_url', '').strip()
            if webhook_url:
                task_data['webhook_url'] = webhook_url
            else:
                task_data.pop('webhook_url', None)  # 如果没有Webhook URL，确保移除该字段

            # 更新任务配置
            task = self.config.update_task(task_id, task_data)
            if not task:
                raise ValueError("任务不存在")

            # 更新调度器中的任务
            job_id = f'task_{task_id}'
            self.remove_job_safe(job_id)
            
            if task.get('enabled', True) and task.get('schedule'):
                try:
                    self.scheduler.add_job(
                        self.git_backup_wrapper,
                        CronTrigger.from_crontab(task['schedule']),
                        args=[task_id],
                        id=job_id,
                        replace_existing=True
                    )
                except Exception as e:
                    self.logger.error(f"更新任务调度失败 {task_id}: {str(e)}")

            self.tasks[task_id] = task
            return task
        except Exception as e:
            self.logger.error(f"更新任务失败: {str(e)}")
            raise
    
    def delete_task(self, task_id):
        """删除任务"""
        try:
            # 从调度器中移除任务
            self.remove_job_safe(f'task_{task_id}')
            
            # 删除任务配置
            if not self.config.delete_task(task_id):
                raise ValueError("任务不存在")

            # 从内存中移除任务
            self.tasks.pop(task_id, None)
        except Exception as e:
            self.logger.error(f"删除任务失败: {str(e)}")
            raise
    
    def toggle_task(self, task_id):
        """切换任务状态"""
        try:
            task = self.config.get_task(task_id)
            if not task:
                raise ValueError("任务不存在")

            task['enabled'] = not task.get('enabled', True)
            task = self.config.update_task(task_id, task)

            # 更新调度器中的任务
            job_id = f'task_{task_id}'
            self.remove_job_safe(job_id)
            
            if task['enabled'] and task.get('schedule'):
                try:
                    self.scheduler.add_job(
                        self.git_backup_wrapper,
                        CronTrigger.from_crontab(task['schedule']),
                        args=[task_id],
                        id=job_id,
                        replace_existing=True
                    )
                except Exception as e:
                    self.logger.error(f"更新任务调度失败 {task_id}: {str(e)}")

            self.tasks[task_id] = task
            return task
        except Exception as e:
            self.logger.error(f"切换任务状态失败: {str(e)}")
            raise
    
    def get_task(self, task_id):
        """获取任务信息"""
        try:
            task_id = int(task_id)
            return self.tasks.get(task_id) or self.config.get_task(task_id)
        except (ValueError, TypeError):
            return None
    
    def get_all_tasks(self):
        """获取所有任务"""
        return list(self.tasks.values()) or self.config.get_all_tasks()
    
    def git_backup_wrapper(self, task_id):
        """执行Git备份任务的包装方法"""
        try:
            task = self.get_task(task_id)
            if not task:
                raise ValueError("任务不存在")

            # 执行Git备份
            success, message = self.git_manager.git_backup(task)

            # 发送通知
            if success:
                self.notification_manager.send_notification(
                    task,
                    'success',
                    message
                )
            else:
                self.notification_manager.send_notification(
                    task,
                    'error',
                    message
                )

            return success
        except Exception as e:
            error_message = f"执行任务 '{task_id}' 失败: {str(e)}"
            self.logger.error(error_message)
            self.notification_manager.send_notification(
                {'name': f'任务 {task_id}', 'source_path': '未知', 'remote_url': '未知'},
                'error',
                error_message
            )
            raise 