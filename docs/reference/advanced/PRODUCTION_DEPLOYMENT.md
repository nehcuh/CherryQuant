# CherryQuant 生产部署手册

## 目录

1. [系统要求](#系统要求)
2. [部署架构](#部署架构)
3. [前置准备](#前置准备)
4. [部署步骤](#部署步骤)
5. [配置管理](#配置管理)
6. [数据库设置](#数据库设置)
7. [安全配置](#安全配置)
8. [监控和日志](#监控和日志)
9. [备份和恢复](#备份和恢复)
10. [故障排查](#故障排查)
11. [滚动更新](#滚动更新)

---

## 系统要求

### 硬件要求

#### 最小配置
- **CPU**: 4 核
- **内存**: 8 GB
- **硬盘**: 100 GB SSD
- **网络**: 10 Mbps

#### 推荐配置
- **CPU**: 8 核（Intel Xeon 或 AMD EPYC）
- **内存**: 32 GB
- **硬盘**: 500 GB NVMe SSD
- **网络**: 100 Mbps
- **备用服务器**: 建议配置主备架构

### 软件要求

- **操作系统**: Ubuntu 22.04 LTS 或 CentOS 8+
- **Python**: 3.12+
- **MongoDB**: 4.4+ （推荐 5.0+）
- **Redis**: 6.0+
- **Docker**: 20.10+ （可选，推荐）
- **Docker Compose**: 2.0+ （可选，推荐）

---

## 部署架构

### 单机部署（适合测试和小规模）

```
┌────────────────────────────────────┐
│         Application Server         │
│  ┌──────────────────────────────┐  │
│  │   CherryQuant Application    │  │
│  │   - run_cherryquant_complete │  │
│  │   - Web API (FastAPI)        │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │   MongoDB (local)            │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │   Redis (local)              │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
```

### 生产部署（推荐）

```
                    ┌─────────────┐
                    │  Load       │
                    │  Balancer   │
                    │  (Nginx)    │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐        ┌────▼────┐       ┌────▼────┐
   │  App    │        │  App    │       │  App    │
   │  Node 1 │        │  Node 2 │       │  Node 3 │
   └────┬────┘        └────┬────┘       └────┬────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐        ┌────▼────┐       ┌────▼────┐
   │ MongoDB │◄──────►│ MongoDB │◄─────►│ MongoDB │
   │ Primary │        │ Secondary│       │ Secondary│
   └─────────┘        └─────────┘       └─────────┘

        ┌──────────────────────────────────┐
        │     Redis Cluster                │
        │  (Master-Slave with Sentinel)    │
        └──────────────────────────────────┘
```

---

## 前置准备

### 1. 服务器准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要工具
sudo apt install -y git curl wget vim htop ufw

# 配置防火墙
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### 2. 创建应用用户

```bash
# 创建专用用户（不要使用 root）
sudo adduser cherryquant
sudo usermod -aG sudo cherryquant

# 切换到应用用户
su - cherryquant
```

### 3. 安装 Python 3.12

```bash
# 使用 deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# 安装 uv（推荐）
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 4. 安装 MongoDB

```bash
# 导入 MongoDB GPG 密钥
wget -qO - https://www.mongodb.org/static/pgp/server-5.0.asc | sudo apt-key add -

# 添加 MongoDB 仓库
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/5.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-5.0.list

# 安装 MongoDB
sudo apt update
sudo apt install -y mongodb-org

# 启动 MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod
```

### 5. 安装 Redis

```bash
# 安装 Redis
sudo apt install -y redis-server

# 配置 Redis（生产环境）
sudo sed -i 's/supervised no/supervised systemd/' /etc/redis/redis.conf
sudo sed -i 's/# maxmemory <bytes>/maxmemory 2gb/' /etc/redis/redis.conf
sudo sed-i 's/# maxmemory-policy noeviction/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf

# 启动 Redis
sudo systemctl restart redis
sudo systemctl enable redis
```

---

## 部署步骤

### 方案 A：使用 Docker（推荐）

#### 1. 安装 Docker

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 2. 克隆代码

```bash
cd /opt
sudo git clone https://github.com/your-org/CherryQuant.git
sudo chown -R cherryquant:cherryquant /opt/CherryQuant
cd /opt/CherryQuant
```

#### 3. 配置环境变量

```bash
cp .env.example .env
vim .env  # 编辑配置（见下文"配置管理"）
```

#### 4. 构建和启动

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 方案 B：直接部署（无 Docker）

#### 1. 克隆代码

```bash
cd /opt
sudo git clone https://github.com/your-org/CherryQuant.git
sudo chown -R cherryquant:cherryquant /opt/CherryQuant
cd /opt/CherryQuant
```

#### 2. 安装依赖

```bash
# 使用 uv（推荐）
uv sync --frozen

# 或使用 pip
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

#### 3. 配置环境变量

```bash
cp .env.example .env
vim .env  # 编辑配置
```

#### 4. 初始化数据库

```bash
# 创建 MongoDB 索引
uv run python scripts/init_database.py

# 加载历史数据（可选）
uv run python scripts/init_historical_data.py
```

#### 5. 使用 systemd 管理服务

创建服务文件：

```bash
sudo vim /etc/systemd/system/cherryquant.service
```

内容：

```ini
[Unit]
Description=CherryQuant AI Trading System
After=network.target mongod.service redis.service
Wants=mongod.service redis.service

[Service]
Type=simple
User=cherryquant
Group=cherryquant
WorkingDirectory=/opt/CherryQuant
Environment="PATH=/opt/CherryQuant/.venv/bin"
EnvironmentFile=/opt/CherryQuant/.env
ExecStart=/opt/CherryQuant/.venv/bin/python run_cherryquant_complete.py
Restart=on-failure
RestartSec=10s

# 安全加固
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/CherryQuant/logs

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable cherryquant
sudo systemctl start cherryquant

# 查看状态
sudo systemctl status cherryquant

# 查看日志
sudo journalctl -u cherryquant -f
```

---

## 配置管理

### 环境变量清单

创建 `.env` 文件（**永远不要提交到 git**）：

```bash
# ===== 运行环境 =====
ENVIRONMENT=production
DEBUG=false
TIMEZONE=Asia/Shanghai

# ===== 数据源配置 =====
DATA_MODE=live  # dev/live

# CTP 配置（live 模式必需）
CTP_USERID=your_user_id
CTP_PASSWORD=your_password
CTP_BROKER_ID=9999
CTP_MD_ADDRESS=tcp://180.168.146.187:10211
CTP_TD_ADDRESS=tcp://180.168.146.187:10201
CTP_APP_ID=simnow_client_test
CTP_AUTH_CODE=0000000000000000

# Tushare 配置
TUSHARE_TOKEN=your_tushare_token

# ===== 数据库配置 =====
# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=cherryquant_prod
MONGODB_USERNAME=cherryquant
MONGODB_PASSWORD=your_strong_password_here
MONGODB_MIN_POOL_SIZE=10
MONGODB_MAX_POOL_SIZE=100

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0
CACHE_TTL=3600

# ===== AI 配置 =====
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_MAX_TOKENS=2000
OPENAI_TEMPERATURE=0.2

# ===== 风险管理 =====
MAX_TOTAL_CAPITAL_USAGE=0.8
PORTFOLIO_STOP_LOSS=0.15
DAILY_LOSS_LIMIT=0.05
MAX_POSITION_SIZE=0.2
MAX_SECTOR_CONCENTRATION=0.4
MAX_LEVERAGE_TOTAL=3.0

# ===== 日志配置 =====
LOG_LEVEL=INFO
LOG_JSON=true  # 生产环境使用 JSON 日志
LOG_COLORS=false

# ===== 警报配置 =====
# 邮件
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_SENDER=alert@cherryquant.com
EMAIL_USERNAME=alert@cherryquant.com
EMAIL_PASSWORD=your_email_password
EMAIL_RECIPIENTS=admin@cherryquant.com,trader@cherryquant.com

# 微信企业号
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_key
WECHAT_ENABLED=true

# 钉钉
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=your_token
DINGTALK_ENABLED=true
```

### 配置验证

```bash
# 验证配置
uv run python -c "
from config.settings.base import CherryQuantConfig
config = CherryQuantConfig.from_env()
config.print_summary()
config.validate_for_production()
print('✅ 配置验证通过')
"
```

---

## 数据库设置

### MongoDB 生产配置

#### 1. 启用认证

```bash
# 连接到 MongoDB
mongosh

# 创建管理员用户
use admin
db.createUser({
  user: "admin",
  pwd: "your_admin_password",
  roles: [ { role: "root", db: "admin" } ]
})

# 创建应用用户
use cherryquant_prod
db.createUser({
  user: "cherryquant",
  pwd: "your_app_password",
  roles: [ { role: "readWrite", db: "cherryquant_prod" } ]
})
```

#### 2. 配置副本集（高可用）

编辑 `/etc/mongod.conf`：

```yaml
replication:
  replSetName: "cherryquant-rs"

security:
  authorization: enabled
  keyFile: /etc/mongodb/keyfile
```

生成 keyfile：

```bash
openssl rand -base64 756 | sudo tee /etc/mongodb/keyfile
sudo chmod 400 /etc/mongodb/keyfile
sudo chown mongodb:mongodb /etc/mongodb/keyfile
```

初始化副本集：

```javascript
rs.initiate({
  _id: "cherryquant-rs",
  members: [
    { _id: 0, host: "mongo1.example.com:27017" },
    { _id: 1, host: "mongo2.example.com:27017" },
    { _id: 2, host: "mongo3.example.com:27017" }
  ]
})
```

#### 3. 创建索引

```bash
uv run python scripts/create_indexes.py
```

或手动创建：

```javascript
use cherryquant_prod

// 市场数据索引
db.market_data.createIndex({ "symbol": 1, "timestamp": -1 })
db.market_data.createIndex({ "timestamp": 1 }, { expireAfterSeconds: 31536000 })  // 1年TTL

// 交易决策索引
db.trading_decisions.createIndex({ "symbol": 1, "timestamp": -1 })
db.trading_decisions.createIndex({ "strategy_id": 1, "timestamp": -1 })

// 持仓索引
db.positions.createIndex({ "symbol": 1, "status": 1 })
```

### Redis 生产配置

编辑 `/etc/redis/redis.conf`：

```conf
# 绑定到本地（如果不需要远程访问）
bind 127.0.0.1

# 启用密码
requirepass your_redis_password

# 持久化
save 900 1
save 300 10
save 60 10000

appendonly yes
appendfilename "appendonly.aof"

# 内存限制
maxmemory 2gb
maxmemory-policy allkeys-lru

# 慢查询日志
slowlog-log-slower-than 10000
slowlog-max-len 128
```

重启 Redis：

```bash
sudo systemctl restart redis
```

---

## 安全配置

### 1. 防火墙设置

```bash
# 只允许必要的端口
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP（如果需要）
sudo ufw allow 443/tcp  # HTTPS（如果需要）

# MongoDB 和 Redis 不对外开放（仅本地）
# 如果需要远程访问，使用 VPN 或 SSH 隧道

sudo ufw enable
sudo ufw status
```

### 2. SSH 加固

编辑 `/etc/ssh/sshd_config`：

```conf
# 禁用 root 登录
PermitRootLogin no

# 禁用密码登录（只使用 SSH 密钥）
PasswordAuthentication no
PubkeyAuthentication yes

# 更改默认端口（可选）
Port 2222
```

重启 SSH：

```bash
sudo systemctl restart sshd
```

### 3. 日志文件权限

```bash
# 确保日志目录权限正确
chmod 750 /opt/CherryQuant/logs
chmod 640 /opt/CherryQuant/logs/*.log
```

### 4. 环境变量保护

```bash
# .env 文件权限
chmod 600 /opt/CherryQuant/.env
```

---

## 监控和日志

### 1. 应用日志

JSON 格式的日志已配置，位于 `logs/` 目录：

```bash
# 实时查看日志
tail -f logs/cherryquant.log | jq '.'

# 查找错误
grep '"level":"error"' logs/cherryquant.log | jq '.'

# 查找特定symbol的决策
grep '"symbol":"rb2501"' logs/cherryquant.log | jq '.'
```

### 2. 系统监控

安装监控工具（可选）：

```bash
# 安装 Prometheus Node Exporter
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.1/node_exporter-1.6.1.linux-amd64.tar.gz
tar xvfz node_exporter-1.6.1.linux-amd64.tar.gz
sudo cp node_exporter-1.6.1.linux-amd64/node_exporter /usr/local/bin/
sudo useradd -rs /bin/false node_exporter

# 创建 systemd 服务
sudo vim /etc/systemd/system/node_exporter.service
```

### 3. 数据库监控

#### MongoDB 监控

```bash
# 使用 mongostat
mongostat --uri "mongodb://cherryquant:password@localhost:27017/cherryquant_prod"

# 使用 mongotop
mongotop --uri "mongodb://cherryquant:password@localhost:27017/cherryquant_prod"
```

#### Redis 监控

```bash
# Redis 统计信息
redis-cli -a your_password info stats

# 实时监控
redis-cli -a your_password monitor
```

### 4. 告警配置

确保 `.env` 中配置了告警渠道：

```bash
# 测试告警
uv run python -c "
from cherryquant.utils.alerting import send_alert
send_alert(
    title='系统启动',
    message='CherryQuant 生产环境已启动',
    level='info'
)
"
```

---

## 备份和恢复

### MongoDB 备份

#### 自动备份脚本

创建 `/opt/CherryQuant/scripts/backup_mongodb.sh`：

```bash
#!/bin/bash

BACKUP_DIR="/backup/mongodb"
DATE=$(date +%Y%m%d_%H%M%S)
MONGODB_URI="mongodb://cherryquant:password@localhost:27017/cherryquant_prod"

# 创建备份
mongodump --uri="$MONGODB_URI" --out="$BACKUP_DIR/$DATE" --gzip

# 保留最近7天的备份
find $BACKUP_DIR -type d -mtime +7 -exec rm -rf {} \;

echo "Backup completed: $BACKUP_DIR/$DATE"
```

设置定时任务：

```bash
# 编辑 crontab
crontab -e

# 每天凌晨 2 点备份
0 2 * * * /opt/CherryQuant/scripts/backup_mongodb.sh >> /var/log/mongodb_backup.log 2>&1
```

#### 恢复数据

```bash
# 恢复特定日期的备份
mongorestore --uri="mongodb://cherryquant:password@localhost:27017" \
  --gzip \
  /backup/mongodb/20251118_020000/cherryquant_prod
```

### 代码和配置备份

```bash
# 备份配置文件
cp /opt/CherryQuant/.env /backup/env/.env.$(date +%Y%m%d)

# Git 仓库
cd /opt/CherryQuant
git bundle create /backup/git/cherryquant_$(date +%Y%m%d).bundle --all
```

---

## 故障排查

详见 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)（下一步创建）

### 常见问题快速参考

1. **服务无法启动**
   ```bash
   sudo systemctl status cherryquant
   sudo journalctl -u cherryquant -n 100 --no-pager
   ```

2. **MongoDB 连接失败**
   ```bash
   mongosh "mongodb://cherryquant:password@localhost:27017/cherryquant_prod"
   ```

3. **Redis 连接失败**
   ```bash
   redis-cli -a your_password ping
   ```

4. **OpenAI API 错误**
   ```bash
   curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

---

## 滚动更新

### 零停机更新步骤

1. **拉取最新代码**
   ```bash
   cd /opt/CherryQuant
   git fetch origin
   git checkout tags/v1.2.0  # 或 git pull origin main
   ```

2. **更新依赖**
   ```bash
   uv sync --frozen
   ```

3. **运行测试**
   ```bash
   uv run pytest
   ```

4. **数据库迁移**（如果需要）
   ```bash
   uv run python scripts/migrate_database.py
   ```

5. **重启服务**
   ```bash
   sudo systemctl restart cherryquant
   ```

6. **验证**
   ```bash
   # 检查服务状态
   sudo systemctl status cherryquant

   # 查看日志
   sudo journalctl -u cherryquant -f
   ```

### 回滚

```bash
# 停止服务
sudo systemctl stop cherryquant

# 回滚代码
cd /opt/CherryQuant
git checkout tags/v1.1.0  # 回滚到上一个版本

# 更新依赖
uv sync --frozen

# 启动服务
sudo systemctl start cherryquant
```

---

## 性能优化

### 1. 系统层面

```bash
# 增加文件描述符限制
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# 优化 TCP 参数
sudo sysctl -w net.ipv4.tcp_tw_reuse=1
sudo sysctl -w net.core.somaxconn=4096
```

### 2. MongoDB 优化

- 确保工作集在内存中
- 使用 WiredTiger 存储引擎（默认）
- 启用压缩：`storage.wiredTiger.collectionConfig.blockCompressor: snappy`

### 3. 应用层优化

- 使用连接池（已配置）
- 启用 Redis 缓存（已配置）
- 异步 I/O（已使用 asyncio）

---

## 检查清单

部署前检查：

- [ ] 服务器硬件满足要求
- [ ] Python 3.12+ 已安装
- [ ] MongoDB 已安装并配置认证
- [ ] Redis 已安装并配置密码
- [ ] 防火墙已正确配置
- [ ] SSH 已加固
- [ ] `.env` 文件已正确配置
- [ ] 数据库索引已创建
- [ ] 备份策略已设置
- [ ] 监控和告警已配置
- [ ] 测试环境验证通过

部署后验证：

- [ ] 服务成功启动
- [ ] 能够连接 MongoDB
- [ ] 能够连接 Redis
- [ ] 能够调用 OpenAI API
- [ ] 能够接收实时行情（live 模式）
- [ ] 日志正常输出
- [ ] 告警通知正常
- [ ] 监控指标正常

---

## 联系支持

遇到问题？

- 查看 [故障排查指南](./TROUBLESHOOTING.md)
- 提交 Issue: https://github.com/your-org/CherryQuant/issues
- 邮件支持: support@cherryquant.com
