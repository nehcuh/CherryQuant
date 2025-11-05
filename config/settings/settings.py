"""
CherryQuant 主设置文件
整合所有配置模块
"""

from .base import CONFIG, CherryQuantConfig

# 向后兼容的设置 - 保持与原有代码的兼容性
TRADING_CONFIG = {
    "default_symbol": CONFIG.trading.default_symbol,
    "decision_interval": CONFIG.trading.decision_interval,
    "max_position_size": CONFIG.trading.max_position_size,
    "default_leverage": CONFIG.trading.default_leverage,
    "risk_per_trade": CONFIG.trading.risk_per_trade,
}

LOGGING_CONFIG = {
    "level": CONFIG.logging.level,
    "log_dir": CONFIG.logging.log_dir,
}

AI_CONFIG = {
    "model": CONFIG.ai.model,
    "base_url": CONFIG.ai.base_url,
}

RISK_CONFIG = {
    "max_drawdown": 0.15,  # 最大回撤15%
    "max_loss_per_day": 0.05,  # 单日最大损失5%
    "max_capital_usage": 0.8,  # 最大资金使用率80%
    "position_size_limit": CONFIG.trading.max_position_size,
}