# 迁移指南：AKShare → Tushare + vn.py 记录器

本指南帮助从早期 AKShare 驱动的数据路径迁移到以 Tushare（历史）+ vn.py CTP（实时）为核心的数据架构。

## 变化摘要
- 历史数据：AKShare 路径移除，改用 Tushare Pro（主连/日线优先）
- 实时数据：不再轮询外部接口，改用 vn.py CTP 订阅 tick 并本地聚合为 5m/10m/30m/60m K 线
- AI 决策：消费 5m 为主、10m/30m/1h 为辅，默认在 5m 收盘触发；下单为限价，下一根 5m 失效（GTT）

## 迁移步骤
1) 环境变量
```env
DATA_SOURCE=tushare
TUSHARE_TOKEN=你的tushare_pro_token
# 实时请参考 docs/VN_RECORDER.md 配置 CTP
```

2) 历史数据加载
- 使用 adapters/data_adapter/market_data_manager.py 的 TushareDataSource
- 将历史日线写入 market_data 表；分钟线由记录器产出

3) 移除 AKShare 依赖
- 旧的 AKShare 专用脚本可删除或标记弃用
- 代码中的 AKShare 回退路径应清理（若存在）

4) 启动实时记录器
- 参考 docs/VN_RECORDER.md，通过 vn.py CTP 订阅 vt_symbol（如 rb.SHFE、i.DCE）
- 确认 market_data 表实时写入 5m/10m/30m/1h 数据

5) 验证 AI 决策
- 运行模拟：`uv run python run_cherryquant.py simulation`
- 检查 AI 决策落库 ai_decisions 与订单的到期/成交逻辑

## 回退方案
- 若缺少 Tushare Token：AI 引擎将使用模拟序列/已有 DB 数据；功能受限
- 若 CTP 暂不可用：可仍以历史数据配合模拟逻辑运行，实时性受限

---

## 附录：导入路径迁移（包结构升级）

为了统一导入路径与便于部署，项目已将原先根目录下的 ai/、adapters/、services/、web/ 迁移至包内路径 `src/cherryquant/`。请将旧导入替换为新的包导入。

### 变更总览
- 旧路径 → 新路径（示例）
  - `from ai.decision_engine.futures_engine import FuturesDecisionEngine`
    → `from cherryquant.ai.decision_engine.futures_engine import FuturesDecisionEngine`
  - `from adapters.data_adapter.market_data_manager import create_default_data_manager`
    → `from cherryquant.adapters.data_adapter.market_data_manager import create_default_data_manager`
  - `from services.data_ingestor import run_loop`
    → `from cherryquant.services.data_ingestor import run_loop`
  - `from web.api.main import create_app`
    → `from cherryquant.web.api.main import create_app`

### 常见替换规则
- `from ai.` → `from cherryquant.ai.`
- `from adapters.` → `from cherryquant.adapters.`
- `from services.` → `from cherryquant.services.`
- `from web.` → `from cherryquant.web.`

### 手动替换示例
```python
# 之前
from ai.llm_client.openai_client import AsyncOpenAIClient
from adapters.data_storage.database_manager import get_database_manager

# 之后
from cherryquant.ai.llm_client.openai_client import AsyncOpenAIClient
from cherryquant.adapters.data_storage.database_manager import get_database_manager
```

### 快速迁移建议
- 在本仓库提供的脚本（scripts/refactor_imports.py）中，支持将外部工程的旧导入批量替换为新路径（默认 dry-run，添加 --apply 才会写回）。
- 推荐在单独分支上执行，配合 `git diff` 审核。

### 安装与运行建议
- 使用 uv 管理依赖：
  ```bash
  uv sync --group dev
  uv run pip install -e .
  ```
- 安装为可编辑模式后，即可在你的项目中直接 `import cherryquant...`，无需再修改 `sys.path`。
- CI 建议执行步骤（示例）：
  - uv sync → uv run pip install -e . → uv run ruff/mypy/pytest

