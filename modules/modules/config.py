import yaml
import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger('git_backup')

class Config:
    def __init__(self):
        self.config_file = 'config.yaml'
        self.tasks: List[Dict] = []
        self.logger = logging.getLogger(__name__)
        self.BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
        self.load_config()
    
    def load_config(self) -> None:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                    self.tasks = config_data.get('tasks', [])
                    self.logger.info(f"成功加载 {len(self.tasks)} 个任务")
            else:
                self.logger.info("配置文件不存在，将创建新的配置文件")
                self.save_config()
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            self.tasks = []
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump({'tasks': self.tasks}, f, allow_unicode=True, sort_keys=False)
            self.logger.info("配置文件保存成功")
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {str(e)}")
    
    def get_task(self, task_id: int) -> Optional[Dict]:
        """获取指定ID的任务"""
        for task in self.tasks:
            if task.get('id') == task_id:
                return task
        return None
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        return self.tasks
    
    def add_task(self, task_data: Dict) -> Dict:
        """添加新任务"""
        # 生成新的任务ID
        task_id = max([task.get('id', 0) for task in self.tasks], default=0) + 1
        task_data['id'] = task_id
        task_data['enabled'] = task_data.get('enabled', True)
        self.tasks.append(task_data)
        self.save_config()
        return task_data
    
    def update_task(self, task_id: int, task_data: Dict) -> Dict:
        """更新任务"""
        for i, task in enumerate(self.tasks):
            if task.get('id') == task_id:
                task_data['id'] = task_id
                self.tasks[i] = task_data
                self.save_config()
                return task_data
        raise ValueError(f"任务不存在: {task_id}")
    
    def delete_task(self, task_id: int) -> None:
        """删除任务"""
        self.tasks = [task for task in self.tasks if task.get('id') != task_id]
        self.save_config()
    
    def toggle_task(self, task_id: int) -> Dict:
        """切换任务状态"""
        task = self.get_task(task_id)
        if task:
            task['enabled'] = not task.get('enabled', True)
            self.save_config()
            return task
        raise ValueError(f"任务不存在: {task_id}")
    
    def get_next_task_id(self) -> int:
        """获取下一个可用的任务ID"""
        return max([task.get('id', 0) for task in self.tasks], default=0) + 1 