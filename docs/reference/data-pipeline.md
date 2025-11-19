# 数据管道总览（Tushare + vn.py CTP）

本项目的数据管道采用“历史 + 实时”的组合：
- 历史数据：使用 Tushare Pro 获取主连/日线等历史数据，标准化落库
- 实时数据：使用 vn.py CTP 网关订阅实时 tick，并通过 RealtimeRecorder 聚合为 5m/10m/30m/60m K 线写入 TimescaleDB

## 架构

1) Tushare 历史加载
- 通过 adapters/data_adapter/market_data_manager.py 的 TushareDataSource 获取历史数据
- 标准化为 columns: datetime, open, high, low, close, volume
- 使用 adapters/data_storage/database_manager.py 写入 market_data 表

2) 实时记录器（vn.py CTP）
- 组件：adapters/vnpy_recorder/realtime_recorder.py
- 从 VNPyGateway 接收 tick 回调
- 聚合周期：5m、10m、30m、1h（可扩展）
- 每个周期完成后写一条 MarketDataPoint 到 DB（market_data 表，ON CONFLICT UPSERT）

3) AI 决策消费
- ai/decision_engine/futures_engine.py 从 DB 读取 5m 为主、10m/30m/1h 为辅
- 计算 MA/RSI/MACD 等指标，构造提示词
- 触发时机：对齐到 5m 收盘

## 表结构（简要）

- market_data(time, symbol, exchange, timeframe, open_price, high_price, low_price, close_price, volume, open_interest, turnover)
- technical_indicators(time, symbol, exchange, timeframe, ma5, ma10, ma20, ma60, ema12, ema26, macd, macd_signal, macd_histogram, kdj_k, kdj_d, kdj_j, rsi, ...)
- ai_decisions(... status, entry_price ...)
- trades(... entry_time/price, exit_time/price ...)

## 时序与对齐

- 实时聚合按周期“桶”对齐：
  - 5m：(:00, :05, :10, ...] 的右闭区间时间戳
  - 10m/30m/1h 同理
- AI 决策循环在每个 5m 收盘边界触发（GTT 下一根 5m 失效）

## 常见问题

- 无 Tushare Token：历史加载将受限，AI 引擎会走模拟路径/或仅基于已有 DB 数据
- CTP 未连接：无法获得实时聚合 K 线，AI 仍可使用历史/演示数据运行
