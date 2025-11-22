"""
重试和错误恢复工具

提供生产级的错误恢复机制，包括：
1. 指数退避重试
2. 断路器模式
3. 降级策略
4. 错误分类和处理

教学要点：
1. 容错设计
2. 弹性工程
3. 生产级错误处理
"""

import logging
import asyncio
import time
from typing import Callable, Any, Type, Union
from functools import wraps
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ==================== 重试策略配置 ====================

class RetryStrategy(Enum):
    """重试策略"""
    EXPONENTIAL = "exponential"  # 指数退避
    LINEAR = "linear"            # 线性退避
    FIXED = "fixed"              # 固定延迟
    IMMEDIATE = "immediate"      # 立即重试


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3              # 最大重试次数
    base_delay: float = 1.0            # 基础延迟（秒）
    max_delay: float = 60.0            # 最大延迟（秒）
    exponential_base: float = 2.0      # 指数退避基数
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL

    # 可重试的异常类型
    retriable_exceptions: tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    )

    # 不可重试的异常类型 (快速失败)
    non_retriable_exceptions: tuple[Type[Exception], ...] = (
        ValueError,
        TypeError,
        KeyError,
    )


# ==================== 断路器模式 ====================

class CircuitState(Enum):
    """断路器状态"""
    CLOSED = "closed"      # 关闭：正常工作
    OPEN = "open"          # 打开：停止调用
    HALF_OPEN = "half_open"  # 半开：尝试恢复


@dataclass
class CircuitBreakerConfig:
    """断路器配置"""
    failure_threshold: int = 5         # 失败阈值
    success_threshold: int = 2         # 成功阈值（半开状态）
    timeout: float = 60.0              # 打开状态持续时间（秒）
    half_open_max_calls: int = 1       # 半开状态最大调用数


class CircuitBreaker:
    """
    断路器模式实现

    防止级联失败，提供快速失败和自动恢复机制。

    教学要点：
    1. 断路器模式的三种状态
    2. 失败计数和阈值判断
    3. 自动恢复机制
    4. 生产环境的弹性设计
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.half_open_calls = 0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过断路器调用函数

        教学要点：
        1. 状态机模式
        2. 失败快速返回
        3. 自动状态转换
        """
        if self.state == CircuitState.OPEN:
            # 检查是否应该尝试恢复
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError(
                    f"断路器打开，拒绝调用 {func.__name__}"
                )

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"断路器半开状态已达最大调用数"
                )
            self.half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """异步版本的断路器调用"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError(
                    f"断路器打开，拒绝调用 {func.__name__}"
                )

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"断路器半开状态已达最大调用数"
                )
            self.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """成功回调"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()

        # 重置失败计数
        self.failure_count = 0

    def _on_failure(self) -> None:
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            # 半开状态失败，立即打开
            self._transition_to_open()
        elif self.failure_count >= self.config.failure_threshold:
            # 失败次数超过阈值，打开断路器
            self._transition_to_open()

    def _should_attempt_reset(self) -> bool:
        """判断是否应该尝试重置"""
        if self.last_failure_time is None:
            return True

        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.config.timeout

    def _transition_to_closed(self) -> None:
        """转换到关闭状态"""
        logger.info(f"🟢 断路器关闭：恢复正常")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0

    def _transition_to_open(self) -> None:
        """转换到打开状态"""
        logger.warning(f"🔴 断路器打开：停止调用")
        self.state = CircuitState.OPEN
        self.success_count = 0
        self.half_open_calls = 0

    def _transition_to_half_open(self) -> None:
        """转换到半开状态"""
        logger.info(f"🟡 断路器半开：尝试恢复")
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0


class CircuitBreakerOpenError(Exception):
    """断路器打开异常"""
    pass


# ==================== 重试装饰器 ====================

