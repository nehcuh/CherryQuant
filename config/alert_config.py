"""
警报配置文件
配置各种通知渠道的参数
"""

import os
from typing import Dict, Any

def get_alert_config() -> Dict[str, Any]:
    """获取警报配置"""
    return {
        "email": {
            "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "sender": os.getenv("EMAIL_SENDER", "cherryquant@example.com"),
            "username": os.getenv("EMAIL_USERNAME", "cherryquant@example.com"),
            "password": os.getenv("EMAIL_PASSWORD", ""),
            "recipients": os.getenv("EMAIL_RECIPIENTS", "admin@example.com").split(",")
        },
        "wechat": {
            "webhook_url": os.getenv("WECHAT_WEBHOOK_URL", ""),
            "enabled": bool(os.getenv("WECHAT_ENABLED", "false").lower() == "true")
        },
        "dingtalk": {
            "webhook_url": os.getenv("DINGTALK_WEBHOOK_URL", ""),
            "enabled": bool(os.getenv("DINGTALK_ENABLED", "false").lower() == "true")
        },
        "webhook": {
            "url": os.getenv("ALERT_WEBHOOK_URL", ""),
            "headers": {
                "Authorization": f"Bearer {os.getenv('WEBHOOK_TOKEN', '')}",
                "Content-Type": "application/json"
            }
        }
    }