# CherryQuant 故障排查指南

## 目录

1. [通用排查流程](#通用排查流程)
2. [启动失败问题](#启动失败问题)
3. [数据库连接问题](#数据库连接问题)
4. [API 和外部服务问题](#api和外部服务问题)
5. [数据获取问题](#数据获取问题)
6. [交易执行问题](#交易执行问题)
7. [性能问题](#性能问题)
8. [日志和监控问题](#日志和监控问题)
9. [常见错误代码](#常见错误代码)
10. [获取帮助](#获取帮助)

---

## 通用排查流程

### 第一步：检查日志

```bash
# 查看最近的错误日志
tail -n 100 logs/cherryquant.log | grep -i error

# 使用 jq 格式化 JSON 日志
tail -n 100 logs/cherryquant.log | jq 'select(.level=="error")'

# 查看系统日志（如果使用 systemd）
sudo journalctl -u cherryquant -n 100 --no-pager
```

### 第二步：检查服务状态

```bash
# 应用服务
sudo systemctl status cherryquant

# MongoDB
sudo systemctl status mongod

# Redis
sudo systemctl status redis
```

### 第三步：验证配置

```bash
# 检查环境变量
uv run python -c "
from config.settings.base import CherryQuantConfig
config = CherryQuantConfig.from_env()
config.print_summary()
"

# 验证生产配置
uv run python -c "
from config.settings.base import CherryQuantConfig
config = CherryQuantConfig.from_env()
config.validate_for_production()
"
```

### 第四步：测试连接

```bash
# MongoDB 连接测试
uv run python -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    await client.admin.command('ping')
    print('✅ MongoDB 连接成功')

asyncio.run(test())
"

# Redis 连接测试
redis-cli ping
```

---

## 启动失败问题

### 问题：服务无法启动

#### 症状
```
sudo systemctl status cherryquant
● cherryquant.service - CherryQuant AI Trading System
   Loaded: loaded (/etc/systemd/system/cherryquant.service; enabled)
   Active: failed (Result: exit-code)
```

#### 可能原因和解决方法

**1. 端口已被占用**

```bash
# 检查端口占用
sudo lsof -i :8000  # FastAPI 默认端口

# 解决方法：杀死占用进程或更改端口
kill -9 <PID>

# 或在 .env 中更改端口
echo "API_PORT=8001" >> .env
```

**2. Python 环境问题**

```bash
# 检查 Python 版本
python3.12 --version

# 重新创建虚拟环境
rm -rf .venv
uv sync
```

**3. 依赖缺失**

```bash
# 查看详细错误
sudo journalctl -u cherryquant -n 50

# 重新安装依赖
uv sync --frozen
```

**4. 权限问题**

```bash
# 检查文件所有权
ls -la /opt/CherryQuant

# 修复权限
sudo chown -R cherryquant:cherryquant /opt/CherryQuant
chmod 640 /opt/CherryQuant/.env
chmod 750 /opt/CherryQuant/logs
```

**5. 配置错误**

```bash
# 验证配置
uv run python -c "
from config.settings.base import CherryQuantConfig
try:
    config = CherryQuantConfig.from_env()
    print('✅ 配置加载成功')
except Exception as e:
    print(f'❌ 配置错误: {e}')
"
```

### 问题：ImportError 或 ModuleNotFoundError

#### 症状
```
ModuleNotFoundError: No module named 'cherryquant'
```

#### 解决方法

```bash
# 1. 确保在正确的目录
cd /opt/CherryQuant

# 2. 确保虚拟环境激活
source .venv/bin/activate

# 3. 重新安装包（可编辑模式）
pip install -e .

# 4. 检查 PYTHONPATH
echo $PYTHONPATH

# 5. 使用 uv（推荐）
uv sync
```

---

## 数据库连接问题

### MongoDB 连接失败

#### 症状
```
pymongo.errors.ServerSelectionTimeoutError: localhost:27017: [Errno 111] Connection refused
```

#### 排查步骤

**1. 检查 MongoDB 是否运行**

```bash
sudo systemctl status mongod

# 如果未运行，启动它
sudo systemctl start mongod
```

**2. 检查连接字符串**

```bash
# 查看配置
grep MONGODB_URI .env

# 测试连接
mongosh "mongodb://localhost:27017"

# 如果配置了认证
mongosh "mongodb://cherryquant:password@localhost:27017/cherryquant_prod"
```

**3. 检查防火墙**

```bash
# 检查 MongoDB 端口
sudo lsof -i :27017

# 检查防火墙规则
sudo ufw status
```

**4. 检查 MongoDB 日志**

```bash
sudo tail -f /var/log/mongodb/mongod.log
```

**5. 验证认证配置**

```bash
# 连接到 MongoDB
mongosh

# 切换到admin数据库
use admin

# 验证用户
db.auth("cherryquant", "your_password")

# 列出用户
db.getUsers()
```

### Redis 连接失败

#### 症状
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.
```

#### 排查步骤

**1. 检查 Redis 是否运行**

```bash
sudo systemctl status redis

# 如果未运行
sudo systemctl start redis
```

**2. 测试连接**

```bash
# 无密码
redis-cli ping

# 有密码
redis-cli -a your_password ping
```

**3. 检查 Redis 配置**

```bash
# 查看绑定地址
grep "^bind" /etc/redis/redis.conf

# 查看密码设置
grep "^requirepass" /etc/redis/redis.conf
```

**4. 查看 Redis 日志**

```bash
sudo tail -f /var/log/redis/redis-server.log
```

---

## API 和外部服务问题

### OpenAI API 调用失败

#### 症状
```
openai.error.AuthenticationError: Incorrect API key provided
```

#### 排查步骤

**1. 验证 API Key**

```bash
# 检查环境变量
grep OPENAI_API_KEY .env

# 测试 API Key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**2. 检查网络连接**

```bash
# 测试 OpenAI API 可达性
curl -I https://api.openai.com

# 检查代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

**3. 检查配额和账单**

访问 OpenAI 控制台：https://platform.openai.com/usage

**4. 查看详细错误**

```bash
# 启用调试日志
export LOG_LEVEL=DEBUG

# 重启服务并查看日志
sudo systemctl restart cherryquant
sudo journalctl -u cherryquant -f
```

**5. 测试降级方案**

```python
# 测试是否正确降级到 simulation
uv run python -c "
from cherryquant.ai.decision_engine.futures_engine import FuturesDecisionEngine
import asyncio

async def test():
    # 使用无效 API key
    config = type('Config', (), {'ai': type('AI', (), {'api_key': 'invalid'})()})()
    engine = FuturesDecisionEngine(config=config)

    decision = await engine.make_decision('rb2501', {'price': 3500})
    print(f'Decision: {decision}')  # 应该返回 simulation 模式的决策

asyncio.run(test())
"
```

### Tushare API 问题

#### 症状
```
tushare.exceptions.TokenError: Token is required
```

#### 解决方法

```bash
# 1. 检查 token
grep TUSHARE_TOKEN .env

# 2. 验证 token
uv run python -c "
import tushare as ts
ts.set_token('your_token_here')
pro = ts.pro_api()
df = pro.trade_cal(exchange='SSE', start_date='20250101', end_date='20250131')
print(df.head())
"

# 3. 检查配额
# 访问 https://tushare.pro/user/token
```

### QuantBox 集成问题

#### 症状
```
ModuleNotFoundError: No module named 'quantbox'
```

#### 解决方法

```bash
# 1. 检查 QuantBox 路径
ls -la /Users/huchen/Projects/quantbox

# 2. 重新安装
cd /Users/huchen/Projects/quantbox
pip install -e .

# 3. 验证安装
python -c "import quantbox; print(quantbox.__version__)"

# 4. 检查 pyproject.toml 中的路径配置
grep quantbox /opt/CherryQuant/pyproject.toml
```

---

## 数据获取问题

### 历史数据获取失败

#### 症状
```
No data returned for symbol: rb2501
```

#### 排查步骤

**1. 检查symbol格式**

```python
# 测试 symbol 解析
uv run python -c "
from cherryquant.adapters.data_adapter.contract_resolver import ContractResolver
import asyncio

async def test():
    resolver = ContractResolver()
    dominant = await resolver.resolve_dominant_contract('rb')
    print(f'Dominant contract: {dominant}')

asyncio.run(test())
"
```

**2. 检查数据源可用性**

```bash
# Tushare
uv run python -c "
import tushare as ts
ts.set_token(ts.get_token())
pro = ts.pro_api()
df = pro.fut_daily(ts_code='RB2505.SHF', start_date='20250101')
print(df.head())
"

# QuantBox
uv run python -c "
from quantbox import QuantBox
qb = QuantBox()
# 测试数据获取
"
```

**3. 检查数据库中的数据**

```javascript
// 连接 MongoDB
mongosh "mongodb://localhost:27017/cherryquant_prod"

// 查看market_data集合
db.market_data.find({ symbol: "rb2501" }).limit(5)

// 统计数据量
db.market_data.countDocuments({ symbol: "rb2501" })
```

**4. 检查缓存**

```bash
# Redis 缓存
redis-cli
> KEYS cherryquant:*rb2501*
> GET cherryquant:market_data:rb2501
```

### 实时行情获取失败（CTP）

#### 症状
```
CTP connection failed: Invalid credentials
```

#### 排查步骤

**1. 检查 CTP 配置**

```bash
# 验证配置
grep CTP_ .env

# 确保所有必需字段都已填写
# CTP_USERID, CTP_PASSWORD, CTP_BROKER_ID, CTP_MD_ADDRESS, CTP_TD_ADDRESS
```

**2. 测试 CTP 连接**

```python
uv run python -c "
from vnpy_ctp import CtpGateway
# 测试连接...
"
```

**3. 检查网络**

```bash
# 测试 CTP 服务器可达性
telnet 180.168.146.187 10211  # MD address
telnet 180.168.146.187 10201  # TD address
```

**4. 查看 CTP 日志**

```bash
# CTP 日志通常在运行目录下
ls -la ./*.log
tail -f QueryTime*.log
tail -f TradeTime*.log
```

---

## 交易执行问题

### 订单提交失败

#### 症状
```
Order rejected: Insufficient funds
```

#### 排查步骤

**1. 检查账户状态**

```python
uv run python -c "
# 查询账户资金
from cherryquant.adapters.vnpy_recorder.account_manager import AccountManager
# 获取可用资金...
"
```

**2. 检查风险限制**

```bash
# 查看风险配置
grep MAX_ .env

# 验证风险参数
uv run python -c "
from config.settings.base import CherryQuantConfig
config = CherryQuantConfig.from_env()
print(f'最大资金使用率: {config.risk.max_total_capital_usage}')
print(f'最大单个品种仓位: {config.risk.max_position_size}')
"
```

**3. 查看持仓**

```javascript
// MongoDB
db.positions.find({ status: "OPEN" })
```

**4. 检查交易时段**

```python
uv run python -c "
import datetime
from cherryquant.utils.trading_calendar import is_trading_time

now = datetime.datetime.now()
print(f'当前时间: {now}')
print(f'是否交易时段: {is_trading_time(now)}')
"
```

### AI 决策异常

#### 症状
```
AI decision returned HOLD with low confidence
```

#### 排查步骤

**1. 检查输入数据质量**

```python
# 验证输入数据
uv run python -c "
# 检查数据完整性
data = {
    'close': 3500,
    'ma5': None,  # ← 问题：缺失指标
    'ma20': 3480,
    'rsi': 65
}

# 应该有完整的技术指标
"
```

**2. 查看 AI 决策日志**

```bash
# 过滤 AI 决策相关日志
tail -f logs/cherryquant.log | grep -i "ai_decision"

# 使用 jq 分析
cat logs/cherryquant.log | jq 'select(.event | startswith("ai_decision"))'
```

**3. 测试提示词**

```python
# 手动测试 AI 决策
uv run python -c "
from cherryquant.ai.decision_engine.futures_engine import FuturesDecisionEngine
import asyncio

async def test():
    # 测试数据
    data = {
        'symbol': 'rb2501',
        'close': 3500,
        'change_pct': 1.5,
        'ma5': 3480,
        'ma20': 3450,
        'rsi': 65,
        'macd': 0.5
    }

    engine = FuturesDecisionEngine(...)
    decision = await engine.make_decision('rb2501', data)
    print(f'Decision: {decision}')

asyncio.run(test())
"
```

**4. 检查 API 响应**

```bash
# 查看 OpenAI API 响应时间
cat logs/cherryquant.log | jq 'select(.event=="ai_decision_complete") | .duration_seconds'
```

---

## 性能问题

### 系统响应缓慢

#### 排查步骤

**1. 检查系统资源**

```bash
# CPU 使用率
top -b -n 1 | head -20

# 内存使用
free -h

# 磁盘 I/O
iostat -x 1 5

# 网络
iftop
```

**2. 检查数据库性能**

```bash
# MongoDB 慢查询
mongosh
> use cherryquant_prod
> db.setProfilingLevel(2)  # 记录所有查询
> db.system.profile.find().limit(10).sort({ ts: -1 })

# Redis 慢查询
redis-cli slowlog get 10
```

**3. 分析应用性能**

```python
# 使用 Python profiler
uv run python -m cProfile -o profile.stats run_cherryquant.py

# 分析结果
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative')
p.print_stats(20)
"
```

**4. 检查网络延迟**

```bash
# OpenAI API 延迟
time curl -X POST https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4","messages":[{"role":"user","content":"test"}]}'

# CTP 延迟
ping 180.168.146.187
```

### 内存泄漏

#### 症状
```
Memory usage increasing over time
```

#### 排查步骤

**1. 监控内存使用**

```bash
# 持续监控
watch -n 5 'ps aux | grep cherryquant'

# 详细内存分析
sudo pmap -x $(pgrep -f cherryquant)
```

**2. 使用 memory_profiler**

```bash
# 安装
pip install memory_profiler

# 使用装饰器分析
python -m memory_profiler script.py
```

**3. 检查连接池**

```python
# 检查 MongoDB 连接池
uv run python -c "
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionPool
pool = MongoDBConnectionPool.get_instance()
print(f'Active connections: {pool.client.nodes}')
"
```

**4. 重启服务（临时解决）**

```bash
sudo systemctl restart cherryquant
```

---

## 日志和监控问题

### 日志未生成

#### 解决方法

```bash
# 1. 检查日志目录权限
ls -la logs/
chmod 750 logs/

# 2. 检查磁盘空间
df -h

# 3. 检查日志配置
grep LOG_ .env

# 4. 测试日志记录
uv run python -c "
from cherryquant.logging_config import get_logger
logger = get_logger(__name__)
logger.info('test_log_message', test=True)
"

# 5. 查看日志文件
tail -f logs/cherryquant.log
```

### JSON 日志格式错误

#### 症状
```
日志无法被 jq 解析
```

#### 解决方法

```bash
# 检查日志配置
grep LOG_JSON .env

# 应该是
LOG_JSON=true

# 验证 JSON 格式
tail -n 1 logs/cherryquant.log | jq '.'
```

---

## 常见错误代码

### 错误代码对照表

| 错误代码 | 含义 | 解决方法 |
|----------|------|----------|
| `CONFIG_001` | 配置加载失败 | 检查 .env 文件格式 |
| `DB_001` | MongoDB 连接失败 | 检查 MongoDB 服务和配置 |
| `DB_002` | Redis 连接失败 | 检查 Redis 服务和配置 |
| `API_001` | OpenAI API 调用失败 | 检查 API key 和网络 |
| `API_002` | Tushare API 调用失败 | 检查 token 和配额 |
| `CTP_001` | CTP 连接失败 | 检查 CTP 配置和网络 |
| `DATA_001` | 数据获取失败 | 检查数据源和网络 |
| `RISK_001` | 风险限制触发 | 调整风险参数或减少仓位 |
| `ORDER_001` | 订单提交失败 | 检查账户状态和风险限制 |

---

## 获取帮助

### 自助资源

1. **文档**
   - [README.md](../README.md) - 项目概述
   - [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md) - 部署指南
   - [LOGGING_GUIDE.md](./LOGGING_GUIDE.md) - 日志指南
   - [TESTING_COVERAGE.md](./TESTING_COVERAGE.md) - 测试指南

2. **日志分析**
   ```bash
   # 导出最近的错误日志
   grep -i error logs/cherryquant.log > error_report.log
   ```

3. **系统信息收集**
   ```bash
   # 创建诊断报告
   ./scripts/collect_diagnostic_info.sh
   ```

### 提交 Issue

如果无法自行解决，请提交 Issue：

1. **到 GitHub Issues**: https://github.com/your-org/CherryQuant/issues

2. **包含以下信息**：
   - 问题描述
   - 复现步骤
   - 预期行为 vs 实际行为
   - 环境信息：
     - OS 版本
     - Python 版本
     - CherryQuant 版本
     - MongoDB 版本
     - Redis 版本
   - 相关日志（脱敏后）
   - 配置信息（隐藏敏感信息）

3. **使用 Issue 模板**：
   ```markdown
   ## 问题描述
   简要描述问题...

   ## 复现步骤
   1. ...
   2. ...
   3. ...

   ## 预期行为
   应该...

   ## 实际行为
   实际...

   ## 环境信息
   - OS: Ubuntu 22.04
   - Python: 3.12.0
   - CherryQuant: v1.0.0
   - MongoDB: 5.0.8
   - Redis: 6.2.6

   ## 日志
   ```
   [脱敏后的日志]
   ```

   ## 配置
   ```
   [相关配置,隐藏敏感信息]
   ```
   ```

### 紧急支持

- **邮件**: support@cherryquant.com
- **电话**: +86-xxx-xxxx-xxxx (工作日 9:00-18:00)
- **企业微信**: [二维码]

---

## 预防性维护

### 定期检查项目

**每天**：
- [ ] 检查服务状态
- [ ] 查看错误日志
- [ ] 验证数据更新
- [ ] 检查账户状态

**每周**：
- [ ] 查看性能指标
- [ ] 检查磁盘空间
- [ ] 审查交易决策质量
- [ ] 更新依赖（如有安全补丁）

**每月**：
- [ ] 备份测试和恢复演练
- [ ] 性能基准测试
- [ ] 安全审计
- [ ] 代码质量review

### 监控告警

设置以下告警：

1. **服务可用性**：服务停止 > 1 分钟
2. **错误率**：错误日志 > 10/分钟
3. **API 延迟**：95th percentile > 5秒
4. **数据库连接**：连接失败 > 3 次/分钟
5. **磁盘空间**：可用空间 < 10%
6. **内存使用**：使用率 > 90%

---

## 版本历史

- v1.0 (2025-11-18): 初始版本
