"""数据采集模块

提供统一的数据采集接口，支持多种数据源：
- Tushare API
- VNPy 实时数据
- QuantBox (可选)

所有采集器都继承自 BaseCollector，确保接口一致性。
"""

from cherryquant.data.collectors.base_collector import BaseCollector
from cherryquant.data.collectors.tushare_collector import TushareCollector

__all__ = [
    "BaseCollector",
    "TushareCollector",
]
