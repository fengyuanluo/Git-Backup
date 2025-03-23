from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import os
import git
import yaml
import requests
import logging
import shutil
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from functools import wraps
import hashlib
import time
from modules.config import Config
from modules.git_manager import GitManager
from modules.task_manager import TaskManager
from modules.auth_manager import AuthManager
from modules.notification_manager import NotificationManager
from modules.logger import setup_logger
from modules.restore_manager import RestoreManager

# 加载环境变量
load_dotenv()

# 初始化日志
logger = setup_logger()

# 初始化应用
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev')
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化登录管理器
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 初始化调度器
scheduler = BackgroundScheduler()
scheduler.start()

# 初始化各个管理器
config = Config()
git_manager = GitManager()
notification_manager = NotificationManager()
task_manager = TaskManager(config, git_manager, notification_manager, scheduler)

# 初始化还原管理器
restore_manager = RestoreManager(config.BACKUP_DIR)
restore_manager.set_socketio(socketio)  # 设置WebSocket实例

# 在文件开头的环境变量加载部分添加
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
MENTIONED_LIST = os.getenv('MENTIONED_LIST', '@all').split(',')
MENTIONED_MOBILE_LIST = os.getenv('MENTIONED_MOBILE_LIST', '@all').split(',')
WEBHOOK_ENABLED = os.getenv('WEBHOOK_ENABLED', 'false').lower() == 'true'
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route('/')
def index():
    """首页"""
    return render_template('index_vue.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        auth_manager = AuthManager()
        if auth_manager.verify_password(password):
            user = User(1)
            login_user(user)
            logger.info("用户登录成功")
            return redirect(url_for('index'))
        logger.warning("登录失败：密码错误")
        flash('密码错误')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    logger.info("用户登出")
    return redirect(url_for('login'))

def emit_task_update(task_id=None, action=None, data=None):
    """发送任务更新到前端"""
    socketio.emit('task_update', {
        'task_id': task_id,
        'action': action,
        'data': data
    })

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取所有任务"""
    try:
        tasks = task_manager.get_all_tasks()
        return jsonify(tasks)
    except Exception as e:
        logger.error(f"获取任务列表失败: {str(e)}")
        return jsonify({'error': '获取任务列表失败'}), 500

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """创建新的备份任务"""
    try:
        data = request.get_json()
        required_fields = ['name', 'source_path', 'remote_url', 'auth_type']
        
        # 验证必填字段
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'缺少必填字段: {field}'}), 400
        
        # 设置默认分支
        if 'branch' not in data:
            data['branch'] = 'main'
        
        # 插入任务数据
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO tasks (
                name, source_path, remote_url, branch, auth_type, 
                access_token, ssh_key_content, schedule, webhook_url, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['source_path'], data['remote_url'], data['branch'],
            data['auth_type'], data.get('access_token'), data.get('ssh_key_content'),
            data.get('schedule'), data.get('webhook_url'), 1
        ))
        
        task_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'id': task_id, 'message': '任务创建成功'}), 201
        
    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        return jsonify({'error': '创建任务失败'}), 500

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """更新任务"""
    try:
        task_data = request.get_json()
        task = task_manager.update_task(task_id, task_data)
        return jsonify(task)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"更新任务失败: {str(e)}")
        return jsonify({'error': '更新任务失败'}), 500

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    try:
        task_manager.delete_task(task_id)
        return jsonify({'message': '任务已删除'})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"删除任务失败: {str(e)}")
        return jsonify({'error': '删除任务失败'}), 500

@app.route('/api/tasks/<int:task_id>/toggle', methods=['POST'])
def toggle_task(task_id):
    """切换任务状态"""
    try:
        task = task_manager.toggle_task(task_id)
        return jsonify(task)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"切换任务状态失败: {str(e)}")
        return jsonify({'error': '切换任务状态失败'}), 500

@app.route('/api/tasks/<int:task_id>/run', methods=['POST'])
def run_task(task_id):
    """立即执行任务"""
    try:
        success = task_manager.git_backup_wrapper(task_id)
        return jsonify({'success': success})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"执行任务失败: {str(e)}")
        return jsonify({'error': '执行任务失败'}), 500

@app.route('/api/tasks/<int:task_id>/commits', methods=['GET'])
def get_commit_history(task_id):
    """获取任务的提交历史"""
    try:
        page = request.args.get('page', 1, type=int)
        history = restore_manager.get_commit_history(task_id, page)
        return jsonify(history)
    except Exception as e:
        logger.error(f"获取提交历史失败: {str(e)}")
        return jsonify({"error": "获取提交历史失败"}), 500

@app.route('/api/tasks/<int:task_id>/restore', methods=['POST'])
def restore_task(task_id):
    """还原任务到指定版本"""
    try:
        data = request.get_json()
        commit_hash = data.get('commit_hash')
        branch = data.get('branch')  # 获取目标分支参数
        
        if not commit_hash:
            return jsonify({'error': '缺少提交哈希值'}), 400
            
        # 执行还原
        success = restore_manager.restore_commit(task_id, commit_hash, branch)
        
        if success:
            return jsonify({"message": "还原成功"})
        else:
            return jsonify({"error": "还原任务失败"}), 500
            
    except Exception as e:
        logger.error(f"还原任务失败: {str(e)}")
        return jsonify({"error": "还原任务失败"}), 500

# WebSocket事件
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('task_update')
def handle_task_update(data):
    emit('task_updated', data, broadcast=True)

if __name__ == '__main__':
    logger.info("启动Git备份系统")
    if not git_manager.check_git_available():
        logger.warning("Git不可用，请确保Git已正确安装并添加到系统PATH中")
    socketio.run(app, host=HOST, port=PORT, debug=True) 