"""
Docker-specific override for CherryQuant DATABASE_CONFIG so services in containers
connect to the Compose service hostnames instead of localhost.
"""

DATABASE_CONFIG = {
    "postgresql": {
        "host": "postgresql",  # service name from docker/docker-compose.yml
        "port": 5432,
        "database": "cherryquant",
        "user": "cherryquant",
        "password": "cherryquant123",
    },
    "redis": {
        "host": "redis",  # service name from docker/docker-compose.yml
        "port": 6379,
        "db": 0,
    },
    "influxdb": {
        "url": "http://influxdb:8086",
        "token": "cherryquant-super-secret-token",
        "org": "cherryquant",
        "bucket": "market_data",
    },
    "cache_ttl": 300,
    "connection_pool_size": 10,
}

DATA_RETENTION_POLICY = {
    "market_data": {
        "1m": 3,
        "5m": 7,
        "15m": 30,
        "1h": 90,
        "4h": 365,
        "1d": -1,
    },
    "technical_indicators": {"default": 365},
    "ai_decisions": {"default": -1},
    "trades": {"default": -1},
}

DATA_SOURCES = {
    "primary": "akshare",
    "fallback": "simnow",
    "update_interval": {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    },
}
