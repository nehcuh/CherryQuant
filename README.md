# 🍒 CherryQuant - AI期货交易系统

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![uv](https://img.shields.io/badge/uv-Package_Manager-purple.svg)](https://docs.astral.sh/uv/)

**基于大语言模型的中国期货市场AI驱动交易系统**

[快速开始](#-快速开始) • [系统架构](#-系统架构) • [API文档](docs/api/) • [测试案例](docs/testing/) • [配置指南](#-配置指南)

</div>

## 📖 项目简介

CherryQuant 是一个基于 **AI 驱动**的中国期货市场自动化交易系统。项目名称来源于 "Cherry"（樱桃）和 "Quant"（量化）的结合，寓意着精准、高效的量化交易。

### ✨ 核心特性

- 🤖 **AI决策引擎** - 基于 LLM 的智能交易决策
- 🇨🇳 **境内期货专注** - 针对中国期货市场优化
- 📊 **专业框架** - 基于 vn.py 成熟交易基础设施
- ⚡ **快速原型** - MVP版本，1天内可运行
- 🛡️ **风险控制** - 多层级风险管理和仓位控制
- 📈 **实时监控** - 完整的日志和性能跟踪
- 🔄 **多数据源** - 支持AKShare、Simnow等多种数据源

### 🎯 设计理念

基于 **nof1.ai** 的成功经验，CherryQuant 采用纯粹的提示词工程方法，使用未经微调的标准大模型进行期货交易决策，实现真正的 **零样本系统化交易**。

## 🚀 快速开始

### 环境要求

- Python 3.12+
- uv 包管理器
- OpenAI API Key
- Docker + OrbStack（用于数据库服务）
- Simnow账号（可选，用于专业数据源）

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/your-username/CherryQuant.git
cd CherryQuant
```

#### 2. 安装依赖

```bash
# 使用uv安装依赖
uv sync

# 安装数据库相关依赖
uv add asyncpg redis aiofiles pandas numpy
```

#### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
nano .env
```

在 `.env` 文件中设置：

```env
# OpenAI API配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1

# 期货配置
DEFAULT_SYMBOL=rb2501
EXCHANGE=SHFE

# 数据源配置
DATA_SOURCE=tushare    # 可选: tushare, simnow
# Tushare（历史/主连，默认）
TUSHARE_TOKEN=your_tushare_pro_token
# 实时数据使用 vn.py CTP 记录器（见 docs/VN_RECORDER.md）
SIMNOW_USERID=         # Simnow用户ID
SIMNOW_PASSWORD=       # Simnow密码
SIMNOW_BROKER_ID=9999  # Simnow期货公司ID

# 决策配置
DECISION_INTERVAL=300
MAX_POSITION_SIZE=10
LEVERAGE=5

# 数据库配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cherryquant
POSTGRES_USER=cherryquant
POSTGRES_PASSWORD=cherryquant123

REDIS_HOST=localhost
REDIS_PORT=6379
```

#### 4. 启动数据库服务

```bash
# 启动Docker数据库服务
docker-compose -f docker/docker-compose.yml up -d

# 查看服务状态
docker-compose -f docker/docker-compose.yml ps
```

#### 5. 运行系统

```bash
# 启动实时数据记录器（vn.py CTP，tick→合成 5m/10m/30m/60m K线）
# 参考文档: docs/VN_RECORDER.md
# 历史数据建议通过 Tushare 获取并落库，实时由记录器持续写入

# AI品种选择演示
uv run python run_cherryquant_ai_selection.py

# 数据库集成演示
uv run python demo_database_integration.py

# 模拟交易模式（推荐）
uv run python run_cherryquant.py simulation

# 回测模式
uv run python run_cherryquant.py backtest

# 实盘模式（需要真实期货账户）
uv run python run_cherryquant.py live
```

### 🎮 首次运行

```bash
# 1. 启动数据库服务
docker-compose -f docker/docker-compose.yml up -d

# 2. 运行AI品种选择演示
uv run python run_cherryquant_ai_selection.py

# 预期输出示例：
# 🎮 CherryQuant AI品种选择演示开始
# ✅ 数据库连接成功
# 📊 AI市场分析结果: 分析合约总数: 45
# 🏆 TOP 3 交易机会: 1. RB (SHFE) 综合评分: 85/100
# 🎯 AI最终选择: 交易品种: RB.SHFE, 交易方向: buy_to_enter
# ✅ 已执行buy_to_enter订单，添加到持仓

# 3. 运行数据库集成演示
uv run python demo_database_integration.py

# 预期输出示例：
# 🔗 测试数据库连接... ✅ 数据库连接成功
# 📈 生成多时间维度测试数据... 1D: 50条数据, 4H: 50条数据
# 💾 存储数据到数据库... ✅ 存储1D数据: 50条
# 🔍 从数据库检索数据... 📈 检索到日线数据: 50条
# ⚡ 测试缓存性能... 🚀 缓存加速比: 5.2x
```

## 📊 数据源选择

### 角色划分

| 数据源/组件 | 用途 | 优点 | 注意事项 |
| ----------- | ---- | ---- | -------- |
| **Tushare** | 历史日线/主连 | 稳定、专业接口 | 需 TUSHARE_TOKEN；分钟线能力有限 |
| **vn.py CTP 记录器** | 实时 tick→5m/10m/30m/60m | 交易级实时、稳定 | 需 CTP 账号与环境；见 docs/VN_RECORDER.md |

### 推荐配置

```env
# 历史 + 实时（默认推荐）
DATA_SOURCE=tushare
TUSHARE_TOKEN=你的tushare_pro_token
# 实时请使用 vn.py CTP 记录器落库（非环境变量，参考文档）
```

**Simnow配置指南**: [docs/configuration/simnow_setup.md](docs/configuration/simnow_setup.md)

## 🏗️ 系统架构

```
CherryQuant AI期货交易系统
├── 数据层 (Data Layer)
│   ├── PostgreSQL + TimescaleDB - 时序数据库
│   ├── Redis - 高速缓存系统
│   ├── InfluxDB - 高频数据存储（可选）
│   ├── 多时间维度数据管理器 - 9种时间周期支持
│   ├── Tushare 历史数据 - Pro 接口（日线/主连）
│   ├── vn.py CTP 实时记录器 - tick 聚合 5m/10m/30m/60m
│   └── 实时行情更新机制
│
├── 计算层 (Analytics Layer)
│   ├── 技术指标计算引擎 - MACD、KDJ、RSI、布林带等
│   ├── 多时间框架分析 - 月线到分钟线全覆盖
│   ├── AI数据优化器 - 上下文窗口优化
│   ├── 风险指标计算 - ATR、波动率、回撤等
│   └── 市场统计分析 - 板块轮动、情绪指标
│
├── AI决策层 (AI Decision Layer)
│   ├── AI品种选择引擎 - 全市场扫描选股
│   ├── 提示词工程 - 基于nof1.ai设计
│   ├── LLM客户端 - OpenAI GPT集成
│   ├── 决策解析 - JSON格式交易信号
│   ├── 置信度评估 - 交易信号可信度
│   └── 决策记录存储 - 历史决策追踪
│
├── 交易执行层 (Trading Layer)
│   ├── vn.py框架集成 - 专业交易基础设施
│   ├── 仓位管理 - 持仓跟踪和风险控制
│   ├── 订单执行 - 自动下单和平仓
│   ├── 止损止盈 - 自动化风险管理
│   └── 投资组合管理 - 多品种风险控制
│
└── 监控层 (Monitoring Layer)
    ├── 实时日志 - 交易过程记录
    ├── 性能统计 - 盈亏和风险指标
    ├── Grafana可视化 - 实时监控面板
    ├── pgAdmin管理界面 - 数据库管理
    └── 通知系统 - 重要事件提醒
```

### 🗄️ 数据架构亮点

- 决策与交易落库：AI 决策写入 ai_decisions，并在模拟执行时打上 executed 状态与价格；交易在 trades 表建档，平仓后补全 exit 字段与盈亏。

- **多时间维度支持**: 月线、周线、日线、4小时、1小时、30分钟、15分钟、5分钟、1分钟
- **智能数据保留**: 高频数据短期保留，低频数据长期保留，优化存储成本
- **缓存加速**: Redis多层缓存，显著提升查询性能
- **AI友好格式**: 预处理的市场分析数据，适配LLM上下文窗口
- **实时更新**: 增量数据同步，确保AI决策基于最新市场信息

详细的架构设计请参考：[架构文档](docs/design/architecture.md)

## 📊 核心功能

### 1. AI决策引擎

基于 **nof1.ai** 的提示词设计，适配中国期货市场：

```python
# AI决策示例
{
  "signal": "buy_to_enter",
  "symbol": "rb2501",
  "quantity": 3,
  "leverage": 5,
  "profit_target": 3550.0,
  "stop_loss": 3420.0,
  "confidence": 0.78,
  "invalidation_condition": "价格跌破3400",
  "justification": "螺纹钢技术指标显示上涨趋势，RSI从超卖区域反弹"
}
```

### 2. 支持的期货品种

- **螺纹钢 (rb)** - 上海期货交易所 🏗️
- **铁矿石 (i)** - 大连商品交易所 ⛏️
- **焦炭 (j)** - 大连商品交易所 🔥
- **焦煤 (jm)** - 大连商品交易所 🏭
- **沪铜 (cu)** - 上海期货交易所 ⚡
- **沪铝 (al)** - 上海期货交易所 🪙
- **沪金 (au)** - 上海期货交易所 🏆
- **沪银 (ag)** - 上海期货交易所 🥈

### 3. 多时间维度数据管理

- **9种时间周期**: 月线、周线、日线、4小时、1小时、30分钟、15分钟、5分钟、1分钟
- **智能数据保留**: 高频数据保留3-30天，低频数据保留1年-永久
- **Redis缓存加速**: 5.2x查询性能提升，1.16M内存占用
- **时序数据库**: PostgreSQL + TimescaleDB，支持海量数据高效查询
- **实时数据同步**: 增量更新机制，确保AI决策基于最新行情
- **数据完整性**: 多层验证和异常数据处理

### 4. 技术指标计算引擎

- **移动平均线**: MA5/10/20/60, EMA12/26
- **MACD指标**: DIF线、DEA线、MACD柱状图
- **KDJ指标**: K值、D值、J值，超买超卖判断
- **RSI相对强弱**: 14日RSI，背离分析
- **布林带**: 上轨、中轨、下轨，价格通道判断
- **ATR真实波幅**: 动态止损和仓位管理
- **其他指标**: CCI、威廉指标等

### 5. AI数据优化器

- **上下文窗口优化**: 压缩市场数据，适配LLM输入限制
- **多时间框架融合**: 综合不同周期信号，提升决策准确性
- **趋势分析**: 价格趋势、动量分析、支撑阻力位识别
- **风险评估**: 波动率分析、最大回撤、VaR计算
- **市场情绪**: 板块轮动、市场热度指标

### 6. 风险管理

- **仓位控制**: 单品种最大40%资金配置
- **止损机制**: 每笔交易强制1-3%风险控制
- **置信度过滤**: 低置信度信号自动过滤
- **时间间隔**: 5分钟决策间隔，避免过度交易
- **动态风险评估**: ATR动态止损、波动率调整
- **相关性控制**: 避免同板块品种过度集中
- **回撤保护**: 最大回撤15%硬止损

## 🔧 配置指南

### 数据源配置

```python
# 数据源管理（默认 Tushare）
market_data_manager = create_default_data_manager()  # Tushare
# 或显式使用 Tushare
market_data_manager = create_tushare_data_manager()
# 实时行情请使用 vn.py CTP 记录器（见 docs/VN_RECORDER.md）
```

### 数据库配置

```python
# 启动数据库服务
docker-compose -f docker/docker-compose.yml up -d

# 初始化数据库管理器
from adapters.data_storage.database_manager import get_database_manager
from config.database_config import DATABASE_CONFIG

db_manager = await get_database_manager(DATABASE_CONFIG)
```

### 多时间维度数据配置

```python
# 多时间维度数据管理
from adapters.data_storage.timeframe_data_manager import TimeFrame, TimeFrameDataManager

timeframe_manager = TimeFrameDataManager()

# 获取多时间周期数据
data = await timeframe_manager.get_multi_timeframe_data(
    symbol="rb",
    exchange="SHFE",
    timeframes=[TimeFrame.DAILY, TimeFrame.FOUR_HOURLY, TimeFrame.ONE_HOUR]
)

# 获取AI优化数据
ai_data = await timeframe_manager.get_ai_optimized_data("rb", "SHFE")
```

### 数据库服务访问

| 服务 | 地址 | 用户名 | 密码 | 说明 |
|------|------|--------|------|------|
| PostgreSQL | localhost:5432 | cherryquant | cherryquant123 | 主数据库 |
| Redis | localhost:6379 | - | - | 缓存系统 |
| Grafana | localhost:3000 | admin | cherryquant123 | 数据可视化 |
| pgAdmin | localhost:5050 | admin@cherryquant.com | cherryquant123 | 数据库管理 |
| InfluxDB | localhost:8086 | admin | admin123456 | 高频数据（可选） |

### 交易配置

```python
# config/settings/settings.py
TRADING_CONFIG = {
    "default_symbol": "rb2501",      # 默认期货合约
    "decision_interval": 300,         # AI决策间隔（秒）
    "max_position_size": 10,          # 最大持仓手数
    "default_leverage": 5,            # 默认杠杆倍数
    "risk_per_trade": 0.02,           # 每笔交易风险比例
}
```

## 🧪 测试

### 数据库管理命令

```bash
# 查看数据库状态
docker-compose -f docker/docker-compose.yml ps

# 查看日志
docker-compose -f docker/docker-compose.yml logs -f postgresql

# 连接PostgreSQL
docker-compose -f docker/docker-compose.yml exec postgresql psql -U cherryquant -d cherryquant

# 查看Redis缓存
docker-compose -f docker/docker-compose.yml exec redis redis-cli

# 备份数据库
docker-compose -f docker/docker-compose.yml exec postgresql pg_dump -U cherryquant cherryquant > backup.sql

# 清理缓存
uv run python -c "
import asyncio
from adapters.data_storage.database_manager import get_database_manager
from config.database_config import DATABASE_CONFIG
async def clear_cache():
    db = await get_database_manager(DATABASE_CONFIG)
    await db.clear_cache()
    print('缓存清理完成')
asyncio.run(clear_cache())
"
```

### 运行测试

```bash
# 安装测试依赖
uv add --dev pytest pytest-asyncio pytest-cov

# 运行所有测试
uv run pytest tests/ -v

# 运行特定测试
uv run pytest tests/test_ai_engine.py -v

# 生成覆盖率报告
uv run pytest tests/ --cov=cherryquant --cov-report=html
```

## 🛡️ 风险提示

⚠️ **重要声明**：

1. **仅供学习研究** - 本系统仅用于量化交易学习和研究
2. **模拟交易优先** - 强烈建议先在模拟环境充分测试
3. **风险自担** - 实盘交易存在亏损风险，请谨慎使用
4. **合规使用** - 请遵守相关法规和期货公司规定
5. **数据源合规** - 使用Simnow时请遵守其使用条款

## 🔮 未来规划

### 短期目标（1-2周）

- [x] ✅ MVP版本实现
- [x] ✅ 模拟交易测试
- [x] ✅ 多数据源支持
- [x] ✅ AI品种选择引擎
- [x] ✅ 多时间维度数据架构
- [x] ✅ Docker数据库集成
- [x] ✅ 完整技术指标计算
- [x] ✅ Redis缓存系统
- [x] ✅ AI上下文窗口优化
- [ ] 🔄 Web监控界面
- [ ] 🔄 完善风控机制

### 中期目标（1-2月）

- [ ] 完整CTP网关集成
- [ ] 实盘部署优化
- [ ] 性能优化
- [ ] 回测系统完善
- [ ] 移动端监控

### 长期目标（3-6月）

- [ ] 多交易所支持
- [ ] 组合策略管理
- [ ] 机器学习优化
- [ ] 机构级风控

## 📚 相关文档

- [系统架构文档](docs/design/architecture.md)
- [API文档](docs/api/ai_decision_api.md)
- [测试案例](docs/testing/test_cases.md)
- [Simnow配置指南](docs/configuration/simnow_setup.md)
- [数据库架构说明](docker/README.md)
- [数据管理API](docs/api/database_management.md)
- [Docker部署指南](docs/deployment/docker_setup.md)

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发流程

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系方式

- 项目主页: [GitHub Repository](https://github.com/your-username/CherryQuant)
- 问题反馈: [Issues](https://github.com/your-username/CherryQuant/issues)
- 文档: [Wiki](https://github.com/your-username/CherryQuant/wiki)

## 🙏 致谢

- [vn.py](https://github.com/vnpy/vnpy) - 专业的量化交易平台
- [AKShare](https://github.com/akfamily/akshare) - 优秀的金融数据接口
- [Simnow](https://www.simnow.com.cn/) - 期货模拟交易数据源
- [OpenAI](https://openai.com/) - 强大的AI模型支持
- [nof1.ai](https://nof1.ai/) - 提示词工程设计灵感
- [TimescaleDB](https://www.timescale.com/) - 时序数据库解决方案
- [Redis](https://redis.io/) - 内存缓存数据库
- [Docker](https://www.docker.com/) - 容器化部署平台
- [Grafana](https://grafana.com/) - 数据可视化平台

---

<div align="center">

**🍒 CherryQuant - AI驱动的期货交易系统**

如果这个项目对您有帮助，请给我们一个 ⭐️ Star！

Made with ❤️ by CherryQuant Team

</div>
