"""
交易所代码标准化管理模块 (Exchange Code Utilities)

本模块提供统一的交易所代码处理工具函数，整合自quantbox项目的优秀设计。

核心功能：
1. 交易所代码标准化和验证
2. 不同数据源的交易所代码映射（Tushare、GoldMiner、VNPy）
3. 交易所类型判断（股票、期货等）
4. 批量处理和验证

教学要点：
1. 如何设计可扩展的枚举系统
2. 多数据源格式映射的最佳实践
3. 别名管理策略
4. 配置驱动开发
5. 数据验证的层次化设计

代码风格：Python 3.12+ with type hints
"""

from __future__ import annotations

from typing import Optional, Union, List, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ==================== 枚举定义 ====================

class ExchangeType(Enum):
    """
    交易所类型枚举

    教学要点：
    - 使用枚举管理有限选项
    - 字符串枚举的便利性（可直接比较和打印）
    """
    STOCK = "stock"      # 股票交易所
    FUTURES = "futures"  # 期货交易所
    OPTIONS = "options"  # 期权交易所（预留）


# ==================== 交易所代码定义 ====================

# 标准交易所代码（内部统一格式，MongoDB存储格式）
# 教学要点：配置即文档 - 通过数据结构展示业务规则
STANDARD_EXCHANGES = {
    # 股票交易所
    "SHSE": {
        "name": "上海证券交易所",
        "type": ExchangeType.STOCK,
        "aliases": ["SSE", "SH"]
    },
    "SZSE": {
        "name": "深圳证券交易所",
        "type": ExchangeType.STOCK,
        "aliases": ["SZ"]
    },
    "BSE": {
        "name": "北京证券交易所",
        "type": ExchangeType.STOCK,
        "aliases": ["BJ"]
    },
    # 期货交易所
    "SHFE": {
        "name": "上海期货交易所",
        "type": ExchangeType.FUTURES,
        "aliases": ["SHF"]
    },
    "DCE": {
        "name": "大连商品交易所",
        "type": ExchangeType.FUTURES,
        "aliases": []
    },
    "CZCE": {
        "name": "郑州商品交易所",
        "type": ExchangeType.FUTURES,
        "aliases": ["ZCE"]
    },
    "CFFEX": {
        "name": "中国金融期货交易所",
        "type": ExchangeType.FUTURES,
        "aliases": []
    },
    "INE": {
        "name": "上海国际能源交易中心",
        "type": ExchangeType.FUTURES,
        "aliases": []
    },
    "GFEX": {
        "name": "广州期货交易所",
        "type": ExchangeType.FUTURES,
        "aliases": []
    },
}


# ==================== 预计算的映射表 ====================
# 教学要点：预计算优化 - 启动时一次性计算，运行时直接查表

# 构建完整的交易所代码集合（包括别名）
VALID_EXCHANGES: Set[str] = set(STANDARD_EXCHANGES.keys())
for standard_code, info in STANDARD_EXCHANGES.items():
    VALID_EXCHANGES.update(info["aliases"])

# 别名到标准代码的映射
# 教学要点：反向索引 - 加速查找
ALIAS_TO_STANDARD: dict[str, str] = {}
for standard_code, info in STANDARD_EXCHANGES.items():
    for alias in info["aliases"]:
        ALIAS_TO_STANDARD[alias] = standard_code

# 股票交易所列表
STOCK_EXCHANGES: list[str] = [
    code for code, info in STANDARD_EXCHANGES.items()
    if info["type"] == ExchangeType.STOCK
]

# 期货交易所列表
FUTURES_EXCHANGES: list[str] = [
    code for code, info in STANDARD_EXCHANGES.items()
    if info["type"] == ExchangeType.FUTURES
]

# 所有交易所列表
ALL_EXCHANGES: list[str] = list(STANDARD_EXCHANGES.keys())


# ==================== 核心转换函数 ====================

