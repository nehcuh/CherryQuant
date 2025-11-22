"""
数据质量控制器

提供数据质量监控和报告功能。

教学要点：
1. 数据质量度量指标
2. 监控和报警机制
3. 质量报告生成
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from cherryquant.data.collectors.base_collector import MarketData
from cherryquant.data.cleaners.validator import DataValidator, ValidationResult

logger = logging.getLogger(__name__)


# ==================== 质量控制常量配置 ====================

# 质量评分权重
WEIGHT_COMPLETENESS = 0.3  # 完整性权重
WEIGHT_ACCURACY = 0.3      # 准确性权重
WEIGHT_CONSISTENCY = 0.2   # 一致性权重
WEIGHT_TIMELINESS = 0.2    # 及时性权重

# 质量等级阈值
GRADE_A_THRESHOLD = 0.9    # 优秀
GRADE_B_THRESHOLD = 0.8    # 良好
GRADE_C_THRESHOLD = 0.7    # 中等
GRADE_D_THRESHOLD = 0.6    # 及格

# 及时性评分标准（小时）
TIMELINESS_EXCELLENT = 1   # 1小时内得1.0分
TIMELINESS_GOOD = 24       # 1天内得0.8分
TIMELINESS_FAIR = 72       # 3天内得0.5分
TIMELINESS_SCORE_EXCELLENT = 1.0
TIMELINESS_SCORE_GOOD = 0.8
TIMELINESS_SCORE_FAIR = 0.5
TIMELINESS_SCORE_POOR = 0.2
TIMELINESS_SCORE_DEFAULT = 0.5  # 无采集时间时的默认分数


@dataclass
class QualityMetrics:
    """数据质量指标"""
    total_count: int                 # 总数据量
    valid_count: int                 # 有效数据量
    invalid_count: int               # 无效数据量
    error_count: int                 # 错误数量
    warning_count: int               # 警告数量
    completeness_rate: float         # 完整性（0-1）
    accuracy_rate: float             # 准确性（0-1）
    consistency_rate: float          # 一致性（0-1）
    timeliness_score: float          # 及时性得分（0-1）

    # 具体问题统计
    missing_fields: dict[str, int]   # 缺失字段统计
    outliers_count: int              # 离群值数量
    duplicates_count: int            # 重复数据量

    @property
    def overall_score(self) -> float:
        """综合质量得分（0-1）"""
        return (
            self.completeness_rate * WEIGHT_COMPLETENESS +
            self.accuracy_rate * WEIGHT_ACCURACY +
            self.consistency_rate * WEIGHT_CONSISTENCY +
            self.timeliness_score * WEIGHT_TIMELINESS
        )

    @property
    def quality_grade(self) -> str:
        """质量等级"""
        score = self.overall_score
        if score >= GRADE_A_THRESHOLD:
            return "优秀 (A)"
        elif score >= GRADE_B_THRESHOLD:
            return "良好 (B)"
        elif score >= GRADE_C_THRESHOLD:
            return "中等 (C)"
        elif score >= GRADE_D_THRESHOLD:
            return "及格 (D)"
        else:
            return "不及格 (F)"

    def __str__(self) -> str:
        """生成质量报告"""
        return f"""
数据质量报告
{'=' * 60}
总体情况:
  - 总数据量: {self.total_count}
  - 有效数据: {self.valid_count} ({self.valid_count / self.total_count * 100:.1f}%)
  - 无效数据: {self.invalid_count} ({self.invalid_count / self.total_count * 100:.1f}%)

问题统计:
  - 错误: {self.error_count}
  - 警告: {self.warning_count}
  - 离群值: {self.outliers_count}
  - 重复数据: {self.duplicates_count}

质量指标:
  - 完整性: {self.completeness_rate * 100:.1f}%
  - 准确性: {self.accuracy_rate * 100:.1f}%
  - 一致性: {self.consistency_rate * 100:.1f}%
  - 及时性: {self.timeliness_score * 100:.1f}%

