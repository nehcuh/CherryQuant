"""数据清洗模块

提供数据质量控制和标准化功能：
- 数据验证 (validator): 检测缺失值、异常值
- 数据标准化 (normalizer): 格式统一、符号转换
- 质量控制 (quality_control): 数据质量报告和监控

教学价值：
1. 数据质量的重要性
2. 防御性编程实践
3. 统计方法应用
"""

from cherryquant.data.cleaners.validator import DataValidator
from cherryquant.data.cleaners.normalizer import DataNormalizer
from cherryquant.data.cleaners.quality_control import QualityController

__all__ = [
    "DataValidator",
    "DataNormalizer",
    "QualityController",
]
