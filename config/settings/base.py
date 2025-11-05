"""
CherryQuant 基础配置设置
使用Pydantic进行配置验证
"""

from pydantic import BaseModel, Field, validator
from typing import Optional
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class DatabaseConfig(BaseModel):
    """数据库配置"""
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_db: str = Field(default="cherryquant", env="POSTGRES_DB")
    postgres_user: str = Field(default="cherryquant", env="POSTGRES_USER")
    postgres_password: str = Field(default="cherryquant123", env="POSTGRES_PASSWORD")
    
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB", description="Redis数据库编号")
    
    cache_ttl: int = Field(default=300, env="CACHE_TTL", description="缓存TTL（秒）")
    connection_pool_size: int = Field(default=10, env="DB_POOL_SIZE", description="连接池大小")


class AIConfig(BaseModel):
    """AI配置"""
    model: str = Field(default="gpt-4", env="MODEL_NAME", description="使用的AI模型")
    base_url: str = Field(default="https://api.openai.com/v1", env="OPENAI_BASE_URL", description="API基础URL")
    api_key: str = Field(default="", env="OPENAI_API_KEY", description="API密钥")


class TradingConfig(BaseModel):
    """交易配置"""
    default_symbol: str = Field(default="rb2501", env="DEFAULT_SYMBOL", description="默认交易合约")
    exchange: str = Field(default="SHFE", env="EXCHANGE", description="默认交易所")
    decision_interval: int = Field(default=300, env="DECISION_INTERVAL", description="决策间隔（秒）")
    max_position_size: int = Field(default=10, env="MAX_POSITION_SIZE", description="最大持仓手数")
    default_leverage: float = Field(default=5.0, env="DEFAULT_LEVERAGE", description="默认杠杆")
    risk_per_trade: float = Field(default=0.02, env="RISK_PER_TRADE", description="每笔交易风险比例")
    
    @validator('default_leverage')
    def validate_leverage(cls, v):
        if not 1 <= v <= 10:
            raise ValueError("leverage must be between 1 and 10")
        return v


class DataSourceConfig(BaseModel):
    """数据源配置"""
    mode: str = Field(default="dev", env="DATA_MODE", description="数据模式: live(CTP实时) | dev(AKShare准实时)")
    source: str = Field(default="tushare", env="DATA_SOURCE", description="数据源类型")
    tushare_token: Optional[str] = Field(default=None, env="TUSHARE_TOKEN", description="Tushare令牌")

    # CTP配置
    ctp_userid: Optional[str] = Field(default=None, env="CTP_USERID", description="CTP用户ID")
    ctp_password: Optional[str] = Field(default=None, env="CTP_PASSWORD", description="CTP密码")
    ctp_broker_id: str = Field(default="9999", env="CTP_BROKER_ID", description="CTP期货公司ID")
    ctp_md_address: str = Field(default="tcp://180.168.146.187:10131", env="CTP_MD_ADDRESS", description="CTP行情服务器")
    ctp_td_address: str = Field(default="tcp://180.168.146.187:10130", env="CTP_TD_ADDRESS", description="CTP交易服务器")

    # 兼容旧配置
    simnow_userid: Optional[str] = Field(default=None, env="SIMNOW_USERID", description="Simnow用户ID (已弃用，使用CTP_USERID)")
    simnow_password: Optional[str] = Field(default=None, env="SIMNOW_PASSWORD", description="Simnow密码 (已弃用，使用CTP_PASSWORD)")
    simnow_broker_id: str = Field(default="9999", env="SIMNOW_BROKER_ID", description="Simnow期货公司ID (已弃用，使用CTP_BROKER_ID)")

    @validator('mode')
    def validate_mode(cls, v):
        if v not in ('live', 'dev'):
            raise ValueError("DATA_MODE must be 'live' or 'dev'")
        return v


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = Field(default="INFO", env="LOG_LEVEL", description="日志级别")
    log_dir: str = Field(default="./logs", env="LOG_DIR", description="日志目录")
    max_bytes: int = Field(default=10485760, env="LOG_MAX_BYTES", description="单个日志文件最大字节数")
    backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT", description="保留日志文件数量")


class CherryQuantConfig(BaseModel):
    """CherryQuant主配置"""
    database: DatabaseConfig = DatabaseConfig()
    ai: AIConfig = AIConfig()
    trading: TradingConfig = TradingConfig()
    data_source: DataSourceConfig = DataSourceConfig()
    logging: LoggingConfig = LoggingConfig()
    
    @classmethod
    def from_env(cls) -> 'CherryQuantConfig':
        """从环境变量创建配置"""
        return cls()


# 全局配置实例
CONFIG = CherryQuantConfig.from_env()