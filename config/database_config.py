"""
CherryQuant 数据库配置
"""

import os
from typing import Dict, Any
from adapters.data_storage.database_manager import DatabaseConfig

def get_database_config() -> DatabaseConfig:
    """获取数据库配置"""
    return DatabaseConfig(
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "cherryquant"),
        postgres_user=os.getenv("POSTGRES_USER", "cherryquant"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "cherryquant123"),
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_db=int(os.getenv("REDIS_DB", "0")),
        cache_ttl=int(os.getenv("CACHE_TTL", "300")),  # 5分钟缓存
    )

# 数据库连接配置（向后兼容）
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

# 数据源配置
DATA_SOURCES = {
    "primary": "akshare",
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