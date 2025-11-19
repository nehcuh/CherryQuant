# vn.py 实时记录器（RealtimeRecorder）

RealtimeRecorder 通过 vn.py CTP 网关订阅 tick，并将其聚合为 5m/10m/30m/60m K 线，实时写入 TimescaleDB。

位置：adapters/vnpy_recorder/realtime_recorder.py

## 前置条件
- 已部署数据库（PostgreSQL + TimescaleDB）并启动
- 已正确配置 .env（数据库参数、CTP 账号等）
- 可用的 vn.py CTP 网关环境（参考 vn.py 官方文档）

## 用法示例（伪代码）

```python
import asyncio
from adapters.vnpy_recorder.realtime_recorder import RealtimeRecorder
from src.trading.vnpy_gateway import VNPyGateway

async def main():
    # 初始化 vn.py 网关（需按实际参数实现）
    gateway = VNPyGateway()
    # 连接 CTP
    gateway.connect({
        "user_id": "{{SIMNOW_USERID}}",
        "password": "{{SIMNOW_PASSWORD}}",
        "broker_id": "9999",
        # 其他必要参数...
    })

    recorder = RealtimeRecorder(gateway)
    await recorder.start([
        "rb.SHFE",  # 约定 vt_symbol 形如 rb.SHFE
        "i.DCE",
    ])

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await recorder.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

说明：
- 记录器会在每个周期结束时，将聚合好的 Bar 写入 market_data 表（带 UPSERT）
- 若需要扩展周期，可在 _Aggregator 中增加 TimeFrame 处理

## 常见问题
- 看不到数据？确认 CTP 连接成功且收到 tick；确认数据库连接正常
- 周期错位？检查本机时钟与交易所时钟的同步；记录器按本地时间对齐周期
- 成交量异常？示例中对 tick.volume 采用简单累加，如为“总量”需改为差分