# Git备份任务管理系统

一个基于Flask的Git备份任务管理系统，支持定时备份、多种认证方式和Webhook通知。

## 功能特点

- 支持多个Git备份任务管理
- 支持Token和SSH两种认证方式
- 支持定时任务（Cron表达式）
- 支持立即执行备份
- 支持企业微信Webhook通知
- 美观的Web界面
- 完整的日志记录
- 高可用性和可扩展性

## 系统要求

- Python 3.7+
- Git
- 现代浏览器（支持ES6+）

## 安装步骤

1. 克隆仓库：
```bash
git clone [repository-url]
cd git-backup
```

2. 创建虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，设置必要的配置项
```

## 配置说明

### 环境变量

- `SECRET_KEY`: Flask应用密钥
- `HOST`: 应用监听地址
- `PORT`: 应用监听端口
- `ADMIN_PASSWORD`: 管理员密码
- `WEBHOOK_ENABLED`: 是否启用Webhook通知
- `WEBHOOK_URL`: 企业微信Webhook地址
- `MENTIONED_LIST`: 需要@的用户列表
- `MENTIONED_MOBILE_LIST`: 需要@的手机号列表

### 任务配置

每个备份任务包含以下配置项：

- `name`: 任务名称
- `source_path`: 源文件夹路径
- `remote_url`: 远程仓库URL
- `auth_type`: 认证方式（token/ssh）
- `schedule`: Cron表达式（可选）
- `webhook_url`: 任务特定的Webhook URL（可选）

## 使用方法

1. 启动应用：
```bash
python app.py
```

2. 访问Web界面：
```
http://localhost:5000
```

3. 使用管理员密码登录

4. 添加备份任务：
   - 点击"添加任务"按钮
   - 填写任务信息
   - 选择认证方式
   - 设置定时任务（可选）
   - 配置Webhook通知（可选）

5. 管理任务：
   - 编辑任务
   - 启用/禁用任务
   - 删除任务
   - 立即执行备份

## 日志

- 应用日志位于 `logs/git_backup.log`
- 日志文件自动轮转，最大10MB，保留5个备份

## 注意事项

1. 确保Git已正确安装并添加到系统PATH
2. 使用SSH认证时，确保SSH密钥权限正确（600）
3. 生产环境部署时，请修改默认密码和密钥
4. 建议使用HTTPS或SSH协议访问远程仓库

## 常见问题

1. Git认证失败
   - 检查Token是否有效
   - 检查SSH密钥权限
   - 确认远程仓库URL格式正确

2. 定时任务不执行
   - 检查Cron表达式格式
   - 确认系统时间正确
   - 查看应用日志

3. Webhook通知失败
   - 检查Webhook URL是否有效
   - 确认网络连接正常
   - 查看应用日志

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 许可证

MIT License 