def normalize_exchange(exchange: str) -> str:
    """
    将交易所代码标准化为内部统一格式

    教学要点：
    1. 统一数据入口的重要性
    2. 别名映射的实现方式
    3. 清晰的错误提示
    4. 大小写无关的用户友好设计

    设计思想：
    - 接受多种输入格式（标准代码和别名）
    - 统一转换为内部标准格式
    - 保证数据一致性

    支持的输入：
    - 标准代码：SHSE, SZSE, SHFE, DCE, CZCE, CFFEX, INE, BSE, GFEX
    - 别名：SSE -> SHSE, SH -> SHSE, SHF -> SHFE, ZCE -> CZCE

    Args:
        exchange: 交易所代码（标准或别名，大小写不敏感）

    Returns:
        str: 标准化的交易所代码

    Raises:
        ValueError: 交易所代码无效或为空

    Examples:
        >>> normalize_exchange("SSE")
        'SHSE'
        >>> normalize_exchange("shse")  # 大小写不敏感
        'SHSE'
        >>> normalize_exchange("SHF")
        'SHFE'
        >>> normalize_exchange("invalid")
        Traceback (most recent call last):
        ...
        ValueError: Invalid exchange code: 'INVALID'...
    """
    if not exchange or not exchange.strip():
        raise ValueError("交易所代码不能为空")

    # 教学要点：输入预处理（去空格、统一大小写）
    exchange = exchange.strip().upper()

    # 验证代码是否有效
    if exchange not in VALID_EXCHANGES:
        raise ValueError(
            f"无效的交易所代码: '{exchange}'. "
            f"有效代码: {', '.join(sorted(ALL_EXCHANGES))}"
        )

    # 如果是别名，转换为标准代码
    # 教学要点：dict.get的第二参数作为默认值
    return ALIAS_TO_STANDARD.get(exchange, exchange)


def denormalize_exchange(exchange: str, target: str = "tushare") -> str:
    """
    将标准交易所代码转换为特定数据源的格式

    教学要点：
    1. 多数据源适配策略
    2. Tushare的特殊处理（股票使用简称，期货使用标准代码）
    3. 可扩展的设计模式（易于添加新数据源）

    设计背景：
    - 不同数据源使用不同的交易所代码格式
    - 需要在内部标准格式和外部格式之间转换
    - Tushare特别复杂：股票和期货使用不同规则

    数据源映射规则：
    - Tushare股票: SHSE->SH, SZSE->SZ, BSE->BJ
    - Tushare期货: 使用标准代码 (SHFE, DCE, CZCE, CFFEX, INE, GFEX)
    - GoldMiner: 使用标准代码
    - VNPy: 使用标准代码

    Args:
        exchange: 标准化的交易所代码
        target: 目标数据源（"tushare", "goldminer", "vnpy"）

    Returns:
        str: 转换后的交易所代码

    Raises:
        ValueError: 交易所代码无效或目标数据源不支持

    Examples:
        >>> denormalize_exchange("SHSE", "tushare")
        'SH'  # 股票使用简称
        >>> denormalize_exchange("SHFE", "tushare")
        'SHFE'  # 期货使用标准代码
        >>> denormalize_exchange("SHFE", "vnpy")
        'SHFE'
    """
    if not exchange:
        raise ValueError("交易所代码不能为空")

    exchange = exchange.strip().upper()

    # 验证是否为标准代码
    if exchange not in STANDARD_EXCHANGES:
        raise ValueError(
            f"无效的标准交易所代码: '{exchange}'. "
            f"有效代码: {', '.join(sorted(ALL_EXCHANGES))}"
        )

    # 根据目标数据源转换
    # 教学要点：策略模式的简化实现
    if target.lower() == "tushare":
        # Tushare特殊映射
        # 教学要点：Tushare有两套交易所代码体系的复杂性
        # 1. API入参（exchange参数）：使用标准代码（期货）或简称（股票）
        # 2. API返回值（ts_code后缀）：使用简称（SHF、ZCE、CFX）
        # 本函数用于生成API入参
        tushare_mapping = {
            # 股票交易所：使用简称
            "SHSE": "SH",
            "SZSE": "SZ",
            "BSE": "BJ",
            # 期货交易所：使用标准代码
            "SHFE": "SHFE",
            "CZCE": "CZCE",
            "DCE": "DCE",
            "CFFEX": "CFFEX",
            "INE": "INE",
            "GFEX": "GFEX",
        }
        return tushare_mapping.get(exchange, exchange)

    elif target.lower() == "goldminer":
        # 掘金：使用标准代码
        return exchange

    elif target.lower() == "vnpy":
        # VNPy：使用标准代码
        return exchange

    else:
        raise ValueError(
            f"不支持的目标数据源: '{target}'. "
            f"支持的数据源: 'tushare', 'goldminer', 'vnpy'"
        )


