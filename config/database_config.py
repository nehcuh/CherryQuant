"""
CherryQuant 数据库配置
"""

import os
from typing import Dict, Any
from config.settings.base import CONFIG

def get_database_config() -> Dict[str, Any]:
    """
    获取数据库配置（使用全局 CONFIG 作为单一来源）

    Returns:
        包含 MongoDB 和 Redis 配置的字典
    """
    return {
        # MongoDB 配置
        "mongodb_uri": CONFIG.database.mongodb_uri,
        "mongodb_database": CONFIG.database.mongodb_database,
        "mongodb_min_pool_size": CONFIG.database.mongodb_min_pool_size,
        "mongodb_max_pool_size": CONFIG.database.mongodb_max_pool_size,
        # Redis 配置
        "redis_host": CONFIG.database.redis_host,
        "redis_port": CONFIG.database.redis_port,
        "redis_db": CONFIG.database.redis_db,
        "cache_ttl": CONFIG.database.cache_ttl,
    }

# 数据库连接配置（向后兼容，基于 CONFIG 构建）
DATABASE_CONFIG = get_database_config()

# 数据保留策略
DATA_RETENTION_POLICY = {
    "market_data": {
        "1m": 3,    # 1分钟数据保留3天
        "5m": 7,    # 5分钟数据保留7天
        "15m": 30,  # 15分钟数据保留30天
        "1h": 90,   # 1小时数据保留90天
        "4h": 365,  # 4小时数据保留1年
        "1d": -1    # 日数据永久保留
    },
    "technical_indicators": {
        "default": 365  # 技术指标保留1年
    },
    "ai_decisions": {
        "default": -1  # AI决策永久保留
    },
    "trades": {
        "default": -1  # 交易记录永久保留
    }
}

# 数据源配置（已迁移至 QuantBox）
DATA_SOURCES = {
    "primary": "quantbox",  # QuantBox (Tushare) - 替代 AKShare
    "fallback": "simnow",
    "update_interval": {
        "1m": 60,     # 1分钟数据每60秒更新
        "5m": 300,    # 5分钟数据每5分钟更新
        "15m": 900,   # 15分钟数据每15分钟更新
        "1h": 3600,   # 1小时数据每小时更新
        "4h": 14400,  # 4小时数据每4小时更新
        "1d": 86400   # 日数据每天更新
    }
}
