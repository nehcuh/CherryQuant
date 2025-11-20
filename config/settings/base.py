"""
CherryQuant 基础配置设置
使用Pydantic进行配置验证和环境变量管理
"""

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings
from typing import Optional, List
import os
import logging
from dotenv import load_dotenv


# 在导入配置类之前优先加载项目根目录下的 .env，
# 这样 pydantic-settings 可以从环境变量中读取到用户配置。
_ = load_dotenv()


# 兼容旧的环境变量命名：
# - DATA_MODE -> MODE（供 DataSourceConfig.mode 使用）
# - DATA_SOURCE -> SOURCE（供 DataSourceConfig.source 使用），并移除 DATA_SOURCE，
#   避免被 CherryQuantConfig.data_source 视为整体 JSON 配置。
if os.getenv("DATA_MODE") and not os.getenv("MODE"):
    os.environ["MODE"] = os.environ["DATA_MODE"]

if os.getenv("DATA_SOURCE"):
    if not os.getenv("SOURCE"):
        os.environ["SOURCE"] = os.environ["DATA_SOURCE"]
    # 避免嵌套 BaseSettings 将 DATA_SOURCE 当成复杂对象来解析
    _ = os.environ.pop("DATA_SOURCE", None)

# 兼容 AI 环境变量命名：将 OPENAI_* 映射到通用字段，
# 以便 AIConfig(model/base_url/api_key) 能在 pydantic-settings v2 下正常读取。
if os.getenv("OPENAI_MODEL") and not os.getenv("MODEL"):
    os.environ["MODEL"] = os.environ["OPENAI_MODEL"]

if os.getenv("OPENAI_BASE_URL") and not os.getenv("BASE_URL"):
    os.environ["BASE_URL"] = os.environ["OPENAI_BASE_URL"]

if os.getenv("OPENAI_API_KEY") and not os.getenv("API_KEY"):
    os.environ["API_KEY"] = os.environ["OPENAI_API_KEY"]

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """数据库配置"""

    # MongoDB 配置
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB连接URI",
    )
    mongodb_database: str = Field(default="cherryquant", description="MongoDB数据库名")
    mongodb_min_pool_size: int = Field(default=5, description="MongoDB最小连接池大小")
    mongodb_max_pool_size: int = Field(default=50, description="MongoDB最大连接池大小")
    mongodb_username: str | None = Field(default=None, description="MongoDB用户名")
    mongodb_password: str | None = Field(default=None, description="MongoDB密码")

    # Redis 配置（用于缓存）
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0, description="Redis数据库编号")
    redis_password: str | None = Field(default=None, description="Redis密码")

    cache_ttl: int = Field(default=300, description="缓存TTL（秒）")

    @field_validator("mongodb_uri")
    def validate_mongodb_uri(cls, v: str):
        """验证MongoDB URI"""
        if not v.startswith("mongodb://") and not v.startswith("mongodb+srv://"):
            raise ValueError(
                "MongoDB URI must start with 'mongodb://' or 'mongodb+srv://'"
            )
        return v

    class Config:
        env_file: str = ".env"
        env_file_encoding: str = "utf-8"
        case_sensitive: bool = True
        extra: str = "ignore"


class AIConfig(BaseSettings):
    """AI配置

    注意：此配置通过 env_file/.env 与环境变量映射，用于驱动
    AsyncOpenAIClient，而不再在适配层中直接读取 os.environ。
    """

    model: str = Field(
        default="gpt-4o", description="使用的AI模型", alias="OPENAI_MODEL"
    )
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="API基础URL",
        alias="OPENAI_BASE_URL",
    )
    api_key: str = Field(default="", description="API密钥", alias="OPENAI_API_KEY")
    temperature: float = Field(
        default=0.3, description="AI温度参数", alias="OPENAI_TEMPERATURE"
    )
    max_retries: int = Field(
        default=3, description="最大重试次数", alias="OPENAI_MAX_RETRIES"
    )
    timeout: int = Field(
        default=30, description="API超时时间（秒）", alias="OPENAI_TIMEOUT"
    )

    class Config:
        """环境变量与 .env 加载配置（兼容现有 OPENAI_* / *_TIMEOUT 等变量）"""

        env_file: str = ".env"
        env_file_encoding: str = "utf-8"
        extra: str = "ignore"

    @field_validator("api_key")
    def validate_api_key(cls, v: str, info: ValidationInfo):
        """验证API密钥"""
        # 获取base_url配置
        base_url = str(info.data.get("base_url", ""))  # type: ignore[arg-type]

        # 如果base_url包含本地地址，则忽略API密钥验证
        local_indicators = ["localhost", "127.0.0.1", "0.0.0.0", "::1"]
        if any(indicator in base_url for indicator in local_indicators):
            logger.info("ℹ️  使用本地API服务，跳过API密钥验证")
            return v

        if not v or v == "your_openai_api_key_here":
            logger.warning("⚠️ OpenAI API密钥未配置，AI功能将无法使用")
        return v

    @field_validator("temperature")
    def validate_temperature(cls, v: float):
        """验证温度参数"""
        if not 0 <= v <= 2:
            raise ValueError("AI temperature必须在0-2之间")
        return v


