"""
实时警报系统
支持多种通知方式，包括微信、邮件、钉钉等
"""

import asyncio
import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import requests
import aiohttp

from ..risk.portfolio_risk_manager import RiskEvent, RiskEventType, RiskLevel

logger = logging.getLogger(__name__)

class AlertChannel(Enum):
    """警报渠道"""
    EMAIL = "email"
    WECHAT = "wechat"
    DINGTALK = "dingtalk"
    SLACK = "slack"
    WEBHOOK = "webhook"

class AlertStatus(Enum):
    """警报状态"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

@dataclass
class AlertRule:
    """警报规则"""
    rule_id: str
    name: str
    description: str
    event_types: List[RiskEventType]
    severity_threshold: RiskLevel
    channels: List[AlertChannel]
    cooldown_minutes: int = 30
    enabled: bool = True
    conditions: Dict[str, Any] = None

@dataclass
class Alert:
    """警报"""
    alert_id: str
    rule_id: str
    event: RiskEvent
    status: AlertStatus
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    channels_sent: List[AlertChannel] = None
    error_message: Optional[str] = None

class AlertManager:
    """警报管理器"""

    def __init__(
        self,
        email_config: Optional[Dict[str, Any]] = None,
        wechat_config: Optional[Dict[str, Any]] = None,
        dingtalk_config: Optional[Dict[str, Any]] = None,
        webhook_config: Optional[Dict[str, Any]] = None
    ):
        """初始化警报管理器

        Args:
            email_config: 邮件配置
            wechat_config: 微信配置
            dingtalk_config: 钉钉配置
            webhook_config: Webhook配置
        """
        self.email_config = email_config or {}
        self.wechat_config = wechat_config or {}
        self.dingtalk_config = dingtalk_config or {}
        self.webhook_config = webhook_config or {}

        # 警报规则
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}

        # 警报历史
        self.alert_history: List[Alert] = []

        # 冷却时间记录
        self.cooldown_timers: Dict[str, datetime] = {}

        # 回调函数
        self.alert_callbacks: List[Callable] = []

        # HTTP会话
        self.session: Optional[aiohttp.ClientSession] = None

        # 初始化默认规则
        self._initialize_default_rules()

        logger.info("警报管理器初始化完成")

    async def start(self) -> None:
        """启动警报管理器"""
        self.session = aiohttp.ClientSession()
        logger.info("警报管理器已启动")

    async def stop(self) -> None:
        """停止警报管理器"""
        if self.session:
            await self.session.close()
        logger.info("警报管理器已停止")

    def _initialize_default_rules(self) -> None:
        """初始化默认警报规则"""
        default_rules = [
            AlertRule(
                rule_id="critical_daily_loss",
                name="每日巨额亏损警报",
                description="当日亏损超过5%时发送紧急警报",
                event_types=[RiskEventType.DAILY_LOSS_LIMIT],
                severity_threshold=RiskLevel.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.WECHAT],
                cooldown_minutes=60
            ),
            AlertRule(
                rule_id="high_drawdown",
                name="高回撤警报",
                description="回撤超过15%时发送警报",
                event_types=[RiskEventType.MAX_DRAWDOWN],
                severity_threshold=RiskLevel.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.WECHAT],
                cooldown_minutes=120
            ),
            AlertRule(
                rule_id="capital_usage_alert",
                name="资金使用率警报",
                description="资金使用率超过80%时发送警报",
                event_types=[RiskEventType.CAPITAL_USAGE_EXCEEDED],
                severity_threshold=RiskLevel.HIGH,
                channels=[AlertChannel.EMAIL],
                cooldown_minutes=30
            ),
            AlertRule(
                rule_id="correlation_risk",
                name="相关性风险警报",
                description="策略间相关性过高时发送警报",
                event_types=[RiskEventType.CORRELATION_RISK],
                severity_threshold=RiskLevel.MEDIUM,
                channels=[AlertChannel.EMAIL],
                cooldown_minutes=180
            ),
            AlertRule(
                rule_id="sector_concentration",
                name="板块集中度警报",
                description="单一板块集中度过高时发送警报",
                event_types=[RiskEventType.SECTOR_CONCENTRATION],
                severity_threshold=RiskLevel.MEDIUM,
                channels=[AlertChannel.EMAIL],
                cooldown_minutes=180
            )
        ]

        for rule in default_rules:
            self.rules[rule.rule_id] = rule

    async def handle_risk_event(self, event: RiskEvent) -> None:
        """处理风险事件"""
        try:
            # 查找匹配的规则
            matching_rules = self._find_matching_rules(event)

            for rule in matching_rules:
                if not rule.enabled:
                    continue

                # 检查冷却时间
                if self._is_in_cooldown(rule.rule_id):
                    logger.debug(f"规则 {rule.rule_id} 在冷却期内，跳过")
                    continue

                # 创建警报
                alert = await self._create_alert(rule, event)
                if alert:
                    await self._send_alert(alert)

        except Exception as e:
            logger.error(f"处理风险事件失败: {e}")

    def _find_matching_rules(self, event: RiskEvent) -> List[AlertRule]:
        """查找匹配的警报规则"""
        matching_rules = []

        for rule in self.rules.values():
            # 事件类型匹配
            if event.event_type not in rule.event_types:
                continue

            # 严重程度匹配
            if self._compare_severity(event.severity, rule.severity_threshold) < 0:
                continue

            # 条件匹配
            if rule.conditions and not self._check_conditions(rule.conditions, event):
                continue

            matching_rules.append(rule)

        return matching_rules

    def _compare_severity(self, event_severity: RiskLevel, threshold: RiskLevel) -> int:
        """比较严重程度"""
        severity_order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3
        }

        return severity_order[event_severity] - severity_order[threshold]

    def _check_conditions(self, conditions: Dict[str, Any], event: RiskEvent) -> bool:
        """检查警报条件"""
        try:
            # 策略ID过滤
            if 'strategy_ids' in conditions:
                if event.strategy_id not in conditions['strategy_ids']:
                    return False

            # 数值范围检查
            if 'min_value' in conditions and event.current_value < conditions['min_value']:
                return False

            if 'max_value' in conditions and event.current_value > conditions['max_value']:
                return False

            # 时间窗口检查
            if 'time_window' in conditions:
                window_minutes = conditions['time_window']
                cutoff_time = datetime.now() - timedelta(minutes=window_minutes)

                recent_events = [
                    e for e in self.alert_history
                    if e.created_at > cutoff_time and e.rule_id in conditions.get('related_rules', [])
                ]

                max_events = conditions.get('max_events_in_window', 1)
                if len(recent_events) >= max_events:
                    return False

            return True

        except Exception as e:
            logger.error(f"检查警报条件失败: {e}")
            return False

    def _is_in_cooldown(self, rule_id: str) -> bool:
        """检查是否在冷却期内"""
        if rule_id not in self.cooldown_timers:
            return False

        cooldown_time = self.cooldown_timers[rule_id]
        rule = self.rules.get(rule_id)

        if not rule:
            return False

        return datetime.now() < cooldown_time + timedelta(minutes=rule.cooldown_minutes)

    async def _create_alert(self, rule: AlertRule, event: RiskEvent) -> Optional[Alert]:
        """创建警报"""
        import uuid

        alert = Alert(
            alert_id=str(uuid.uuid4()),
            rule_id=rule.rule_id,
            event=event,
            status=AlertStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            channels_sent=[]
        )

        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)

        # 设置冷却时间
        self.cooldown_timers[rule.rule_id] = datetime.now()

        logger.info(f"创建警报: {alert.alert_id} - {rule.name}")
        return alert

    async def _send_alert(self, alert: Alert) -> None:
        """发送警报"""
        rule = self.rules.get(alert.rule_id)
        if not rule:
            return

        for channel in rule.channels:
            try:
                success = await self._send_to_channel(alert, channel)
                if success:
                    alert.channels_sent.append(channel)
                    logger.info(f"警报已发送到 {channel.value}: {alert.alert_id}")
                else:
                    logger.error(f"警报发送失败到 {channel.value}: {alert.alert_id}")

            except Exception as e:
                logger.error(f"发送警报到 {channel.value} 失败: {e}")
                alert.error_message = str(e)

        alert.sent_at = datetime.now()

        # 调用回调函数
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"警报回调执行失败: {e}")

    async def _send_to_channel(self, alert: Alert, channel: AlertChannel) -> bool:
        """发送到指定渠道"""
        if channel == AlertChannel.EMAIL:
            return await self._send_email(alert)
        elif channel == AlertChannel.WECHAT:
            return await self._send_wechat(alert)
        elif channel == AlertChannel.DINGTALK:
            return await self._send_dingtalk(alert)
        elif channel == AlertChannel.WEBHOOK:
            return await self._send_webhook(alert)
        else:
            logger.warning(f"不支持的警报渠道: {channel.value}")
            return False

    async def _send_email(self, alert: Alert) -> bool:
        """发送邮件警报"""
        try:
            if not self.email_config:
                logger.warning("邮件配置未设置")
                return False

            rule = self.rules.get(alert.rule_id)
            event = alert.event

            # 构建邮件内容
            subject = f"[CherryQuant警报] {rule.name}"

            html_content = f"""
            <html>
            <body>
                <h2>🚨 CherryQuant AI交易系统警报</h2>
                <table border="1" style="border-collapse: collapse; padding: 10px;">
                    <tr><td><b>警报名称</b></td><td>{rule.name}</td></tr>
                    <tr><td><b>事件类型</b></td><td>{event.event_type.value}</td></tr>
                    <tr><td><b>严重程度</b></td><td>{event.severity.value.upper()}</td></tr>
                    <tr><td><b>描述</b></td><td>{event.description}</td></tr>
                    <tr><td><b>当前值</b></td><td>{event.current_value:.4f}</td></tr>
                    <tr><td><b>阈值</b></td><td>{event.threshold_value:.4f}</td></tr>
                    <tr><td><b>建议行动</b></td><td>{event.action_taken}</td></tr>
                    <tr><td><b>时间</b></td><td>{event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                </table>
                <p>请及时处理相关风险事件。</p>
                <p>此邮件由CherryQuant系统自动发送，请勿回复。</p>
            </body>
            </html>
            """

            # 发送邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_config['sender']
            msg['To'] = ', '.join(self.email_config['recipients'])

            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            # SMTP发送
            with smtplib.SMTP(
                self.email_config['smtp_server'],
                self.email_config['smtp_port']
            ) as server:
                server.starttls()
                server.login(
                    self.email_config['username'],
                    self.email_config['password']
                )
                server.send_message(msg)

            return True

        except Exception as e:
            logger.error(f"发送邮件警报失败: {e}")
            return False

    async def _send_wechat(self, alert: Alert) -> bool:
        """发送微信警报"""
        try:
            if not self.wechat_config:
                logger.warning("微信配置未设置")
                return False

            rule = self.rules.get(alert.rule_id)
            event = alert.event

            # 构建微信消息
            message = f"""
🚨 CherryQuant警报

警报名称: {rule.name}
事件类型: {event.event_type.value}
严重程度: {event.severity.value.upper()}
描述: {event.description}
当前值: {event.current_value:.4f}
阈值: {event.threshold_value:.4f}
建议行动: {event.action_taken}
时间: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            """

            # 企业微信API调用
            webhook_url = self.wechat_config['webhook_url']
            data = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }

            async with self.session.post(webhook_url, json=data) as response:
                return response.status == 200

        except Exception as e:
            logger.error(f"发送微信警报失败: {e}")
            return False

    async def _send_dingtalk(self, alert: Alert) -> bool:
        """发送钉钉警报"""
        try:
            if not self.dingtalk_config:
                logger.warning("钉钉配置未设置")
                return False

            rule = self.rules.get(alert.rule_id)
            event = alert.event

            # 构建钉钉消息
            message = f"""
🚨 CherryQuant AI交易系统警报

**警报名称**: {rule.name}
**事件类型**: {event.event_type.value}
**严重程度**: {event.severity.value.upper()}
**描述**: {event.description}
**当前值**: {event.current_value:.4f}
**阈值**: {event.threshold_value:.4f}
**建议行动**: {event.action_taken}
**时间**: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            """

            # 钉钉机器人API调用
            webhook_url = self.dingtalk_config['webhook_url']
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"CherryQuant警报 - {rule.name}",
                    "text": message
                }
            }

            async with self.session.post(webhook_url, json=data) as response:
                result = await response.json()
                return result.get('errcode') == 0

        except Exception as e:
            logger.error(f"发送钉钉警报失败: {e}")
            return False

    async def _send_webhook(self, alert: Alert) -> bool:
        """发送Webhook警报"""
        try:
            if not self.webhook_config:
                logger.warning("Webhook配置未设置")
                return False

            webhook_url = self.webhook_config['url']

            # 构建Webhook数据
            data = {
                "alert_id": alert.alert_id,
                "rule_id": alert.rule_id,
                "event": {
                    "event_type": alert.event.event_type.value,
                    "severity": alert.event.severity.value,
                    "description": alert.event.description,
                    "current_value": alert.event.current_value,
                    "threshold_value": alert.event.threshold_value,
                    "action_taken": alert.event.action_taken,
                    "timestamp": alert.event.timestamp.isoformat(),
                    "strategy_id": alert.event.strategy_id
                },
                "alert": {
                    "status": alert.status.value,
                    "created_at": alert.created_at.isoformat(),
                    "channels_sent": [ch.value for ch in alert.channels_sent]
                }
            }

            # 添加自定义头部
            headers = self.webhook_config.get('headers', {})

            async with self.session.post(webhook_url, json=data, headers=headers) as response:
                return response.status == 200

        except Exception as e:
            logger.error(f"发送Webhook警报失败: {e}")
            return False

    def add_rule(self, rule: AlertRule) -> None:
        """添加警报规则"""
        self.rules[rule.rule_id] = rule
        logger.info(f"添加警报规则: {rule.rule_id}")

    def remove_rule(self, rule_id: str) -> bool:
        """移除警报规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"移除警报规则: {rule_id}")
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """启用警报规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """禁用警报规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            return True
        return False

    async def resolve_alert(self, alert_id: str, resolution_note: str = "") -> bool:
        """解决警报"""
        if alert_id not in self.active_alerts:
            return False

        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.updated_at = datetime.now()

        # 从活跃警报中移除
        del self.active_alerts[alert_id]

        logger.info(f"警报已解决: {alert_id} - {resolution_note}")
        return True

    def get_active_alerts(self) -> List[Alert]:
        """获取活跃警报"""
        return list(self.active_alerts.values())

    def get_alert_history(
        self,
        hours: int = 24,
        severity: Optional[RiskLevel] = None,
        event_type: Optional[RiskEventType] = None
    ) -> List[Alert]:
        """获取警报历史"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        filtered_alerts = [
            alert for alert in self.alert_history
            if alert.created_at >= cutoff_time
        ]

        if severity:
            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert.event.severity == severity
            ]

        if event_type:
            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert.event.event_type == event_type
            ]

        return sorted(filtered_alerts, key=lambda x: x.created_at, reverse=True)

    def get_alert_statistics(self, days: int = 7) -> Dict[str, Any]:
        """获取警报统计"""
        cutoff_time = datetime.now() - timedelta(days=days)

        recent_alerts = [
            alert for alert in self.alert_history
            if alert.created_at >= cutoff_time
        ]

        # 按严重程度统计
        by_severity = {}
        for alert in recent_alerts:
            severity = alert.event.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

        # 按事件类型统计
        by_event_type = {}
        for alert in recent_alerts:
            event_type = alert.event.event_type.value
            by_event_type[event_type] = by_event_type.get(event_type, 0) + 1

        # 按规则统计
        by_rule = {}
        for alert in recent_alerts:
            rule_name = self.rules.get(alert.rule_id, {}).name or alert.rule_id
            by_rule[rule_name] = by_rule.get(rule_name, 0) + 1

        # 渠道发送统计
        channel_stats = {}
        for alert in recent_alerts:
            for channel in alert.channels_sent:
                channel_name = channel.value
                channel_stats[channel_name] = channel_stats.get(channel_name, 0) + 1

        return {
            "total_alerts": len(recent_alerts),
            "active_alerts": len(self.active_alerts),
            "by_severity": by_severity,
            "by_event_type": by_event_type,
            "by_rule": by_rule,
            "channel_stats": channel_stats,
            "average_resolution_time": self._calculate_avg_resolution_time(recent_alerts)
        }

    def _calculate_avg_resolution_time(self, alerts: List[Alert]) -> Optional[float]:
        """计算平均解决时间"""
        resolved_alerts = [
            alert for alert in alerts
            if alert.status == AlertStatus.RESOLVED
        ]

        if not resolved_alerts:
            return None

        total_time = sum(
            (alert.updated_at - alert.created_at).total_seconds() / 60
            for alert in resolved_alerts
        )

        return total_time / len(resolved_alerts)

    def register_alert_callback(self, callback: Callable) -> None:
        """注册警报回调"""
        self.alert_callbacks.append(callback)

    def test_channels(self) -> Dict[str, bool]:
        """测试所有通知渠道"""
        import uuid

        # 创建测试事件
        test_event = RiskEvent(
            event_id=str(uuid.uuid4()),
            event_type=RiskEventType.CAPITAL_USAGE_EXCEEDED,
            severity=RiskLevel.MEDIUM,
            timestamp=datetime.now(),
            strategy_id="test_strategy",
            description="这是一个测试警报",
            current_value=0.85,
            threshold_value=0.8,
            action_taken="测试行动",
            additional_data={}
        )

        # 创建测试规则
        test_rule = AlertRule(
            rule_id="test_rule",
            name="测试警报规则",
            description="用于测试通知渠道的警报规则",
            event_types=[RiskEventType.CAPITAL_USAGE_EXCEEDED],
            severity_threshold=RiskLevel.MEDIUM,
            channels=list(AlertChannel),
            cooldown_minutes=0,
            enabled=True
        )

        results = {}
        for channel in test_rule.channels:
            try:
                # 创建测试警报
                alert = Alert(
                    alert_id=str(uuid.uuid4()),
                    rule_id=test_rule.rule_id,
                    event=test_event,
                    status=AlertStatus.ACTIVE,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    channels_sent=[]
                )

                # 异步发送测试
                success = asyncio.run(self._send_to_channel(alert, channel))
                results[channel.value] = success

            except Exception as e:
                logger.error(f"测试渠道 {channel.value} 失败: {e}")
                results[channel.value] = False

        return results