#!/usr/bin/env python3
"""
实时数据流示例

难度：⭐⭐ 初级

学习要点：
1. VNPy 实时数据接口
2. 数据流处理
3. 回调函数设计
4. 数据缓存策略

运行方式：
    uv run python examples/02_data/realtime_data_stream.py

前置要求：
    - 配置 .env 文件中的 CTP 参数（使用 SimNow 模拟环境）
    - 或者使用模拟数据模式（不需要真实连接）
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from collections import deque

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class SimulatedDataStream:
    """模拟数据流（用于演示，无需真实CTP连接）"""

    def __init__(self, symbol: str, base_price: float = 3500.0):
        self.symbol = symbol
        self.base_price = base_price
        self.running = False
        self.callbacks = []

    def subscribe(self, callback):
        """订阅数据回调"""
        self.callbacks.append(callback)

    async def start(self):
        """启动数据流"""
        self.running = True
        import random

        print(f"📡 开始接收 {self.symbol} 的实时数据...")

        tick_count = 0
        while self.running and tick_count < 20:
            # 模拟生成tick数据
            tick_count += 1
            price_change = random.uniform(-10, 10)
            tick_data = {
                "symbol": self.symbol,
                "datetime": datetime.now(),
                "last_price": self.base_price + price_change,
                "volume": random.randint(100, 1000),
                "bid_price": self.base_price + price_change - 1,
                "ask_price": self.base_price + price_change + 1,
            }

            # 触发回调
            for callback in self.callbacks:
                callback(tick_data)

            await asyncio.sleep(0.5)  # 每0.5秒一个tick

    def stop(self):
        """停止数据流"""
        self.running = False


async def example_1_basic_stream():
    """示例1：基础实时数据流"""
    print("\n" + "=" * 60)
    print("示例 1: 基础实时数据流")
    print("=" * 60 + "\n")

    # 1. 创建模拟数据流
    stream = SimulatedDataStream(symbol="rb2501", base_price=3500.0)

    # 2. 定义回调函数
    tick_count = 0

    def on_tick(tick_data):
        nonlocal tick_count
        tick_count += 1
        print(
            f"  [{tick_count}] {tick_data['datetime'].strftime('%H:%M:%S')} "
            f"价格: {tick_data['last_price']:.2f} "
            f"成交量: {tick_data['volume']}"
        )

    # 3. 订阅数据
    stream.subscribe(on_tick)

    # 4. 启动数据流（运行10秒）
    print("📊 开始接收实时数据（10秒）...\n")
    task = asyncio.create_task(stream.start())

    await asyncio.sleep(10)
    stream.stop()
    await task

    print(f"\n✅ 示例1完成，共接收 {tick_count} 个tick")


async def example_2_data_aggregation():
    """示例2：数据聚合（Tick → K线）"""
    print("\n" + "=" * 60)
    print("示例 2: 数据聚合 (Tick → 5秒K线)")
    print("=" * 60 + "\n")

    # 1. K线聚合器
    class KLineAggregator:
        def __init__(self, period_seconds: int = 5):
            self.period_seconds = period_seconds
            self.current_bar = None
            self.start_time = None
            self.completed_bars = []

        def on_tick(self, tick_data):
            now = tick_data["datetime"]
            price = tick_data["last_price"]
            volume = tick_data["volume"]

            # 开始新的K线
            if self.current_bar is None:
                self.start_time = now
                self.current_bar = {
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": volume,
                    "start_time": now,
                }
                return

            # 更新当前K线
            self.current_bar["high"] = max(self.current_bar["high"], price)
            self.current_bar["low"] = min(self.current_bar["low"], price)
            self.current_bar["close"] = price
            self.current_bar["volume"] += volume

            # 检查是否完成一根K线
            elapsed = (now - self.start_time).total_seconds()
            if elapsed >= self.period_seconds:
                self.completed_bars.append(self.current_bar.copy())
                print(
                    f"  📊 K线完成: "
                    f"开:{self.current_bar['open']:.2f} "
                    f"高:{self.current_bar['high']:.2f} "
                    f"低:{self.current_bar['low']:.2f} "
                    f"收:{self.current_bar['close']:.2f} "
                    f"量:{self.current_bar['volume']}"
                )
                self.current_bar = None
                self.start_time = None

    # 2. 创建数据流和聚合器
    stream = SimulatedDataStream(symbol="rb2501", base_price=3500.0)
    aggregator = KLineAggregator(period_seconds=5)

    # 3. 订阅数据
    stream.subscribe(aggregator.on_tick)

    # 4. 启动数据流
    print("📊 开始接收数据并聚合成5秒K线...\n")
    task = asyncio.create_task(stream.start())

    await asyncio.sleep(12)  # 运行12秒，应该完成2根K线
    stream.stop()
    await task

    print(f"\n✅ 示例2完成，生成 {len(aggregator.completed_bars)} 根K线")


async def example_3_data_buffer():
    """示例3：数据缓冲和滑动窗口"""
    print("\n" + "=" * 60)
    print("示例 3: 数据缓冲和滑动窗口")
    print("=" * 60 + "\n")

    # 1. 滑动窗口缓冲器
    class SlidingWindowBuffer:
        def __init__(self, window_size: int = 10):
            self.window = deque(maxlen=window_size)

        def on_tick(self, tick_data):
            price = tick_data["last_price"]
            self.window.append(price)

            if len(self.window) == self.window.maxlen:
                # 计算统计指标
                prices = list(self.window)
                avg_price = sum(prices) / len(prices)
                max_price = max(prices)
                min_price = min(prices)
                volatility = max_price - min_price

                print(
                    f"  [{len(self.window)}个tick] "
                    f"均价:{avg_price:.2f} "
                    f"最高:{max_price:.2f} "
                    f"最低:{min_price:.2f} "
                    f"波幅:{volatility:.2f}"
                )

    # 2. 创建数据流和缓冲器
    stream = SimulatedDataStream(symbol="rb2501", base_price=3500.0)
    buffer = SlidingWindowBuffer(window_size=10)

    # 3. 订阅数据
    stream.subscribe(buffer.on_tick)

    # 4. 启动数据流
    print("📊 开始接收数据并计算滑动窗口统计...\n")
    task = asyncio.create_task(stream.start())

    await asyncio.sleep(10)
    stream.stop()
    await task

    print("\n✅ 示例3完成")


async def example_4_multi_symbol_stream():
    """示例4：多品种数据流"""
    print("\n" + "=" * 60)
    print("示例 4: 多品种实时数据流")
    print("=" * 60 + "\n")

    # 1. 多品种管理器
    class MultiSymbolManager:
        def __init__(self):
            self.latest_prices = {}

        def create_callback(self, symbol: str):
            """为每个品种创建独立的回调"""

            def on_tick(tick_data):
                self.latest_prices[symbol] = tick_data["last_price"]

                # 每收到一个tick，显示所有品种的最新价格
                prices_str = "  |  ".join(
                    [f"{sym}: {price:.2f}" for sym, price in self.latest_prices.items()]
                )
                print(f"  {tick_data['datetime'].strftime('%H:%M:%S')} | {prices_str}")

            return on_tick

    # 2. 创建多个数据流
    symbols = [
        ("rb2501", 3500.0),
        ("hc2501", 3200.0),
        ("i2501", 800.0),
    ]

    manager = MultiSymbolManager()
    streams = []

    for symbol, base_price in symbols:
        stream = SimulatedDataStream(symbol=symbol, base_price=base_price)
        stream.subscribe(manager.create_callback(symbol))
        streams.append(stream)

    # 3. 启动所有数据流
    print("📊 开始接收多品种实时数据（10秒）...\n")

    tasks = [asyncio.create_task(stream.start()) for stream in streams]

    await asyncio.sleep(10)

    for stream in streams:
        stream.stop()

    await asyncio.gather(*tasks)

    print(f"\n✅ 示例4完成，监控了 {len(symbols)} 个品种")


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("📚 CherryQuant 数据获取示例 - 实时数据流")
    print("=" * 70)

    print("\n💡 提示: 本示例使用模拟数据，无需真实CTP连接")
    print("   若要连接真实SimNow环境，请参考 docs/guides/quick-start.md\n")

    try:
        # 运行所有示例
        await example_1_basic_stream()
        await example_2_data_aggregation()
        await example_3_data_buffer()
        await example_4_multi_symbol_stream()

        # 总结
        print("\n" + "=" * 70)
        print("✅ 所有示例运行完成！")
        print("=" * 70)
        print("\n💡 下一步:")
        print("  1. 运行 examples/02_data/multi_source_demo.py 学习多数据源管理")
        print("  2. 阅读 docs/reference/vnpy-recorder.md 了解实时数据录制")
        print("  3. 完成 Lab 02 实验任务")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