综合得分: {self.overall_score * 100:.1f}% - {self.quality_grade}
{'=' * 60}
"""


class QualityController:
    """
    数据质量控制器

    提供数据质量监控、评估和报告功能。

    教学要点：
    1. 质量管理的维度（完整性、准确性、一致性、及时性）
    2. 指标计算方法
    3. 质量报告的设计
    """

    def __init__(
        self,
        validator: DataValidator | None = None,
        min_quality_score: float = 0.7,
    ):
        """
        初始化质量控制器

        Args:
            validator: 数据验证器（如果为None则创建默认）
            min_quality_score: 最低质量分数阈值
        """
        self.validator = validator or DataValidator()
        self.min_quality_score = min_quality_score

        # 历史记录
        self.quality_history: list[QualityMetrics] = []

    def assess_data_quality(
        self,
        data_list: list[MarketData],
    ) -> QualityMetrics:
        """
        评估数据质量

        Args:
            data_list: 要评估的数据列表

        Returns:
            QualityMetrics: 质量指标

        教学要点：
        1. 多维度质量评估
        2. 指标计算方法
        3. 质量判定标准
        """
        if not data_list:
            logger.warning("⚠️ 数据列表为空，无法评估质量")
            return self._create_empty_metrics()

        # 1. 验证数据
        valid_data, invalid_data, validation_result = (
            self.validator.validate_market_data_batch(data_list)
        )

        # 2. 计算各项指标
        total_count = len(data_list)
        valid_count = len(valid_data)
        invalid_count = len(invalid_data)

        # 完整性：有效数据比例
        completeness_rate = valid_count / total_count if total_count > 0 else 0

        # 准确性：无错误的数据比例
        error_count = validation_result.summary.get("error", 0)
        accuracy_rate = 1.0 - (error_count / total_count) if total_count > 0 else 0

        # 一致性：无警告的数据比例
        warning_count = validation_result.summary.get("warning", 0)
        consistency_rate = 1.0 - (warning_count / total_count) if total_count > 0 else 0

        # 及时性：基于数据时间戳
        timeliness_score = self._calculate_timeliness(data_list)

        # 缺失字段统计
        missing_fields = self._count_missing_fields(data_list)

        # 离群值数量（从验证结果中提取）
        outliers_count = sum(
            1 for issue in validation_result.issues
            if "离群值" in issue.message or "异常" in issue.message
        )

        # 重复数据统计
        duplicates_count = self._count_duplicates(data_list)

        metrics = QualityMetrics(
            total_count=total_count,
            valid_count=valid_count,
            invalid_count=invalid_count,
            error_count=error_count,
            warning_count=warning_count,
            completeness_rate=completeness_rate,
            accuracy_rate=accuracy_rate,
            consistency_rate=consistency_rate,
            timeliness_score=timeliness_score,
            missing_fields=missing_fields,
            outliers_count=outliers_count,
            duplicates_count=duplicates_count,
        )

        # 记录历史
        self.quality_history.append(metrics)

        # 日志输出
        logger.info(f"📊 数据质量评估完成: {metrics.quality_grade}")
        if metrics.overall_score < self.min_quality_score:
            logger.warning(
                f"⚠️ 数据质量低于阈值 "
                f"({metrics.overall_score:.2f} < {self.min_quality_score})"
            )

        return metrics

    def _calculate_timeliness(self, data_list: list[MarketData]) -> float:
        """
        计算数据及时性得分

        教学要点：
        1. 及时性的定义
        2. 时间衰减函数
        3. 实时数据 vs 历史数据的区别
        """
        if not data_list:
            return 0.0

        now = datetime.now()
        scores = []

        for data in data_list:
            if not data.collected_at:
                # 如果没有采集时间，使用默认分数
                scores.append(TIMELINESS_SCORE_DEFAULT)
                continue

            # 计算数据延迟（采集时间 - 数据时间）
            delay = (data.collected_at - data.datetime).total_seconds()

            # 时效性得分：延迟越小，得分越高
            # 使用指数衰减函数
            if delay < TIMELINESS_EXCELLENT * 3600:  # 1小时
                score = TIMELINESS_SCORE_EXCELLENT
            elif delay < TIMELINESS_GOOD * 3600:  # 1天
                score = TIMELINESS_SCORE_GOOD
            elif delay < TIMELINESS_FAIR * 3600:  # 3天
                score = TIMELINESS_SCORE_FAIR
            else:
                score = TIMELINESS_SCORE_POOR

            scores.append(score)

        return sum(scores) / len(scores) if scores else 0.0

    def _count_missing_fields(
        self,
        data_list: list[MarketData],
    ) -> dict[str, int]:
        """统计缺失字段"""
        missing_counts = {
            "open_interest": 0,
            "turnover": 0,
            "collected_at": 0,
        }

        for data in data_list:
            if data.open_interest is None:
                missing_counts["open_interest"] += 1
            if data.turnover is None:
                missing_counts["turnover"] += 1
            if data.collected_at is None:
                missing_counts["collected_at"] += 1

        return missing_counts

    def _count_duplicates(self, data_list: list[MarketData]) -> int:
        """统计重复数据"""
        seen = set()
        duplicates = 0

        for data in data_list:
            key = (
                data.symbol,
                data.exchange.value,
                data.datetime,
                data.timeframe.value,
            )

            if key in seen:
                duplicates += 1
            else:
                seen.add(key)

        return duplicates

    def _create_empty_metrics(self) -> QualityMetrics:
        """创建空的质量指标"""
        return QualityMetrics(
            total_count=0,
            valid_count=0,
            invalid_count=0,
            error_count=0,
            warning_count=0,
            completeness_rate=0.0,
            accuracy_rate=0.0,
            consistency_rate=0.0,
            timeliness_score=0.0,
            missing_fields={},
            outliers_count=0,
            duplicates_count=0,
        )

    def generate_quality_report(
        self,
        metrics: QualityMetrics,
        output_file: str | None = None,
    ) -> str:
        """
        生成质量报告

        Args:
            metrics: 质量指标
            output_file: 输出文件路径（可选）

        Returns:
            str: 报告内容

        教学要点：
        1. 报告格式设计
        2. 可视化表示
        3. 文件输出
        """
        report = str(metrics)

        # 添加详细的缺失字段信息
        if metrics.missing_fields:
            report += "\n缺失字段详情:\n"
            for field, count in metrics.missing_fields.items():
                rate = count / metrics.total_count * 100 if metrics.total_count > 0 else 0
                report += f"  - {field}: {count} ({rate:.1f}%)\n"

        # 添加建议
        report += "\n改进建议:\n"
        if metrics.completeness_rate < 0.9:
            report += "  - 提高数据完整性：检查数据采集流程\n"
        if metrics.accuracy_rate < 0.9:
            report += "  - 提高数据准确性：加强数据验证\n"
        if metrics.consistency_rate < 0.9:
            report += "  - 提高数据一致性：检查 OHLC 关系\n"
        if metrics.timeliness_score < 0.8:
            report += "  - 提高数据及时性：优化采集频率\n"
        if metrics.duplicates_count > 0:
            report += "  - 去除重复数据：启用去重机制\n"

        # 输出到文件
        if output_file:
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(report)
                logger.info(f"✅ 质量报告已保存到: {output_file}")
            except Exception as e:
                logger.error(f"❌ 保存报告失败: {e}")

        return report

    def get_quality_trend(self, last_n: int = 10) -> list[float]:
        """
        获取质量趋势

        Args:
            last_n: 最近N次评估

        Returns:
            list[float]: 质量得分列表

        教学要点：
        1. 时间序列分析
        2. 趋势识别
        3. 历史数据利用
        """
        if not self.quality_history:
            return []

        recent = self.quality_history[-last_n:]
        return [m.overall_score for m in recent]

    def is_quality_degrading(self, window: int = 5) -> bool:
        """
        判断质量是否在下降

        Args:
            window: 观察窗口大小

        Returns:
            bool: 质量是否在下降

        教学要点：
        1. 趋势检测算法
        2. 早期预警机制
        """
        trend = self.get_quality_trend(window)

        if len(trend) < 2:
            return False

        # 简单的线性回归判断趋势
        # 如果后半部分均值 < 前半部分均值，认为在下降
        mid = len(trend) // 2
        first_half = sum(trend[:mid]) / mid if mid > 0 else 0
        second_half = sum(trend[mid:]) / (len(trend) - mid) if len(trend) > mid else 0

        return second_half < first_half * 0.95  # 下降超过5%