# ==================== 验证函数 ====================

def validate_exchange(exchange: str) -> str:
    """
    验证单个交易所代码并返回标准格式

    这是normalize_exchange的别名，提供更语义化的函数名。

    教学要点：
    - 函数别名的应用
    - 提供多个入口满足不同使用习惯

    Args:
        exchange: 交易所代码

    Returns:
        str: 标准化的交易所代码

    Raises:
        ValueError: 交易所代码无效
    """
    return normalize_exchange(exchange)


def validate_exchanges(
    exchanges: Optional[Union[str, list[str]]] = None,
    default_type: str = "all"
) -> list[str]:
    """
    验证并标准化交易所代码列表

    教学要点：
    1. 灵活的参数设计（支持None、str、list）
    2. 智能的默认值处理
    3. 自动去重保持顺序
    4. 字符串分割处理（支持逗号分隔）

    应用场景：
    - API参数验证
    - 批量处理准备
    - 配置文件解析

    Args:
        exchanges: 交易所代码或代码列表
                  - None: 使用默认值（根据default_type）
                  - str: 单个交易所代码或逗号分隔的多个代码
                  - list[str]: 交易所代码列表
        default_type: 当exchanges为None时使用的默认类型
                     - "all": 所有交易所
                     - "stock": 股票交易所
                     - "futures": 期货交易所

    Returns:
        list[str]: 标准化后的交易所代码列表（已去重）

    Raises:
        ValueError: 任何交易所代码无效或default_type无效

    Examples:
        >>> validate_exchanges("SSE")
        ['SHSE']
        >>> validate_exchanges(["SSE", "SZSE"])
        ['SHSE', 'SZSE']
        >>> validate_exchanges("SSE,SZSE")  # 支持逗号分隔
        ['SHSE', 'SZSE']
        >>> validate_exchanges(None, "stock")
        ['SHSE', 'SZSE', 'BSE']
        >>> validate_exchanges(["SSE", "SSE", "SH"])  # 自动去重
        ['SHSE']
    """
    if exchanges is None:
        # 使用默认值
        # 教学要点：默认值的合理选择
        if default_type == "all":
            return ALL_EXCHANGES.copy()
        elif default_type == "stock":
            return STOCK_EXCHANGES.copy()
        elif default_type == "futures":
            return FUTURES_EXCHANGES.copy()
        else:
            raise ValueError(
                f"无效的default_type: '{default_type}'. "
                f"有效类型: 'all', 'stock', 'futures'"
            )

    # 处理字符串输入（可能包含逗号分隔）
    # 教学要点：用户友好的输入处理
    if isinstance(exchanges, str):
        if "," in exchanges:
            exchanges = [e.strip() for e in exchanges.split(",")]
        else:
            exchanges = [exchanges]

    # 验证并标准化每个交易所代码
    result = []
    for exchange in exchanges:
        if exchange and exchange.strip():  # 跳过空字符串
            result.append(normalize_exchange(exchange))

    # 去重并保持顺序
    # 教学要点：保持顺序的去重算法
    seen = set()
    unique_result = []
    for exchange in result:
        if exchange not in seen:
            seen.add(exchange)
            unique_result.append(exchange)

    return unique_result


# ==================== 类型判断函数 ====================

def is_stock_exchange(exchange: str) -> bool:
    """
    判断是否为股票交易所

    教学要点：
    - 封装业务逻辑
    - 类型检查的实现

    Args:
        exchange: 交易所代码（标准或别名）

    Returns:
        bool: 是否为股票交易所

    Examples:
        >>> is_stock_exchange("SHSE")
        True
        >>> is_stock_exchange("SSE")  # 别名也支持
        True
        >>> is_stock_exchange("SHFE")
        False
    """
    standard_code = normalize_exchange(exchange)
    return STANDARD_EXCHANGES[standard_code]["type"] == ExchangeType.STOCK


