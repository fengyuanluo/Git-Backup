import os
import requests
import logging
from datetime import datetime

logger = logging.getLogger('git_backup')

class NotificationManager:
    def __init__(self):
        self.logger = logger
    
    def format_backup_message(self, task, status, details=None):
        """格式化备份消息"""
        emoji = "✅" if status == "success" else "❌"
        status_text = "成功" if status == "success" else "失败"
        
        message = f"{emoji} Git备份任务通知\n\n"
        message += f"📋 任务名称：{task.get('name', '未命名')}\n"
        message += f"📁 源文件夹：{task.get('source_path', '未知')}\n"
        message += f"🔗 远程仓库：{task.get('remote_url', '未知')}\n"
        message += f"🌿 目标分支：{task.get('branch', 'main')}\n"
        message += f"⏰ 执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"📊 执行状态：{status_text}\n"
        
        if details:
            message += f"\n📝 详细信息：\n{details}"
        
        return message
    
    def send_notification(self, task, status, details=None):
        """发送通知"""
        webhook_url = task.get('webhook_url')
        if not webhook_url:
            self.logger.info("任务未配置Webhook URL，跳过通知")
            return
        
        try:
            message = self.format_backup_message(task, status, details)
            
            # 构建企业微信格式的消息
            payload = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }
            
            # 发送请求
            headers = {'Content-Type': 'application/json'}
            response = requests.post(webhook_url, json=payload, headers=headers)
            
            # 检查响应
            response.raise_for_status()
            response_json = response.json()
            
            if response_json.get('errcode') == 0:
                self.logger.info("Webhook通知发送成功")
                self.logger.debug(f"发送的消息内容: {message}")
            else:
                self.logger.error(f"Webhook通知发送失败: {response_json.get('errmsg', '未知错误')}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"发送Webhook请求失败: {str(e)}")
        except Exception as e:
            self.logger.error(f"处理Webhook通知时出错: {str(e)}")

    def notify_backup_result(self, task, success, error_message=None, commit_info=None):
        """发送备份结果通知"""
        status = "success" if success else "failure"
        
        if success:
            if commit_info:
                if commit_info == "没有需要备份的更改":
                    details = f"💡 {commit_info}"
                else:
                    # 提取提交信息中的时间
                    try:
                        if " - " in commit_info:
                            time_str = commit_info.split(" - ")[1]
                            details = f"⏱️ 提交时间：{time_str}\n📝 提交说明：{commit_info}"
                        else:
                            details = f"📝 提交说明：{commit_info}"
                    except Exception as e:
                        self.logger.error(f"处理提交信息时出错: {str(e)}")
                        details = f"📝 提交说明：{commit_info}"
        else:
            details = f"⚠️ 错误原因：{error_message}" if error_message else "⚠️ 未知错误"
        
        self.send_notification(task, status, details)

    def notify_restore_result(self, task, commit_hash, success, error_message=None):
        """发送还原结果通知"""
        status = "success" if success else "failure"
        
        if success:
            details = f"🔄 已还原到提交：{commit_hash[:8]}"
        else:
            details = f"⚠️ 错误原因：{error_message}" if error_message else "⚠️ 未知错误"
        
        self.send_notification(task, status, details)
    
    def send_success_notification(self, message):
        """发送成功通知"""
        task = {
            'name': '立即执行',
            'source_path': '当前目录',
            'remote_url': '未知',
            'branch': '当前分支',
            'webhook_url': os.environ.get('WEBHOOK_URL')
        }
        self.send_notification(task, 'success', f"💫 {message}")
    
    def send_error_notification(self, message):
        """发送错误通知"""
        task = {
            'name': '立即执行',
            'source_path': '当前目录',
            'remote_url': '未知',
            'branch': '当前分支',
            'webhook_url': os.environ.get('WEBHOOK_URL')
        }
        self.send_notification(task, 'failure', f"⚠️ {message}") 