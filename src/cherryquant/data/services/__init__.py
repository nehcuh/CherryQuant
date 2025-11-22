"""数据服务层

提供高层次的业务逻辑封装：
- 交易日历服务 (calendar_service): 交易日历管理
- 合约管理服务 (contract_service): 期货合约元数据管理
- 市场数据服务 (market_data_service): 市场数据采集和查询

教学价值：
1. 服务层的职责划分
2. 业务逻辑封装
3. 依赖注入和组合
"""

from cherryquant.data.services.calendar_service import CalendarService
from cherryquant.data.services.contract_service import ContractService

__all__ = [
    "CalendarService",
    "ContractService",
]
