"""
CherryQuant 基础配置设置
使用Pydantic进行配置验证和环境变量管理
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List
import os
import logging
from dotenv import load_dotenv

# 加载环境变量
env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(env_file)

logger = logging.getLogger(__name__)


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
    model: str = Field(default="gpt-4", env="OPENAI_MODEL", description="使用的AI模型")
    base_url: str = Field(default="https://api.openai.com/v1", env="OPENAI_BASE_URL", description="API基础URL")
    api_key: str = Field(default="", env="OPENAI_API_KEY", description="API密钥")
    temperature: float = Field(default=0.1, env="AI_TEMPERATURE", description="AI温度参数")
    max_retries: int = Field(default=3, env="MAX_RETRIES", description="最大重试次数")
    timeout: int = Field(default=30, env="API_TIMEOUT", description="API超时时间（秒）")

    @validator('api_key')
    def validate_api_key(cls, v):
        """验证API密钥"""
        if not v or v == "your_openai_api_key_here":
            logger.warning("⚠️ OpenAI API密钥未配置，AI功能将无法使用")
        return v

    @validator('temperature')
    def validate_temperature(cls, v):
        """验证温度参数"""
        if not 0 <= v <= 2:
            raise ValueError("AI temperature必须在0-2之间")
        return v


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
        """验证数据模式"""
        if v not in ('live', 'dev'):
            raise ValueError("DATA_MODE must be 'live' or 'dev'")
        return v

    @validator('tushare_token')
    def validate_tushare_token(cls, v):
        """验证Tushare令牌"""
        if not v or v == "your_tushare_pro_token_here":
            logger.warning("⚠️ Tushare Pro Token未配置，主力合约解析和历史数据功能受限")
        return v

    @root_validator
    def validate_live_mode_requirements(cls, values):
        """验证live模式的必需配置"""
        mode = values.get('mode')
        if mode == 'live':
            ctp_userid = values.get('ctp_userid')
            ctp_password = values.get('ctp_password')

            # 向后兼容：检查旧的simnow配置
            simnow_userid = values.get('simnow_userid')
            simnow_password = values.get('simnow_password')

            if simnow_userid and not ctp_userid:
                logger.warning("⚠️ SIMNOW_USERID已弃用，请使用CTP_USERID")
                values['ctp_userid'] = simnow_userid

            if simnow_password and not ctp_password:
                logger.warning("⚠️ SIMNOW_PASSWORD已弃用，请使用CTP_PASSWORD")
                values['ctp_password'] = simnow_password

            # 验证CTP配置
            if not values.get('ctp_userid'):
                raise ValueError("live模式需要配置CTP_USERID")
            if not values.get('ctp_password'):
                raise ValueError("live模式需要配置CTP_PASSWORD")

            logger.info("✅ live模式配置验证通过")
        else:
            logger.info(f"ℹ️  使用 {mode} 模式（开发/测试模式）")

        return values


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

    # 环境配置
    environment: str = Field(default="development", env="ENVIRONMENT", description="运行环境")
    debug: bool = Field(default=False, env="DEBUG", description="调试模式")
    timezone: str = Field(default="Asia/Shanghai", env="TIMEZONE", description="时区")

    @classmethod
    def from_env(cls) -> 'CherryQuantConfig':
        """从环境变量创建配置"""
        try:
            config = cls()
            logger.info("✅ 配置加载成功")
            return config
        except Exception as e:
            logger.error(f"❌ 配置加载失败: {e}")
            raise

    def print_summary(self):
        """打印配置摘要"""
        print("\n" + "="*60)
        print("📋 CherryQuant 配置摘要")
        print("="*60)
        print(f"🌍 运行环境: {self.environment}")
        print(f"🐛 调试模式: {self.debug}")
        print(f"🕐 时区: {self.timezone}")
        print(f"\n📊 数据模式: {self.data_source.mode}")
        print(f"📡 数据源: {self.data_source.source}")
        print(f"🤖 AI模型: {self.ai.model}")
        print(f"💾 数据库: {self.database.postgres_host}:{self.database.postgres_port}/{self.database.postgres_db}")
        print(f"📝 日志级别: {self.logging.level}")
        print(f"📁 日志目录: {self.logging.log_dir}")

        if self.data_source.mode == 'live':
            print(f"\n🔴 LIVE 模式配置:")
            print(f"  - CTP账户: {self.data_source.ctp_userid}")
            print(f"  - CTP Broker: {self.data_source.ctp_broker_id}")
            print(f"  - 行情服务器: {self.data_source.ctp_md_address}")
            print(f"  - 交易服务器: {self.data_source.ctp_td_address}")
        else:
            print(f"\n🟢 DEV 模式配置:")
            print(f"  - 使用准实时数据（AKShare）")
            print(f"  - 无需CTP账户")

        print("="*60 + "\n")

    def validate_for_production(self):
        """生产环境配置验证"""
        issues = []

        if self.environment == "production":
            # 生产环境必须检查
            if self.database.postgres_password == "cherryquant123":
                issues.append("⚠️ 使用默认数据库密码，存在安全风险")

            if not self.ai.api_key or self.ai.api_key == "your_openai_api_key_here":
                issues.append("⚠️ OpenAI API密钥未配置")

            if self.data_source.mode == "live":
                if not self.data_source.ctp_userid or not self.data_source.ctp_password:
                    issues.append("⚠️ CTP账户配置不完整")

        if issues:
            logger.warning("生产环境配置检查发现问题:")
            for issue in issues:
                logger.warning(f"  {issue}")
            return False

        logger.info("✅ 生产环境配置检查通过")
        return True


# 全局配置实例
CONFIG = CherryQuantConfig.from_env()

# 打印配置摘要（仅在直接运行时）
if __name__ == "__main__":
    CONFIG.print_summary()
    CONFIG.validate_for_production()