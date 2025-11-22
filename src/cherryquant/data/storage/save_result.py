"""
SaveResult - 数据保存结果追踪器

整合自quantbox.services.data_saver_service.SaveResult
提供详细的数据保存操作统计和错误追踪。

教学要点：
1. 操作结果的追踪和记录
2. 错误管理策略
3. 性能度量（操作持续时间）
4. 可序列化的结果对象
"""
from __future__ import annotations

import datetime
from typing import Any
from dataclasses import dataclass, field


@dataclass
class SaveResult:
    """
    数据保存操作结果追踪器

    教学要点：
    1. 使用dataclass简化数据类定义
    2. 记录操作的完整生命周期（开始时间、结束时间、持续时间）
    3. 统计信息的准确追踪（插入数、修改数、错误数）
    4. 详细的错误信息记录

    设计理念（来自quantbox）：
    - 每个保存操作都应该有明确的结果反馈
    - 错误信息要足够详细，便于调试
    - 性能指标要可度量（持续时间）
    - 结果要可序列化，便于日志记录
    """

    # 操作状态
    success: bool = True

    # 统计信息
    inserted_count: int = 0      # 新插入的记录数
    modified_count: int = 0      # 修改的记录数
    error_count: int = 0         # 错误数量

    # 错误详情
    errors: list[dict[str, Any]] = field(default_factory=list)

    # 时间追踪
    start_time: datetime.datetime = field(default_factory=datetime.datetime.now)
    end_time: datetime.datetime | None = None

    def add_error(self, error_type: str, error_msg: str, data: Any = None) -> None:
        """
        添加错误信息

        教学要点：
        1. 错误分类（error_type）便于统计分析
        2. 保存出错数据（data）便于调试
        3. 时间戳记录便于追踪错误发生时间

        Args:
            error_type: 错误类型（如 "VALIDATION_ERROR", "SAVE_ERROR", "NO_DATA"）
            error_msg: 错误消息
            data: 导致错误的数据（可选）

        Examples:
            >>> result = SaveResult()
            >>> result.add_error("VALIDATION_ERROR", "日期格式无效", {"date": "invalid"})
            >>> result.success  # False
            >>> result.error_count  # 1
        """
        self.success = False
        self.error_count += 1
        self.errors.append({
            "type": error_type,
            "message": error_msg,
            "data": data,
            "timestamp": datetime.datetime.now()
        })

    def complete(self) -> None:
        """
        完成操作，记录结束时间

        教学要点：
        - 明确操作的生命周期结束点
        - 持续时间的准确计算需要明确的end_time

        Examples:
            >>> result = SaveResult()
            >>> # ... 执行保存操作 ...
            >>> result.complete()
            >>> print(result.duration)  # 显示操作持续时间
        """
        self.end_time = datetime.datetime.now()

    @property
    def duration(self) -> datetime.timedelta:
        """
        获取操作持续时间

        教学要点：
        1. 使用@property提供计算属性
        2. 未完成操作时计算当前持续时间
        3. 已完成操作时使用end_time计算最终持续时间

        Returns:
            datetime.timedelta: 操作持续时间

        Examples:
            >>> result = SaveResult()
            >>> import time
            >>> time.sleep(0.1)
            >>> print(result.duration.total_seconds())  # ~0.1秒
        """
        if self.end_time:
            return self.end_time - self.start_time
        return datetime.datetime.now() - self.start_time

    @property
    def total_count(self) -> int:
        """
        获取总操作记录数

        Returns:
            int: 插入数 + 修改数
        """
        return self.inserted_count + self.modified_count

    @property
    def success_rate(self) -> float:
        """
        计算成功率

        Returns:
            float: 成功率（0.0-1.0），如果总数为0则返回1.0
        """
        total = self.total_count + self.error_count
        if total == 0:
            return 1.0
        return (self.total_count) / total

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典格式（便于JSON序列化和日志记录）

        教学要点：
        1. 提供多种格式输出支持
        2. 便于集成到日志系统
        3. 便于API响应返回

        Returns:
            dict: 包含所有追踪信息的字典

        Examples:
            >>> result = SaveResult()
            >>> result.inserted_count = 100
            >>> result.complete()
            >>> import json
            >>> print(json.dumps(result.to_dict(), default=str))
        """
        return {
            "success": self.success,
            "inserted_count": self.inserted_count,
            "modified_count": self.modified_count,
            "total_count": self.total_count,
            "error_count": self.error_count,
            "errors": self.errors,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": str(self.duration),
            "duration_seconds": self.duration.total_seconds(),
            "success_rate": self.success_rate,
        }

    def __repr__(self) -> str:
        """字符串表示"""
        status = "✓" if self.success else "✗"
        return (
            f"SaveResult({status} "
            f"total={self.total_count}, "
            f"inserted={self.inserted_count}, "
            f"modified={self.modified_count}, "
            f"errors={self.error_count}, "
            f"duration={self.duration.total_seconds():.2f}s)"
        )


# 使用示例
if __name__ == "__main__":
    import time

    print("=" * 60)
    print("SaveResult 使用示例")
    print("=" * 60)

    # 示例1：成功的保存操作
    print("\n示例1：成功的保存操作")
    result = SaveResult()
    time.sleep(0.1)  # 模拟操作
    result.inserted_count = 50
    result.modified_count = 30
    result.complete()
    print(result)
    print(f"成功率: {result.success_rate:.1%}")

    # 示例2：包含错误的保存操作
    print("\n示例2：包含错误的保存操作")
    result2 = SaveResult()
    result2.inserted_count = 80
    result2.add_error("VALIDATION_ERROR", "日期格式无效", {"date": "2024-13-45"})
    result2.add_error("SAVE_ERROR", "数据库连接失败")
    result2.complete()
    print(result2)
    print(f"错误详情：")
    for error in result2.errors:
        print(f"  - {error['type']}: {error['message']}")

    # 示例3：序列化为字典
    print("\n示例3：序列化为字典")
    result_dict = result.to_dict()
    print(f"插入数: {result_dict['inserted_count']}")
    print(f"修改数: {result_dict['modified_count']}")
    print(f"总计: {result_dict['total_count']}")
    print(f"持续时间: {result_dict['duration_seconds']:.3f}秒")
