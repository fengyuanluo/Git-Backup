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

### 方式一：本地安装

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

### 方式二：Docker部署

1. 使用Docker Compose部署：
```bash
# 下载docker-compose.yml和.env.example文件
cp .env.example .env
# 编辑.env文件设置环境变量
docker-compose up -d
```

2. 使用Docker命令部署：
```bash
docker pull ghcr.io/[username]/git-backup:latest
docker run -d \
  --name git-backup \
  -p 5000:5000 \
  -v $(pwd)/backups:/app/backups \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v ~/.ssh:/root/.ssh:ro \
  -e SECRET_KEY=your-secret-key \
  -e ADMIN_PASSWORD=admin \
  ghcr.io/[username]/git-backup:latest
```

## 配置说明

### 环境变量

- `SECRET_KEY`: Flask应用密钥
- `HOST`: 应用监听地址（默认：0.0.0.0）
- `PORT`: 应用监听端口（默认：5000）
- `ADMIN_PASSWORD`: 管理员密码（默认：admin）
- `WEBHOOK_ENABLED`: 是否启用全局Webhook通知（默认：false）
- `WEBHOOK_URL`: 全局企业微信Webhook地址
- `MENTIONED_LIST`: 需要@的用户列表（默认：@all）
- `MENTIONED_MOBILE_LIST`: 需要@的手机号列表（默认：@all）
- `GIT_PYTHON_TRACE`: Git操作日志级别（默认：full）
- `TZ`: 时区设置（默认：Asia/Shanghai）
- `SSH_KEY_PATH`: SSH密钥路径（Docker部署时使用，默认：~/.ssh）

### Webhook配置说明

系统支持两级Webhook配置：
1. 全局Webhook配置：通过环境变量`WEBHOOK_URL`设置，适用于所有备份任务
2. 任务级Webhook配置：在创建或编辑任务时单独设置`webhook_url`，仅对特定任务生效

当任务配置了自己的Webhook URL时，将优先使用任务级配置，否则使用全局配置。

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

## 发布新版本

本项目使用 GitHub Actions 自动构建和发布多平台可执行文件。每当推送新的版本标签时，GitHub Actions 将自动构建并发布新版本。

### 发布步骤

1. 确保所有更改已经提交到主分支
2. 创建新的版本标签：
   ```bash
   git tag v1.0.0  # 将版本号替换为实际版本号
   git push origin v1.0.0
   ```
3. GitHub Actions 将自动执行以下操作：
   - 为 Windows、Linux 和 macOS 构建可执行文件
   - 创建发布版本
   - 上传构建的可执行文件到发布页面

### 下载

访问 [Releases](../../releases) 页面下载最新版本。提供以下版本：

- Windows: `git-backup-windows.zip`
- Linux: `git-backup-linux.zip`
- macOS: `git-backup-macos.zip`

### 版本命名规则

版本号遵循语义化版本规范 (Semantic Versioning)：

- 主版本号：不兼容的API修改
- 次版本号：向下兼容的功能性新增
- 修订号：向下兼容的问题修正

例如：v1.0.0、v1.1.0、v1.1.1

## 开发相关

如果您想参与开发，请按照以下步骤操作：

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request