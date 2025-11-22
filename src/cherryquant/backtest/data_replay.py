"""
数据回放器

功能：
1. 逐条回放历史数据
2. 模拟实时数据流
3. 支持多品种、多时间周期

教学要点：
1. 迭代器模式
2. 时间驱动的回测
"""

from typing import Iterator
from datetime import datetime


class DataReplay:
    """
    数据回放器

    按时间顺序回放历史数据，模拟实时行情。
    """

    def __init__(self, data: list[dict], sort_by_time: bool = True):
        """
        Args:
            data: 历史数据列表
                  每条数据格式: {
                      "timestamp": datetime,
                      "symbol": str,
                      "open": float,
                      "high": float,
                      "low": float,
                      "close": float,
                      "volume": int,
                      ...
                  }
            sort_by_time: 是否按时间排序
        """
        self.data = data

        # 按时间排序（确保数据是时间顺序）
        if sort_by_time:
            self.data.sort(key=lambda x: x["timestamp"])

        self.current_index = 0
        self.current_time: datetime | None = None

    def has_next(self) -> bool:
        """是否还有数据"""
        return self.current_index < len(self.data)

    def next(self) -> dict:
        """
        获取下一条数据

        Returns:
            数据字典

        Raises:
            StopIteration: 没有更多数据
        """
        if not self.has_next():
            raise StopIteration("No more data")

        bar = self.data[self.current_index]
        self.current_index += 1
        self.current_time = bar["timestamp"]

        return bar

    def peek(self, offset: int = 0) -> dict | None:
        """
        查看未来数据（不移动指针）

        Args:
            offset: 偏移量（0=下一条，1=下下条，...）

        Returns:
            数据字典（如果存在）
        """
        index = self.current_index + offset

        if index < len(self.data):
            return self.data[index]

        return None

    def reset(self):
        """重置到开始"""
        self.current_index = 0
        self.current_time = None

    def skip_to(self, timestamp: datetime):
        """跳转到指定时间"""
        for i in range(self.current_index, len(self.data)):
            if self.data[i]["timestamp"] >= timestamp:
                self.current_index = i
                self.current_time = self.data[i]["timestamp"]
                return

        # 如果没找到，跳到末尾
        self.current_index = len(self.data)

    def get_current_bar(self) -> dict | None:
        """获取当前Bar（不移动指针）"""
        if self.current_index > 0:
            return self.data[self.current_index - 1]
        return None

    def __iter__(self) -> Iterator[dict]:
        """支持迭代器协议"""
        return self

    def __next__(self) -> dict:
        """支持迭代器协议"""
        return self.next()

    def __len__(self) -> int:
        """数据总数"""
        return len(self.data)

    @property
    def progress(self) -> float:
        """回放进度（0-1）"""
        if len(self.data) == 0:
            return 1.0
        return self.current_index / len(self.data)

    @property
    def progress_pct(self) -> str:
        """回放进度百分比"""
        return f"{self.progress * 100:.1f}%"


class MultiSymbolDataReplay:
    """
    多品种数据回放器

    同时回放多个品种的数据，按时间顺序合并。
    """

    def __init__(self, data_by_symbol: dict[str, list[dict]]):
        """
        Args:
            data_by_symbol: 按品种分组的数据
                {
                    "rb2501": [{timestamp, open, high, ...}, ...],
                    "hc2501": [{timestamp, open, high, ...}, ...],
                }
        """
        # 合并所有数据并按时间排序
        all_data = []
        for symbol, data in data_by_symbol.items():
            for bar in data:
                bar_with_symbol = bar.copy()
                bar_with_symbol["symbol"] = symbol
                all_data.append(bar_with_symbol)

        all_data.sort(key=lambda x: x["timestamp"])

        self.replay = DataReplay(all_data, sort_by_time=False)
        self.symbols = list(data_by_symbol.keys())

    def has_next(self) -> bool:
        return self.replay.has_next()

    def next(self) -> dict:
        return self.replay.next()

    def peek(self, offset: int = 0) -> dict | None:
        return self.replay.peek(offset)

    def reset(self):
        self.replay.reset()

    def __iter__(self) -> Iterator[dict]:
        return self.replay

    def __next__(self) -> dict:
        return self.replay.next()

    @property
    def progress(self) -> float:
        return self.replay.progress
