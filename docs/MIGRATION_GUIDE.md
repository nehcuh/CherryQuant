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
