"""
数据验证器

对市场数据进行完整性和合理性验证。

教学要点：
1. 数据质量检查的维度
2. 统计方法在数据验证中的应用
3. 异常检测算法
4. 业务规则验证
"""

import logging
from typing import Any
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from cherryquant.data.collectors.base_collector import MarketData, ContractInfo

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """验证级别"""
    ERROR = "error"      # 严重错误，数据不可用
    WARNING = "warning"  # 警告，数据可用但需注意
    INFO = "info"        # 信息，数据正常


@dataclass
class ValidationIssue:
    """验证问题记录"""
    level: ValidationLevel
    field: str           # 问题字段
    message: str         # 问题描述
    value: Any | None = None  # 问题值
    expected: str | None = None  # 期望值说明


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    issues: list[ValidationIssue]
    summary: dict[str, int]  # 各级别问题数量统计

    def __str__(self) -> str:
        """生成验证报告"""
        if self.is_valid:
            return "✅ 数据验证通过"

        lines = [
            "⚠️ 数据验证发现问题:",
            f"  - 错误: {self.summary.get('error', 0)} 个",
            f"  - 警告: {self.summary.get('warning', 0)} 个",
            f"  - 信息: {self.summary.get('info', 0)} 个",
        ]
        return "\n".join(lines)


