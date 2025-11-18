"""
警报配置文件
配置各种通知渠道的参数

当前实现通过 CherryQuantConfig.alerts 统一管理，避免在业务代码中直接读取环境变量。
"""

from typing import Dict, Any

from config.settings.base import CONFIG

def get_alert_config() -> Dict[str, Any]:
    """获取警报配置（从 CherryQuantConfig.alerts 派生字典结构）"""
    alerts = CONFIG.alerts

    return {
        "email": {
            "smtp_server": alerts.smtp_server,
            "smtp_port": alerts.smtp_port,
            "sender": alerts.email_sender,
            "username": alerts.email_username,
            "password": alerts.email_password,
            "recipients": alerts.email_recipients,
        },
        "wechat": {
            "webhook_url": alerts.wechat_webhook_url,
            "enabled": alerts.wechat_enabled,
        },
        "dingtalk": {
            "webhook_url": alerts.dingtalk_webhook_url,
            "enabled": alerts.dingtalk_enabled,
        },
        "webhook": {
            "url": alerts.alert_webhook_url,
            "headers": {
                "Authorization": f"Bearer {alerts.webhook_token}",
                "Content-Type": "application/json",
            },
        },
    }