def is_futures_exchange(exchange: str) -> bool:
    """
    判断是否为期货交易所

    Args:
        exchange: 交易所代码（标准或别名）

    Returns:
        bool: 是否为期货交易所

    Examples:
        >>> is_futures_exchange("SHFE")
        True
        >>> is_futures_exchange("SHF")  # 别名也支持
        True
        >>> is_futures_exchange("SHSE")
        False
    """
    standard_code = normalize_exchange(exchange)
    return STANDARD_EXCHANGES[standard_code]["type"] == ExchangeType.FUTURES


# ==================== 信息查询函数 ====================

def get_exchange_info(exchange: str) -> dict[str, any]:
    """
    获取交易所的详细信息

    教学要点：
    - 信息查询API设计
    - 数据封装
    - 防御性复制（copy()）

    Args:
        exchange: 交易所代码（标准或别名）

    Returns:
        dict: 交易所信息，包含以下字段：
            - code: 标准代码
            - name: 中文名称
            - type: 交易所类型（"stock"或"futures"）
            - aliases: 别名列表

    Raises:
        ValueError: 交易所代码无效

    Examples:
        >>> info = get_exchange_info("SSE")
        >>> info["code"]
        'SHSE'
        >>> info["name"]
        '上海证券交易所'
        >>> info["type"]
        'stock'
    """
    standard_code = normalize_exchange(exchange)
    exchange_data = STANDARD_EXCHANGES[standard_code]

    return {
        "code": standard_code,
        "name": exchange_data["name"],
        "type": exchange_data["type"].value,  # Enum转字符串
        "aliases": exchange_data["aliases"].copy()  # 防御性复制
    }


def get_all_exchanges(exchange_type: Optional[str] = None) -> list[str]:
    """
    获取所有交易所代码列表

    教学要点：
    - 列表查询API
    - 类型过滤

    Args:
        exchange_type: 交易所类型过滤
                      - None: 返回所有交易所
                      - "stock": 只返回股票交易所
                      - "futures": 只返回期货交易所

    Returns:
        list[str]: 交易所代码列表

    Examples:
        >>> len(get_all_exchanges())
        9
        >>> len(get_all_exchanges("stock"))
        3
        >>> len(get_all_exchanges("futures"))
        6
    """
    if exchange_type is None:
        return ALL_EXCHANGES.copy()
    elif exchange_type == "stock":
        return STOCK_EXCHANGES.copy()
    elif exchange_type == "futures":
        return FUTURES_EXCHANGES.copy()
    else:
        raise ValueError(
            f"无效的exchange_type: '{exchange_type}'. "
            f"有效类型: None, 'stock', 'futures'"
        )


# ==================== 模块使用示例 ====================

if __name__ == "__main__":
    # 基础使用示例
    print("=" * 60)
    print("CherryQuant 交易所代码管理模块示例")
    print("=" * 60)

    # 1. 代码标准化
    print("\n1. 交易所代码标准化:")
    print(f"  normalize_exchange('SSE') = {normalize_exchange('SSE')}")
    print(f"  normalize_exchange('SHF') = {normalize_exchange('SHF')}")

    # 2. 数据源转换
    print("\n2. 数据源格式转换:")
    print(f"  SHSE -> Tushare: {denormalize_exchange('SHSE', 'tushare')}")
    print(f"  SHFE -> Tushare: {denormalize_exchange('SHFE', 'tushare')}")

    # 3. 批量验证
    print("\n3. 批量验证:")
    result = validate_exchanges("SSE,SHF,DCE")
    print(f"  validate_exchanges('SSE,SHF,DCE') = {result}")

    # 4. 类型判断
    print("\n4. 类型判断:")
    print(f"  is_stock_exchange('SHSE') = {is_stock_exchange('SHSE')}")
    print(f"  is_futures_exchange('SHFE') = {is_futures_exchange('SHFE')}")

    # 5. 信息查询
    print("\n5. 交易所信息:")
    info = get_exchange_info("SSE")
    print(f"  {info['code']}: {info['name']} ({info['type']})")

    print("\n" + "=" * 60)
