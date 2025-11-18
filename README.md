# 🍒 CherryQuant - AI期货交易系统

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![uv](https://img.shields.io/badge/uv-Package_Manager-purple.svg)](https://docs.astral.sh/uv/)
[![vnpy](https://img.shields.io/badge/vnpy-4.1.0+-red.svg)](https://www.vnpy.com/)
[![QuantBox](https://img.shields.io/badge/QuantBox-Integrated-orange.svg)](docs/QUANTBOX_INTEGRATION.md)

**基于大语言模型的中国期货市场AI驱动交易系统**

[快速开始](#-快速开始) • [系统架构](docs/ARCHITECTURE.md) • [配置指南](#-配置指南) • [数据流程](docs/DATA_PIPELINE.md) • [QuantBox集成](docs/QUANTBOX_INTEGRATION.md)

</div>

## 📖 项目简介

CherryQuant 是一个基于 **AI 驱动**的中国期货市场自动化交易系统。项目名称来源于 "Cherry"（樱桃）和 "Quant"（量化）的结合，寓意着精准、高效的量化交易。

### ✨ 核心特性

- 🤖 **AI品种选择** - 从品种池中自动选择最优交易机会
- 📊 **动态主力合约** - 使用Tushare自动解析当前主力合约
- 🔄 **双模式架构** - live(CTP实时) / dev(准实时) 灵活切换
- 🇨🇳 **境内期货专注** - 支持上期所、大商所、郑商所、中金所
- ⚡ **vnpy集成** - 基于成熟的vnpy框架进行CTP连接
- 🛡️ **多层风险控制** - 策略级+组合级风险管理
- 📈 **实时数据记录** - CTP Tick → K线聚合 → TimescaleDB
- 🎯 **多策略协同** - 支持多个AI策略并行运行
- 🚀 **QuantBox集成** - 高性能异步数据管理，性能提升10-20倍
- 💾 **智能缓存系统** - 缓存预热，首次操作速度提升95%+

### 🎯 设计理念

采用 **提示词工程** 方法，使用未经微调的GPT-4进行期货交易决策，实现 **零样本系统化交易**。

**关键创新**:
- **品种池配置**: 不再硬编码合约（如rb2501），而是配置品种池（如黑色系），AI从池中选择
- **动态合约解析**: 使用Tushare `fut_mapping` API自动查询当前主力合约
- **数据模式分离**: dev模式使用免费API开发测试，live模式接入CTP实时数据

## 🚀 快速开始

### 环境要求

- **Python**: 3.12+
- **包管理器**: uv
- **AI模型**: OpenAI API Key (GPT-4)
- **数据服务**: Docker + PostgreSQL + Redis + MongoDB (QuantBox)
- **CTP账户**: SimNow模拟账户 或 实盘账户（live模式需要）
- **Tushare Pro**: Token（推荐2000+积分，用于分钟线和主力合约查询）

### 第三方依赖与本地编译（重要）

本项目 **随仓库一起包含** 了部分第三方依赖源码，用于保证在中国期货场景下的版本可控，其中包括：

- `vnpy_ctp-6.7.7.2`：位于 `third_party/vnpy_ctp-6.7.7.2/`，作为 `vnpy-ctp` 包的源码（未修改的上游版本）。

安装依赖时（例如执行 `uv sync --group dev`）会从该目录 **本地编译** `vnpy-ctp`，因此你需要提前安装：

- C/C++ 编译工具链（例如：
  - macOS: `xcode-select --install`
  - Ubuntu/Debian: `sudo apt-get install -y build-essential ninja-build meson pkg-config python3-dev`
  - Windows: 安装 Visual Studio Build Tools / 带 C++ 的 Visual Studio）
- Python 构建工具链：`meson`, `ninja`, `pybind11` 等（会由 `vnpy-ctp` 的 `pyproject.toml` 自动透传并安装）

> 提示：如果本地不满足 CTP SDK 或平台限制，`vnpy-ctp` 可能编译/导入失败，此时系统会通过 `CTP_AVAILABLE` 标志自动降级，不影响 **dev / simulation** 模式运行。

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/your-username/CherryQuant.git
cd CherryQuant
```

#### 2. 安装依赖

```bash
# 使用uv安装所有依赖（含开发工具）
uv sync --group dev

# 安装包（可编辑模式，启用 cherryquant.* 导入）
uv run pip install -e .

# 验证安装与导入
uv run python -c "import cherryquant, sys; print('OK', cherryquant.__version__)"
```

#### 3. 启动数据库服务

```bash
# 使用Docker启动PostgreSQL和Redis
docker-compose -f docker/docker-compose.yml up -d

# 验证服务
docker ps
```

#### 4. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件（根据实际情况填写）
nano .env
```

**关键配置项**:

```env
# ============= AI模型配置 =============
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# ============= 数据模式配置 =============
# 模式选择: dev(开发测试) | live(实盘/模拟盘)
DATA_MODE=dev

# Tushare Pro Token（推荐2000+积分）
TUSHARE_TOKEN=your_tushare_pro_token

# ============= CTP配置（live模式需要） =============
CTP_USERID=your_simnow_userid
CTP_PASSWORD=your_simnow_password
CTP_BROKER_ID=9999
CTP_MD_ADDRESS=tcp://180.168.146.187:10131
CTP_TD_ADDRESS=tcp://180.168.146.187:10130

# ============= 数据库配置 =============
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cherryquant
POSTGRES_USER=cherryquant
POSTGRES_PASSWORD=cherryquant123

REDIS_HOST=localhost
REDIS_PORT=6379
```

#### 5. 初始化历史数据

**首次使用建议先下载历史数据**:

```bash
# 快速下载日线数据（推荐，5-10分钟）
uv run run_cherryquant_complete.py --download-data

# 下载日线和小时线（需要高级Tushare权限，较慢）
uv run run_cherryquant_complete.py --download-data --timeframes 1d 1h

# 下载指定品种
uv run run_cherryquant_complete.py --download-data --symbols rb cu i SR
```

**数据格式说明**:
- 所有数据自动转换为 **VNPy 标准格式**
- 郑商所合约使用 **3位数字**（如 `SR501.CZCE`）
- 其他交易所使用 **4位数字**（如 `rb2501.SHFE`）

详见：[数据下载指南](docs/DATA_DOWNLOAD_GUIDE.md) | [合约标准化说明](docs/SYMBOL_STANDARDIZATION.md)

#### 6. 运行系统

**开发模式（推荐首次运行）**:
```bash
# 基础模拟交易
uv run python run_cherryquant.py

# AI品种选择演示
uv run python run_cherryquant_ai_selection.py

# 完整系统（多策略+风险+告警+Web）
uv run python run_cherryquant_complete.py

# 跳过数据检查快速启动
uv run run_cherryquant_complete.py --skip-data-check
```

**生产模式（需要CTP账户）**:
```bash
# 1. 修改.env设置DATA_MODE=live
# 2. 配置CTP账户信息
# 3. 运行完整系统
uv run python run_cherryquant_complete.py
```

## 📚 系统架构

### 架构图

详见 [ARCHITECTURE.md](docs/ARCHITECTURE.md)

### 核心组件

```
┌─────────────────────────────────────────────┐
│         用户接口层                           │
│  run_cherryquant.py                         │
│  run_cherryquant_complete.py                │
│  run_cherryquant_ai_selection.py            │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│         AI决策层                             │
│  AISelectionEngine (品种选择)               │
│  FuturesEngine (交易决策)                    │
│  AgentManager (多策略协调)                   │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│         数据适配层                           │
│  ContractResolver (主力合约解析)            │
│  MarketDataManager (多数据源管理)           │
│  VNPyGateway (CTP连接封装)                  │
│  RealtimeRecorder (Tick聚合)                │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│         数据存储层                           │
│  PostgreSQL (TimescaleDB) - 时序数据        │
│  Redis - 实时缓存                            │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│         外部服务层                           │
│  OpenAI GPT-4 - AI决策                      │
│  Tushare Pro - 历史数据+主力合约            │
│  vnpy CTP - 实时行情+交易                   │
│  AKShare - 准实时数据(dev模式)              │
└─────────────────────────────────────────────┘
```

### 数据流程

#### Live模式（实时交易）
```
CTP交易所 → VNPyGateway → RealtimeRecorder → TimescaleDB
                ↓
          AI Decision Engine → Order → CTP交易所
```

#### Dev模式（开发测试）
```
AKShare/Tushare → MarketDataManager → AI Decision Engine → 模拟订单
```

## 🔧 配置指南

### 1. 品种池配置

编辑 `config/strategies.json`:

```json
{
  "commodity_pools": {
    "black": {
      "name": "黑色系",
      "commodities": ["rb", "hc", "i", "j", "jm"]
    },
    "metal": {
      "name": "有色金属",
      "commodities": ["cu", "al", "zn", "pb", "ni", "sn"]
    }
  },
  "strategies": [
    {
      "strategy_id": "trend_following_01",
      "strategy_name": "趋势跟踪策略",
      "commodity_pool": "black",
      "max_symbols": 3,
      "selection_mode": "ai_driven",
      "initial_capital": 100000,
      "risk_per_trade": 0.02
    }
  ]
}
```

**说明**:
- `commodity_pool`: 指定品种池（如"black"）
- `max_symbols`: AI从池中最多选择的品种数
- `selection_mode`: "ai_driven"表示AI自主选择

### 2. 数据模式切换

**Dev模式（开发测试）**:
```env
DATA_MODE=dev
# 使用AKShare免费API，无需CTP账户
```

**Live模式（实盘/模拟盘）**:
```env
DATA_MODE=live
CTP_USERID=your_userid
CTP_PASSWORD=your_password
# 需要配置完整的CTP信息
```

### 3. 主力合约解析

系统自动使用Tushare `fut_mapping` API解析主力合约：

```python
# 自动将品种代码转换为当前主力合约
"rb" → "rb2501"  # 2025年1月合约（假设为主力）
"cu" → "cu2412"  # 2024年12月合约
"IF" → "IF2412"  # 股指期货当月合约
```

**降级方案**: Tushare不可用时，使用规则推算（当月+2或+3）

## 📊 运行模式

### 1. 基础模拟交易
```bash
uv run python run_cherryquant.py
```
- 单策略运行
- 实时价格（支持多数据源降级）
- 适合快速测试和开发

### 2. AI品种选择演示
```bash
uv run python run_cherryquant_ai_selection.py
```
- 展示AI如何从品种池中选择
- 全市场扫描和分析
- 输出详细的选择理由

### 3. 完整系统
```bash
uv run python run_cherryquant_complete.py
```
- 多策略并行运行
- 实时风险监控
- 告警系统
- Web API接口（端口8000）
- CTP实时数据记录（live模式）

### 4. 多策略代理
```bash
uv run python run_cherryquant_multi_agent.py
```
- 多个AI策略代理协同
- 组合级风险管理
- 策略间协调和资金分配

## 🧪 测试和验证（CI）
仓库已内置 GitHub Actions 工作流（.github/workflows/ci.yml），使用 uv 同步依赖并执行 Ruff（lint）、Black（格式检查）、Mypy（类型检查）与 Pytest（单元测试）。

### 配置验证
```bash
# 查看配置摘要
uv run python -c "from config.settings.base import CONFIG; CONFIG.print_summary()"

# 生产环境检查
uv run python -c "from config.settings.base import CONFIG; CONFIG.validate_for_production()"
```

### 主力合约解析测试
```bash
uv run python -c "
import asyncio
from adapters.data_adapter.contract_resolver import get_contract_resolver
import os

async def test():
    resolver = get_contract_resolver(os.getenv('TUSHARE_TOKEN'))
    contracts = await resolver.batch_resolve_contracts(['rb', 'cu', 'IF'])
    print(contracts)

asyncio.run(test())
"
```

## 📖 文档

### 用户文档（适合非技术人员）
- [快速入门指南](docs/QUICK_START.md) - 5分钟了解系统（推荐首读）
- [完整用户指南](docs/USER_GUIDE.md) - 详细使用说明和风险提示

### 数据和配置
- [数据下载指南](docs/DATA_DOWNLOAD_GUIDE.md) - 历史数据下载
- [合约标准化说明](docs/SYMBOL_STANDARDIZATION.md) - VNPy格式说明

### 技术文档
- [系统架构](docs/ARCHITECTURE.md) - 详细的架构设计和组件说明
- [数据流程](docs/DATA_PIPELINE.md) - 数据采集、处理、存储流程
- [API文档](docs/api/) - AI决策API使用说明
- [配置指南](docs/configuration/) - SimNow/CTP配置教程
- [迁移指南](docs/MIGRATION_GUIDE.md) - 从旧版本迁移

## ⚠️ 注意事项

### 数据源积分要求
- **Tushare Pro**:
  - 基础数据: 120积分
  - 分钟线数据: **2000+积分**
  - 主力合约映射(fut_mapping): **2000+积分**
- **获取方式**: 注册Tushare Pro并充值或推荐用户获取积分

### CTP连接
- **SimNow**: 免费模拟账户，7*24小时（夜盘有数据）
- **实盘**: 需要期货公司开户，仅交易时段可用
- **macOS支持**: vnpy_ctp 6.7.7.2已支持macOS（Apple Silicon）

### 风险提示
- 期货交易存在高风险，可能导致资金损失
- 本系统为技术研究项目，不构成投资建议
- 实盘交易前请充分测试和评估风险
- 建议从SimNow模拟盘开始

## 🛠️ 开发

### 项目结构
```
CherryQuant/
├── src/
│   ├── cherryquant/                # 核心包（统一从 cherryquant.* 导入）
│   │   ├── ai/                     # AI决策引擎
│   │   ├── adapters/               # 数据/存储/录制适配层
│   │   ├── services/               # 后台服务（数据采集等）
│   │   ├── web/                    # Web API 与静态资源
│   │   └── cherry_quant_strategy.py
│   └── trading/
│       ├── vnpy_gateway.py         # CTP网关封装
│       └── order_manager.py        # 智能订单管理
├── config/                         # 配置管理
│   ├── strategies.json             # 策略与品种池配置
│   └── settings/                   # Pydantic配置验证
├── docker/                         # 基础设施编排（TimescaleDB/Postgres + Redis）
├── docs/                           # 文档
├── tests/                          # 测试
└── run_*.py                        # 运行脚本
```

### 贡献指南
欢迎提交Issue和Pull Request！

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📝 更新日志

### v0.2.0 (2025-11-05)
- ✨ 实现品种池配置和AI自主选择
- ✨ 添加ContractResolver动态主力合约解析
- ✨ 支持live/dev双模式架构
- 🐛 修复vnpy CTP集成API使用错误
- ♻️ 重构配置系统，增强验证
- 🗑️ 清理冗余文件，移除InfluxDB依赖
- 📝 完善文档和架构图

### v0.1.0 (2024-10-30)
- 🎉 初始版本发布
- 实现基础AI决策引擎
- 集成vnpy框架
- 支持多数据源

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 🙏 致谢

- [vnpy](https://www.vnpy.com/) - 优秀的Python量化交易框架
- [Tushare](https://tushare.pro/) - 强大的金融数据接口
- [OpenAI](https://openai.com/) - GPT-4大语言模型
- [AKShare](https://akshare.akfamily.xyz/) - 免费金融数据接口

## 📧 联系方式

- Issues: [GitHub Issues](https://github.com/your-username/CherryQuant/issues)
- Email: team@cherryquant.ai

---

<div align="center">
Made with ❤️ by CherryQuant Team
</div>