class DataValidator:
    """
    数据验证器

    提供多层次的数据质量检查：
    1. 完整性检查：必填字段、数据格式
    2. 合理性检查：数值范围、业务规则
    3. 一致性检查：OHLC 关系、时间序列连续性
    4. 异常值检测：统计方法识别离群点

    教学要点：
    1. 分层验证策略
    2. 可配置的验证规则
    3. 详细的错误报告
    """

    def __init__(
        self,
        strict_mode: bool = False,
        enable_statistical_checks: bool = True,
    ):
        """
        初始化验证器

        Args:
            strict_mode: 严格模式（任何警告都视为错误）
            enable_statistical_checks: 是否启用统计检查（可能较慢）
        """
        self.strict_mode = strict_mode
        self.enable_statistical_checks = enable_statistical_checks

        # 验证规则配置
        self.price_tolerance = Decimal("0.2")  # 价格异常容忍度（20%）
        self.volume_min = 0  # 最小成交量
        self.volume_max = 10_000_000  # 最大成交量（合理范围）

    def validate_market_data(
        self,
        data: MarketData,
        context: list[MarketData | None] = None,
    ) -> ValidationResult:
        """
        验证单条市场数据

        Args:
            data: 要验证的数据
            context: 上下文数据（用于时间序列检查）

        Returns:
            ValidationResult: 验证结果

        教学要点：
        1. 单元数据验证vs批量验证
        2. 上下文相关的验证
        3. 验证规则的组合
        """
        issues = []

        # 1. 完整性检查
        issues.extend(self._check_completeness(data))

        # 2. 合理性检查
        issues.extend(self._check_reasonability(data))

        # 3. OHLC 一致性检查
        issues.extend(self._check_ohlc_consistency(data))

        # 4. 时间序列检查（如果有上下文）
        if context:
            issues.extend(self._check_time_series(data, context))

        # 5. 统计异常检查
        if self.enable_statistical_checks and context:
            issues.extend(self._check_statistical_outliers(data, context))

        # 汇总结果
        summary = self._summarize_issues(issues)
        is_valid = summary.get("error", 0) == 0
        if self.strict_mode:
            is_valid = is_valid and summary.get("warning", 0) == 0

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            summary=summary,
        )

    def validate_market_data_batch(
        self,
        data_list: list[MarketData],
    ) -> tuple[list[MarketData], list[MarketData], ValidationResult]:
        """
        批量验证市场数据

        Args:
            data_list: 数据列表

        Returns:
            Tuple: (有效数据列表, 无效数据列表, 整体验证结果)

        教学要点：
        1. 批量处理策略
        2. 数据分离（有效/无效）
        3. 整体质量评估
        """
        valid_data = []
        invalid_data = []
        all_issues = []

        for i, data in enumerate(data_list):
            # 使用前面的数据作为上下文
            context = data_list[max(0, i - 10):i] if i > 0 else None

            result = self.validate_market_data(data, context)
            all_issues.extend(result.issues)

            if result.is_valid:
                valid_data.append(data)
            else:
                invalid_data.append(data)

        # 整体验证结果
        summary = self._summarize_issues(all_issues)
        is_valid = len(invalid_data) == 0

        overall_result = ValidationResult(
            is_valid=is_valid,
            issues=all_issues,
            summary=summary,
        )

        logger.info(
            f"📊 批量验证完成: "
            f"有效 {len(valid_data)}/{len(data_list)}, "
            f"无效 {len(invalid_data)}/{len(data_list)}"
        )

        return valid_data, invalid_data, overall_result

    def _check_completeness(self, data: MarketData) -> list[ValidationIssue]:
        """
        检查数据完整性

        教学要点：
        1. 必填字段检查
        2. None vs 0 的区别
        3. 期货特有字段的处理
        """
        issues = []

        # 检查必填字段
        if not data.symbol:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="symbol",
                message="合约代码不能为空",
            ))

        if not data.datetime:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="datetime",
                message="时间戳不能为空",
            ))

        # 检查 OHLCV 数据
        for field in ["open", "high", "low", "close"]:
            value = getattr(data, field)
            if value is None or value <= 0:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    field=field,
                    message=f"{field} 必须为正数",
                    value=value,
                ))

        if data.volume is None or data.volume < 0:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="volume",
                message="成交量不能为负数",
                value=data.volume,
            ))

        # 期货特有字段（可选但建议有）
        if data.open_interest is None:
            issues.append(ValidationIssue(
                level=ValidationLevel.INFO,
                field="open_interest",
                message="缺少持仓量数据",
            ))

        return issues

    def _check_reasonability(self, data: MarketData) -> list[ValidationIssue]:
        """
        检查数据合理性

        教学要点：
        1. 业务规则验证
        2. 数值范围检查
        3. 异常模式识别
        """
        issues = []

        # 价格合理性
        if data.close and data.close < Decimal("0.01"):
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="close",
                message="收盘价异常低",
                value=data.close,
            ))

        if data.close and data.close > Decimal("1000000"):
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="close",
                message="收盘价异常高",
                value=data.close,
            ))

        # 成交量合理性
        if data.volume and data.volume > self.volume_max:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="volume",
                message=f"成交量超过阈值 {self.volume_max}",
                value=data.volume,
            ))

        # 持仓量不应为负
        if data.open_interest and data.open_interest < 0:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="open_interest",
                message="持仓量不能为负数",
                value=data.open_interest,
            ))

        return issues

    def _check_ohlc_consistency(self, data: MarketData) -> list[ValidationIssue]:
        """
        检查 OHLC 数据一致性

        教学要点：
        1. OHLC 的数学关系
        2. 市场数据的内在约束
        3. 浮点数比较的注意事项
        """
        issues = []

        if not all([data.open, data.high, data.low, data.close]):
            return issues

        # 最高价应该 >= 其他所有价格
        if data.high < data.open or data.high < data.close:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="high",
                message="最高价应该 >= 开盘价和收盘价",
                value=data.high,
                expected=f"max({data.open}, {data.close})",
            ))

        if data.high < data.low:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="high",
                message="最高价应该 >= 最低价",
                value=data.high,
                expected=f">= {data.low}",
            ))

        # 最低价应该 <= 其他所有价格
        if data.low > data.open or data.low > data.close:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="low",
                message="最低价应该 <= 开盘价和收盘价",
                value=data.low,
                expected=f"min({data.open}, {data.close})",
            ))

        return issues

    def _check_time_series(
        self,
        data: MarketData,
        context: list[MarketData],
    ) -> list[ValidationIssue]:
        """
        检查时间序列连续性

        教学要点：
        1. 时间序列分析基础
        2. 缺失数据检测
        3. 时间跳跃处理
        """
        issues = []

        if not context:
            return issues

        # 检查时间顺序
        last_data = context[-1]
        if data.datetime <= last_data.datetime:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="datetime",
                message="时间戳顺序错误",
                value=data.datetime,
                expected=f"> {last_data.datetime}",
            ))

        return issues

    def _check_statistical_outliers(
        self,
        data: MarketData,
        context: list[MarketData],
    ) -> list[ValidationIssue]:
        """
        统计方法检测离群值

        使用简化的 IQR (Interquartile Range) 方法检测异常值。

        教学要点：
        1. 箱线图原理
        2. IQR 异常检测
        3. 统计方法在金融数据中的应用
        """
        issues = []

        if len(context) < 10:  # 样本太少，跳过统计检查
            return issues

        # 计算收盘价的统计量
        prices = [Decimal(str(d.close)) for d in context if d.close]
        if not prices:
            return issues

        prices.sort()
        n = len(prices)

        # 计算四分位数
        q1 = prices[n // 4]
        q3 = prices[3 * n // 4]
        iqr = q3 - q1

        # 定义异常值范围
        lower_bound = q1 - Decimal("1.5") * iqr
        upper_bound = q3 + Decimal("1.5") * iqr

        # 检查当前数据是否为离群值
        if data.close < lower_bound or data.close > upper_bound:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="close",
                message="收盘价为统计离群值",
                value=data.close,
                expected=f"{lower_bound} ~ {upper_bound}",
            ))

        return issues

    def _summarize_issues(self, issues: list[ValidationIssue]) -> dict[str, int]:
        """汇总问题统计"""
        summary = {"error": 0, "warning": 0, "info": 0}

        for issue in issues:
            summary[issue.level.value] += 1

        return summary

    def validate_contract_info(self, contract: ContractInfo) -> ValidationResult:
        """
        验证合约信息

        教学要点：
        1. 元数据验证
        2. 日期逻辑检查
        3. 业务规则验证
        """
        issues = []

        # 必填字段
        if not contract.symbol:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="symbol",
                message="合约代码不能为空",
            ))

        # 日期逻辑
        if contract.expire_date < contract.list_date:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="expire_date",
                message="到期日期不能早于上市日期",
                value=contract.expire_date,
                expected=f">= {contract.list_date}",
            ))

        # 合约规格
        if contract.multiplier <= 0:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="multiplier",
                message="合约乘数必须为正数",
                value=contract.multiplier,
            ))

        if contract.price_tick <= 0:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="price_tick",
                message="最小变动价位必须为正数",
                value=contract.price_tick,
            ))

        summary = self._summarize_issues(issues)
        is_valid = summary.get("error", 0) == 0

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            summary=summary,
        )