class TradingConfig(BaseSettings):
    """交易配置"""

    default_symbol: str = Field(default="rb2601", description="默认交易合约")
    exchange: str = Field(default="SHFE", description="默认交易所")
    decision_interval: int = Field(default=300, description="决策间隔（秒）")
    max_position_size: int = Field(default=10, description="最大持仓手数")
    default_leverage: float = Field(default=5.0, description="默认杠杆")
    risk_per_trade: float = Field(default=0.02, description="每笔交易风险比例")

    @field_validator("default_leverage")
    def validate_leverage(cls, v: float):
        if not 1 <= v <= 10:
            raise ValueError("leverage must be between 1 and 10")
        return v


class DataSourceConfig(BaseSettings):
    """数据源配置

    说明：
    - 推荐使用 .env 中的 DATA_MODE、DATA_SOURCE，
      我们在模块导入时已将其映射为 MODE / SOURCE 供本配置使用。
    """

    mode: str = Field(
        default="dev",
        description="数据模式: live(CTP实时) | dev(Tushare 准实时)",
        alias="DATA_MODE",
    )
    source: str = Field(
        default="tushare", description="数据源类型", alias="DATA_SOURCE"
    )
    tushare_token: Optional[str] = Field(default=None, description="Tushare令牌")

    # CTP配置
    ctp_userid: str | None = Field(default=None, description="CTP用户ID")
    ctp_password: str | None = Field(default=None, description="CTP密码")
    ctp_broker_id: str = Field(default="9999", description="CTP期货公司ID")
    ctp_md_address: str = Field(
        default="tcp://180.168.146.187:10131",
        description="CTP行情服务器",
    )
    ctp_td_address: str = Field(
        default="tcp://180.168.146.187:10130",
        description="CTP交易服务器",
    )

    @field_validator("data_mode")
    def validate_mode(cls, v: str):
        """验证数据模式"""
        if v not in ("live", "dev"):
            raise ValueError("DATA_MODE must be 'live' or 'dev'")
        return v

    @field_validator("tushare_token")
    def validate_tushare_token(cls, v: str):
        """验证Tushare令牌"""
        if not v or v == "your_tushare_pro_token_here":
            logger.warning("⚠️ Tushare Pro Token未配置，主力合约解析和历史数据功能受限")
        return v

    @model_validator(mode="after")
    def validate_live_mode_requirements(self):
        """验证live模式的必需配置"""
        data_mode = self.data_mode
        if data_mode == "live":
            # 验证 CTP 配置
            if not self.ctp_userid:
                raise ValueError("live模式需要配置CTP_USERID")
            if not self.ctp_password:
                raise ValueError("live模式需要配置CTP_PASSWORD")

            logger.info("✅ live模式配置验证通过")
        else:
            logger.info(f"ℹ️  使用 {data_mode} 模式（开发/测试模式）")

        return self


class RiskConfig(BaseSettings):
    """组合风险管理配置"""

    max_total_capital_usage: float = Field(default=0.8, description="最大总资金使用率")
    max_correlation_threshold: float = Field(default=0.7, description="最大相关性阈值")
    max_sector_concentration: float = Field(
        default=0.4,
        description="最大单一板块集中度",
    )
    portfolio_stop_loss: float = Field(default=0.1, description="组合止损比例")
    daily_loss_limit: float = Field(default=0.05, description="每日亏损限制")
    max_leverage_total: float = Field(default=3.0, description="总杠杆限制")

    @field_validator(
        "max_total_capital_usage",
        "max_correlation_threshold",
        "max_sector_concentration",
    )
    @classmethod
    def validate_percentage(cls, v: float):
        """验证百分比参数"""
        if not 0 < v <= 1:
            raise ValueError(f"Value must be between 0 and 1, got {v}")
        return v

    @field_validator("portfolio_stop_loss", "daily_loss_limit")
    @classmethod
    def validate_loss_limit(cls, v: float):
        """验证止损参数"""
        if not 0 < v <= 0.5:
            raise ValueError(f"Loss limit must be between 0 and 0.5, got {v}")
        return v

    @field_validator("max_leverage_total")
    @classmethod
    def validate_leverage(cls, v: float):
        """验证杠杆参数"""
        if not 1 <= v <= 10:
            raise ValueError("max_leverage_total must be between 1 and 10")
        return v


class LoggingConfig(BaseSettings):
    """日志配置"""

    level: str = Field(default="INFO", description="日志级别")
    log_dir: str = Field(default="./logs", description="日志目录")
    max_bytes: int = Field(default=10485760, description="单个日志文件最大字节数")
    backup_count: int = Field(default=5, description="保留日志文件数量")

    # Structured logging configuration
    json_logs: bool = Field(
        default=False,
        description="Enable JSON structured logs for production",
        alias="LOG_JSON",
    )
    enable_colors: bool = Field(
        default=True,
        description="Enable colored console output (disabled for JSON logs)",
        alias="LOG_COLORS",
    )