def retry_async(
    config: RetryConfig | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> Callable:
    """
    异步函数重试装饰器

    使用示例：
        @retry_async(RetryConfig(max_attempts=3))
        async def fetch_data():
            ...

    教学要点：
    1. 装饰器模式
    2. 指数退避算法
    3. 错误分类处理
    4. 断路器集成
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    # 通过断路器调用
                    if circuit_breaker:
                        return await circuit_breaker.call_async(func, *args, **kwargs)
                    else:
                        return await func(*args, **kwargs)

                except config.non_retriable_exceptions as e:
                    # 不可重试的异常，立即失败
                    logger.error(f"❌ 不可重试的异常: {type(e).__name__}: {e}")
                    raise

                except config.retriable_exceptions as e:
                    last_exception = e

                    if attempt >= config.max_attempts:
                        logger.error(
                            f"❌ {func.__name__} 重试{config.max_attempts}次后仍失败"
                        )
                        break

                    # 计算延迟
                    delay = _calculate_delay(attempt, config)

                    logger.warning(
                        f"⚠️ {func.__name__} 第{attempt}次失败: {type(e).__name__}: {e}, "
                        f"{delay:.1f}秒后重试"
                    )

                    await asyncio.sleep(delay)

                except Exception as e:
                    # 未预期的异常，记录但仍重试
                    last_exception = e

                    if attempt >= config.max_attempts:
                        logger.error(
                            f"❌ {func.__name__} 重试{config.max_attempts}次后仍失败: "
                            f"{type(e).__name__}: {e}"
                        )
                        break

                    delay = _calculate_delay(attempt, config)
                    logger.warning(
                        f"⚠️ {func.__name__} 遇到未预期异常: {type(e).__name__}: {e}, "
                        f"{delay:.1f}秒后重试"
                    )
                    await asyncio.sleep(delay)

            # 所有重试都失败，抛出最后一个异常
            raise last_exception

        return wrapper
    return decorator


def retry_sync(
    config: RetryConfig | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> Callable:
    """
    同步函数重试装饰器

    教学要点：同步版本的重试机制
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    if circuit_breaker:
                        return circuit_breaker.call(func, *args, **kwargs)
                    else:
                        return func(*args, **kwargs)

                except config.non_retriable_exceptions as e:
                    logger.error(f"❌ 不可重试的异常: {type(e).__name__}: {e}")
                    raise

                except config.retriable_exceptions as e:
                    last_exception = e

                    if attempt >= config.max_attempts:
                        logger.error(
                            f"❌ {func.__name__} 重试{config.max_attempts}次后仍失败"
                        )
                        break

                    delay = _calculate_delay(attempt, config)
                    logger.warning(
                        f"⚠️ {func.__name__} 第{attempt}次失败, {delay:.1f}秒后重试"
                    )
                    time.sleep(delay)

                except Exception as e:
                    last_exception = e

                    if attempt >= config.max_attempts:
                        logger.error(f"❌ {func.__name__} 重试失败: {e}")
                        break

                    delay = _calculate_delay(attempt, config)
                    logger.warning(f"⚠️ {func.__name__} 异常: {e}, {delay:.1f}秒后重试")
                    time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    计算重试延迟

    教学要点：
    1. 指数退避算法
    2. 防止雪崩效应
    3. 延迟上限控制
    """
    if config.strategy == RetryStrategy.EXPONENTIAL:
        # 指数退避: delay = base * (exponential_base ^ attempt)
        delay = config.base_delay * (config.exponential_base ** (attempt - 1))
    elif config.strategy == RetryStrategy.LINEAR:
        # 线性退避: delay = base * attempt
        delay = config.base_delay * attempt
    elif config.strategy == RetryStrategy.FIXED:
        # 固定延迟
        delay = config.base_delay
    else:  # IMMEDIATE
        delay = 0

    # 限制最大延迟
    return min(delay, config.max_delay)


# ==================== 降级策略 ====================

class FallbackStrategy:
    """
    降级策略

    当主要操作失败时，提供备用方案。

    教学要点：
    1. 降级设计
    2. 优雅失败
    3. 用户体验保障
    """

    @staticmethod
    async def with_fallback(
        primary: Callable,
        fallback: Callable,
        fallback_exceptions: tuple[Type[Exception], ...] = (Exception,),
    ) -> Any:
        """
        带降级的异步调用

        Args:
            primary: 主要函数
            fallback: 降级函数
            fallback_exceptions: 触发降级的异常类型

        Returns:
            primary或fallback的返回值
        """
        try:
            return await primary()
        except fallback_exceptions as e:
            logger.warning(f"⚠️ 主要操作失败，使用降级方案: {type(e).__name__}: {e}")
            return await fallback()

    @staticmethod
    def with_fallback_sync(
        primary: Callable,
        fallback: Callable,
        fallback_exceptions: tuple[Type[Exception], ...] = (Exception,),
    ) -> Any:
        """带降级的同步调用"""
        try:
            return primary()
        except fallback_exceptions as e:
            logger.warning(f"⚠️ 主要操作失败，使用降级方案: {type(e).__name__}: {e}")
            return fallback()


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 示例1: 基础重试
    @retry_async(RetryConfig(max_attempts=3, base_delay=1.0))
    async def fetch_data_with_retry():
        # 模拟可能失败的操作
        import random
        if random.random() < 0.7:
            raise ConnectionError("网络错误")
        return "数据"

    # 示例2: 带断路器的重试
    breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))

    @retry_async(
        RetryConfig(max_attempts=5),
        circuit_breaker=breaker,
    )
    async def fetch_with_circuit_breaker():
        # 高可靠性的数据获取
        pass

    # 示例3: 降级策略
    async def main():
        result = await FallbackStrategy.with_fallback(
            primary=lambda: fetch_data_with_retry(),
            fallback=lambda: asyncio.sleep(0) or "缓存数据",
        )
        print(f"结果: {result}")

    # asyncio.run(main())
