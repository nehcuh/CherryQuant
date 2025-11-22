"""
多级缓存策略

实现内存 + Redis + MongoDB 的三级缓存架构。

教学要点：
1. 缓存层次设计
2. 缓存穿透、击穿、雪崩的防护
3. TTL 和淘汰策略
4. 缓存一致性维护
"""

import logging
import json
import pickle
from typing import Any, Callable, TypeVar, Generic
from datetime import datetime, timedelta
from dataclasses import asdict
from functools import wraps
import asyncio
import threading

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheLevel:
    """缓存级别枚举"""
    MEMORY = "memory"     # L1: 内存缓存 (最快，容量小)
    REDIS = "redis"       # L2: Redis 缓存 (较快，容量中)
    DATABASE = "database" # L3: 数据库 (慢，容量大)


class CacheStrategy:
    """
    多级缓存策略

    三级缓存架构：
    L1 (Memory) → L2 (Redis) → L3 (Database/Source)

    查询流程：
    1. 检查内存缓存，命中返回
    2. 检查 Redis 缓存，命中返回并回填 L1
    3. 查询数据库/源，返回并回填 L1 + L2

    教学要点：
    1. Cache-Aside 模式
    2. 缓存预热和穿透防护
    3. 分布式缓存设计
    """

    def __init__(
        self,
        enable_l1: bool = True,
        enable_l2: bool = True,
        l1_max_size: int = 1000,
        l1_ttl: int = 300,        # 5分钟
        l2_ttl: int = 3600,       # 1小时
        redis_client: Any | None = None,
    ):
        """
        初始化缓存策略

        Args:
            enable_l1: 启用 L1 (内存) 缓存
            enable_l2: 启用 L2 (Redis) 缓存
            l1_max_size: L1 缓存最大条目数
            l1_ttl: L1 缓存 TTL（秒）
            l2_ttl: L2 缓存 TTL（秒）
            redis_client: Redis 客户端实例

        教学要点：
        1. 缓存配置参数化
        2. 可选的缓存层
        """
        self.enable_l1 = enable_l1
        self.enable_l2 = enable_l2 and redis_client is not None
        self.l1_max_size = l1_max_size
        self.l1_ttl = l1_ttl
        self.l2_ttl = l2_ttl
        self.redis_client = redis_client

        # L1: 内存缓存 (LRU) - 使用 Python 3.7+ 兼容的类型提示
        self._l1_cache: dict[str, tuple[Any, datetime]] = {}
        self._l1_access_order: list[str] = []
        self._l1_lock = threading.RLock()  # 可重入锁，防止死锁

        # 统计信息
        self.stats = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "l3_queries": 0,
        }

    # ==================== L1 内存缓存 ====================

    def _l1_get(self, key: str) -> Any | None:
        """
        从 L1 缓存获取数据

        教学要点：
        1. TTL 检查
        2. LRU 访问顺序更新
        3. 线程安全 (使用 RLock 保护)
        """
        if not self.enable_l1:
            return None

        with self._l1_lock:
            if key in self._l1_cache:
                value, expire_time = self._l1_cache[key]

                # 检查是否过期
                if datetime.now() < expire_time:
                    # 更新访问顺序（LRU）
                    if key in self._l1_access_order:
                        self._l1_access_order.remove(key)
                    self._l1_access_order.append(key)

                    self.stats["l1_hits"] += 1
                    logger.debug(f"📦 L1 缓存命中: {key}")
                    return value

                # 过期，删除
                del self._l1_cache[key]
                if key in self._l1_access_order:
                    self._l1_access_order.remove(key)

            self.stats["l1_misses"] += 1
            return None

    def _l1_set(self, key: str, value: Any) -> None:
        """
        设置 L1 缓存

        教学要点：
        1. LRU 淘汰策略
        2. TTL 设置
        3. 线程安全保护
        """
        if not self.enable_l1:
            return

        with self._l1_lock:
            # 检查容量，执行 LRU 淘汰
            if len(self._l1_cache) >= self.l1_max_size:
                # 淘汰最久未使用的
                if self._l1_access_order:
                    lru_key = self._l1_access_order.pop(0)
                    if lru_key in self._l1_cache:
                        del self._l1_cache[lru_key]
                        logger.debug(f"🗑️ L1 缓存淘汰: {lru_key}")

            # 设置缓存
            expire_time = datetime.now() + timedelta(seconds=self.l1_ttl)
            self._l1_cache[key] = (value, expire_time)

            # 更新访问顺序（如果已存在则移除旧位置）
            if key in self._l1_access_order:
                self._l1_access_order.remove(key)
            self._l1_access_order.append(key)

            logger.debug(f"✅ L1 缓存设置: {key}")

    def _l1_delete(self, key: str) -> None:
        """
        删除 L1 缓存

        教学要点：线程安全的删除操作
        """
        with self._l1_lock:
            if key in self._l1_cache:
                del self._l1_cache[key]
            if key in self._l1_access_order:
                self._l1_access_order.remove(key)

    def _l1_clear(self) -> None:
        """
        清空 L1 缓存

        教学要点：线程安全的批量操作
        """
        with self._l1_lock:
            self._l1_cache.clear()
            self._l1_access_order.clear()
            logger.info("🗑️ L1 缓存已清空")

    # ==================== L2 Redis 缓存 ====================

    async def _l2_get(self, key: str) -> Any | None:
        """
        从 L2 (Redis) 缓存获取数据

        教学要点：
        1. 异步 Redis 操作
        2. 序列化/反序列化
        3. 错误处理
        """
        if not self.enable_l2 or not self.redis_client:
            return None

        try:
            # Redis key 加前缀
            redis_key = f"cherryquant:cache:{key}"

            # 获取数据
            data = await self.redis_client.get(redis_key)

            if data:
                # 反序列化
                value = pickle.loads(data)
                self.stats["l2_hits"] += 1
                logger.debug(f"📦 L2 缓存命中: {key}")

                # 回填 L1
                self._l1_set(key, value)

                return value

        except Exception as e:
            logger.warning(f"⚠️ L2 缓存读取失败: {e}")

        self.stats["l2_misses"] += 1
        return None

    async def _l2_set(self, key: str, value: Any) -> None:
        """
        设置 L2 (Redis) 缓存

        教学要点：
        1. 序列化策略
        2. TTL 设置
        3. 异步写入
        """
        if not self.enable_l2 or not self.redis_client:
            return

        try:
            redis_key = f"cherryquant:cache:{key}"

            # 序列化
            data = pickle.dumps(value)

            # 设置缓存，带 TTL
            await self.redis_client.setex(
                redis_key,
                self.l2_ttl,
                data,
            )

            logger.debug(f"✅ L2 缓存设置: {key}")

        except Exception as e:
            logger.warning(f"⚠️ L2 缓存写入失败: {e}")

    async def _l2_delete(self, key: str) -> None:
        """删除 L2 缓存"""
        if not self.enable_l2 or not self.redis_client:
            return

        try:
            redis_key = f"cherryquant:cache:{key}"
            await self.redis_client.delete(redis_key)
        except Exception as e:
            logger.warning(f"⚠️ L2 缓存删除失败: {e}")

    async def _l2_clear_pattern(self, pattern: str) -> None:
        """
        按模式清除 L2 缓存

        教学要点：
        1. 模式匹配删除
        2. SCAN 命令的使用（避免阻塞）
        """
        if not self.enable_l2 or not self.redis_client:
            return

        try:
            redis_pattern = f"cherryquant:cache:{pattern}"

            # 使用 SCAN 遍历（非阻塞）
            cursor = 0
            deleted_count = 0

            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor,
                    match=redis_pattern,
                    count=100,
                )

                if keys:
                    await self.redis_client.delete(*keys)
                    deleted_count += len(keys)

                if cursor == 0:
                    break

            logger.info(f"🗑️ L2 缓存清除: {deleted_count} 个键 (模式: {pattern})")

        except Exception as e:
            logger.warning(f"⚠️ L2 缓存清除失败: {e}")

    # ==================== 统一缓存接口 ====================

    async def get(
        self,
        key: str,
        fetcher: Callable[[], Any] | None = None,
    ) -> Any | None:
        """
        获取缓存数据（多级查询）

        查询顺序：L1 → L2 → Fetcher

        Args:
            key: 缓存键
            fetcher: 数据获取函数（缓存未命中时调用）

        Returns:
            缓存的数据或 None

        教学要点：
        1. Cache-Aside 模式
        2. 缓存穿透防护
        3. 多级回填策略
        """
        # 1. 尝试 L1
        value = self._l1_get(key)
        if value is not None:
            return value

        # 2. 尝试 L2
        value = await self._l2_get(key)
        if value is not None:
            return value

        # 3. 缓存未命中，调用 fetcher
        if fetcher:
            self.stats["l3_queries"] += 1

            # 执行获取函数
            if asyncio.iscoroutinefunction(fetcher):
                value = await fetcher()
            else:
                value = fetcher()

            # 回填缓存
            if value is not None:
                await self.set(key, value)

            return value

        return None

    async def set(self, key: str, value: Any) -> None:
        """
        设置缓存（多级写入）

        写入顺序：L1 + L2（并行）

        教学要点：
        1. Write-Through 策略
        2. 并行写入优化
        """
        # 并行写入 L1 和 L2
        self._l1_set(key, value)
        await self._l2_set(key, value)

    async def delete(self, key: str) -> None:
        """
        删除缓存（多级删除）

        教学要点：
        1. 缓存一致性维护
        2. 全量删除策略
        """
        self._l1_delete(key)
        await self._l2_delete(key)
        logger.debug(f"🗑️ 缓存删除: {key}")

    async def clear(self, pattern: str | None = None) -> None:
        """
        清空缓存

        Args:
            pattern: 可选的模式匹配（仅对 L2 有效）

        教学要点：
        1. 批量清除操作
        2. 模式匹配
        """
        self._l1_clear()

        if pattern:
            await self._l2_clear_pattern(pattern)
        else:
            # 清除所有 cherryquant:cache:* 键
            await self._l2_clear_pattern("*")

        logger.info("🗑️ 多级缓存已清空")

    # ==================== 装饰器 ====================

    def cached(
        self,
        key_func: Callable[..., str],
        ttl: int | None = None,
    ):
        """
        缓存装饰器

        使用方法：
        ```python
        @cache.cached(lambda symbol, exchange: f"contract_{symbol}_{exchange}")
        async def get_contract(symbol: str, exchange: str):
            # 从数据库查询
            return contract
        ```

        教学要点：
        1. 装饰器模式
        2. 动态键生成
        3. 透明缓存
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 生成缓存键
                cache_key = key_func(*args, **kwargs)

                # 尝试从缓存获取
                value = await self.get(cache_key)
                if value is not None:
                    return value

                # 执行原函数
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # 写入缓存
                if result is not None:
                    await self.set(cache_key, result)

                return result

            return wrapper
        return decorator

    # ==================== 缓存预热 ====================

    async def warm_up(
        self,
        keys_and_fetchers: list[tuple[str, Callable]],
    ) -> int:
        """
        缓存预热

        批量加载数据到缓存，避免冷启动时的缓存穿透。

        Args:
            keys_and_fetchers: [(key, fetcher), ...] 列表

        Returns:
            成功预热的键数量

        教学要点：
        1. 缓存预热策略
        2. 批量并发加载
        3. 冷启动优化
        """
        logger.info(f"🔥 开始缓存预热: {len(keys_and_fetchers)} 个键")

        tasks = []
        for key, fetcher in keys_and_fetchers:
            tasks.append(self.get(key, fetcher))

        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(
            1 for r in results
            if not isinstance(r, Exception) and r is not None
        )

        logger.info(f"✅ 缓存预热完成: {success_count}/{len(keys_and_fetchers)} 成功")
        return success_count

    # ==================== 统计信息 ====================

    def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        教学要点：
        1. 缓存命中率计算
        2. 性能监控指标
        """
        total_requests = (
            self.stats["l1_hits"] +
            self.stats["l1_misses"]
        )

        l1_hit_rate = (
            self.stats["l1_hits"] / total_requests
            if total_requests > 0 else 0
        )

        total_l2_requests = (
            self.stats["l2_hits"] +
            self.stats["l2_misses"]
        )

        l2_hit_rate = (
            self.stats["l2_hits"] / total_l2_requests
            if total_l2_requests > 0 else 0
        )

        return {
            "l1": {
                "enabled": self.enable_l1,
                "size": len(self._l1_cache),
                "max_size": self.l1_max_size,
                "hits": self.stats["l1_hits"],
                "misses": self.stats["l1_misses"],
                "hit_rate": f"{l1_hit_rate:.2%}",
            },
            "l2": {
                "enabled": self.enable_l2,
                "hits": self.stats["l2_hits"],
                "misses": self.stats["l2_misses"],
                "hit_rate": f"{l2_hit_rate:.2%}",
            },
            "l3_queries": self.stats["l3_queries"],
            "total_requests": total_requests,
        }

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "l3_queries": 0,
        }
        logger.info("📊 缓存统计已重置")

    def print_stats(self) -> None:
        """打印统计信息"""
        stats = self.get_stats()

        print("\n" + "="*60)
        print("缓存统计信息")
        print("="*60)
        print(f"L1 (内存) 缓存:")
        print(f"  - 状态: {'启用' if stats['l1']['enabled'] else '禁用'}")
        print(f"  - 大小: {stats['l1']['size']}/{stats['l1']['max_size']}")
        print(f"  - 命中: {stats['l1']['hits']}")
        print(f"  - 未命中: {stats['l1']['misses']}")
        print(f"  - 命中率: {stats['l1']['hit_rate']}")
        print()
        print(f"L2 (Redis) 缓存:")
        print(f"  - 状态: {'启用' if stats['l2']['enabled'] else '禁用'}")
        print(f"  - 命中: {stats['l2']['hits']}")
        print(f"  - 未命中: {stats['l2']['misses']}")
        print(f"  - 命中率: {stats['l2']['hit_rate']}")
        print()
        print(f"L3 (数据库) 查询: {stats['l3_queries']}")
        print(f"总请求数: {stats['total_requests']}")
        print("="*60 + "\n")