class AlertsConfig(BaseSettings):
    """警报/通知配置

    通过环境变量或 .env 文件统一管理邮件、微信、钉钉和通用 Webhook 通知。
    """

    # 邮件配置
    smtp_server: str = Field(
        default="smtp.gmail.com",
        description="SMTP 服务",
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP 端口",
    )
    email_sender: str = Field(
        default="cherryquant@example.com",
        description="发件人邮箱",
    )
    email_username: str = Field(
        default="cherryquant@example.com",
        description="登录用户名",
    )
    email_password: str = Field(
        default="",
        description="邮箱密码/授权码",
    )
    email_recipients: list[str] = Field(
        default_factory=lambda: ["admin@example.com"],
        description="收件人列表",
    )

    # 微信配置
    wechat_webhook_url: str = Field(
        default="",
        description="企业微信 Webhook URL",
    )
    wechat_enabled: bool = Field(
        default=False,
        description="是否启用微信通知",
    )

    # 钉钉配置
    dingtalk_webhook_url: str = Field(
        default="",
        description="钉钉 Webhook URL",
    )
    dingtalk_enabled: bool = Field(
        default=False,
        description="是否启用钉钉通知",
    )

    # 通用 Webhook 配置
    alert_webhook_url: str = Field(
        default="",
        description="通用告警 Webhook 地址",
    )
    webhook_token: str = Field(
        default="",
        description="Webhook 认证 Token",
    )

    @field_validator("email_recipients", mode="before")
    @classmethod
    def split_recipients(cls, v: str):  # type: ignore[override]
        """支持逗号分隔字符串或列表两种形式"""
        return [item.strip() for item in v.split(",") if item.strip()]

    class Config:
        env_file: str = ".env"
        env_file_encoding: str = "utf-8"
        extra: str = "ignore"


class CherryQuantConfig(BaseSettings):
    """CherryQuant主配置"""

    database: DatabaseConfig = DatabaseConfig()
    ai: AIConfig = AIConfig()
    trading: TradingConfig = TradingConfig()
    data_source: DataSourceConfig = DataSourceConfig()
    risk: RiskConfig = RiskConfig()
    logging: LoggingConfig = LoggingConfig()
    alerts: AlertsConfig = AlertsConfig()

    # 环境配置
    environment: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=False, description="调试模式")
    timezone: str = Field(default="Asia/Shanghai", description="时区")

    @classmethod
    def from_env(cls) -> "CherryQuantConfig":
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
        print("\n" + "=" * 60)
        print("📋 CherryQuant 配置摘要")
        print("=" * 60)
        print(f"🌍 运行环境: {self.environment}")
        print(f"🐛 调试模式: {self.debug}")
        print(f"🕐 时区: {self.timezone}")
        print(f"\n📊 数据模式: {self.data_source.mode}")
        print(f"📡 数据源: {self.data_source.source}")
        print(f"🤖 AI模型: {self.ai.model}")
        print(
            f"💾 MongoDB: {self.database.mongodb_uri}/{self.database.mongodb_database}"
        )
        print(
            f"🗃️  Redis缓存: {self.database.redis_host}:{self.database.redis_port}/{self.database.redis_db}"
        )
        print(f"📝 日志级别: {self.logging.level}")
        print(f"📁 日志目录: {self.logging.log_dir}")

        print(f"\n🛡️  风险管理配置:")
        print(f"  - 最大资金使用率: {self.risk.max_total_capital_usage:.0%}")
        print(f"  - 组合止损: {self.risk.portfolio_stop_loss:.0%}")
        print(f"  - 每日亏损限制: {self.risk.daily_loss_limit:.0%}")
        print(f"  - 最大板块集中度: {self.risk.max_sector_concentration:.0%}")
        print(f"  - 最大总杠杆: {self.risk.max_leverage_total:.1f}x")

        if self.data_source.mode == "live":
            print(f"\n🔴 LIVE 模式配置:")
            print(f"  - CTP账户: {self.data_source.ctp_userid}")
            print(f"  - CTP Broker: {self.data_source.ctp_broker_id}")
            print(f"  - 行情服务器: {self.data_source.ctp_md_address}")
            print(f"  - 交易服务器: {self.data_source.ctp_td_address}")
        else:
            print(f"\n🟢 DEV 模式配置:")
            print(f"  - 使用准实时数据（AKShare）")
            print(f"  - 无需CTP账户")

        print("=" * 60 + "\n")

    def validate_for_production(self):
        """生产环境配置验证"""
        issues: list[str] = []

        if self.environment == "production":
            # 生产环境必须检查
            # if not self.database.mongodb_username or not self.database.mongodb_password:
            #     issues.append("⚠️ 生产环境应启用MongoDB认证")

            # if not self.ai.api_key or self.ai.api_key == "your_openai_api_key_here":
            #     issues.append("⚠️ OpenAI API密钥未配置")

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
    if CONFIG.validate_for_production():
        print("Ready for production")
    else:
        print("Not ready")
