"""
交易日期处理工具模块 (Trading Date Utilities)

本模块提供统一的日期处理工具函数，整合自quantbox项目的优秀设计。

核心功能：
1. 日期格式转换（字符串、整数、datetime对象互转）
2. 时间戳转换
3. 交易日查询和计算（基于MongoDB）
4. 性能优化（LRU缓存）

教学要点：
1. 如何设计统一的日期类型系统
2. 多格式日期转换的最佳实践
3. 交易日历查询的性能优化（LRU缓存）
4. MongoDB查询优化技巧
5. 函数式编程与缓存装饰器

代码风格：Python 3.12+ with type hints
"""

from __future__ import annotations

import datetime
from typing import Union, Optional, List, Any
from functools import lru_cache
import logging

# 导入CherryQuant的数据库管理器
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager

logger = logging.getLogger(__name__)

# ==================== 类型别名 ====================

# 统一的日期类型别名，提高代码可读性和类型安全
# 教学要点：使用类型别名简化复杂类型定义
DateLike = Union[str, int, datetime.date, datetime.datetime, None]


# ==================== 数据库连接辅助函数 ====================

def _get_database():
    """
    获取MongoDB数据库连接

    教学要点：
    - 单例模式的应用（MongoDBConnectionManager）
    - 延迟初始化（lazy initialization）
    - 资源管理的最佳实践

    Returns:
        Database: MongoDB数据库连接
    """
    try:
        manager = MongoDBConnectionManager.get_instance()
        if not manager:
            raise RuntimeError("MongoDB连接管理器未初始化")
        return manager.get_database()
    except Exception as e:
        logger.error(f"获取MongoDB连接失败: {e}")
        raise


# ==================== 日期格式转换函数 ====================

def date_to_int(date: DateLike) -> int:
    """
    将多种日期格式统一转换为整数格式 (YYYYMMDD)

    教学要点：
    1. 统一输入接口设计（多类型支持）
    2. 类型检查与分支处理
    3. 数据验证的重要性
    4. 友好的错误提示

    设计思想：
    - 接受多种输入格式，减少调用方的转换负担
    - 使用整数格式存储日期，节省空间并加速查询
    - 严格的格式验证，避免垃圾数据入库

    支持格式：
    - None: 返回今天
    - int: 20240126（8位整数）
    - str: "2024-01-26" 或 "20240126" 或 "2024/01/26"
    - datetime.date: date对象
    - datetime.datetime: datetime对象

    Args:
        date: 需要转换的日期

    Returns:
        int: 整数格式的日期（YYYYMMDD）

    Raises:
        ValueError: 日期格式无效或日期值不合法

    Examples:
        >>> date_to_int("2024-01-26")
        20240126
        >>> date_to_int(20240126)
        20240126
        >>> date_to_int(datetime.date(2024, 1, 26))
        20240126
        >>> date_to_int(None)
        20250122  # 今天的日期
    """
    # 处理None：默认为今天
    if date is None:
        return int(datetime.date.today().strftime('%Y%m%d'))

    # 处理整数类型（最常见，优先处理）
    if isinstance(date, int):
        date_str = str(date)
        if len(date_str) != 8:
            raise ValueError(
                f"整数日期必须是8位数字（YYYYMMDD），实际长度: {len(date_str)}"
            )
        # 验证日期有效性（会抛出ValueError如果无效）
        try:
            datetime.datetime.strptime(date_str, '%Y%m%d')
        except ValueError as e:
            raise ValueError(f"无效的日期整数 '{date}': {str(e)}") from e
        return date

    # 处理datetime对象
    if isinstance(date, datetime.datetime):
        return int(date.strftime('%Y%m%d'))

    # 处理date对象
    if isinstance(date, datetime.date):
        return int(date.strftime('%Y%m%d'))

    # 处理字符串类型
    if isinstance(date, str):
        # 移除所有常见的分隔符（支持多种格式）
        # 教学要点：灵活的字符串处理
        date_str = date.replace('-', '').replace('/', '').replace('.', '').strip()

        if len(date_str) != 8:
            raise ValueError(
                f"日期字符串去除分隔符后必须是8位数字，输入: '{date}'"
            )

        # 验证日期有效性
        try:
            datetime.datetime.strptime(date_str, '%Y%m%d')
            return int(date_str)
        except ValueError as e:
            raise ValueError(f"无效的日期字符串 '{date}': {str(e)}") from e

    # 未知类型
    raise ValueError(f"不支持的日期类型: {type(date).__name__}")


def int_to_date_str(date_int: int) -> str:
    """
    将整数格式日期转换为字符串格式 (YYYY-MM-DD)

    教学要点：
    - 反向转换函数设计
    - 格式化输出
    - 类型转换的对称性

    Args:
        date_int: 整数格式的日期，如 20240126

    Returns:
        str: 字符串格式的日期，如 '2024-01-26'

    Raises:
        ValueError: 日期格式无效

    Examples:
        >>> int_to_date_str(20240126)
        '2024-01-26'
    """
    date_str = str(date_int)
    if len(date_str) != 8:
        raise ValueError(f"日期整数必须是8位数字，实际: {len(date_str)}")

    # 验证日期有效性并转换
    try:
        dt = datetime.datetime.strptime(date_str, '%Y%m%d')
        return dt.strftime('%Y-%m-%d')
    except ValueError as e:
        raise ValueError(f"无效的日期整数 '{date_int}': {str(e)}") from e


def date_to_str(date: DateLike, format: str = "%Y-%m-%d") -> str:
    """
    将日期转换为指定格式的字符串

    教学要点：
    - 灵活的格式化参数设计
    - 默认参数的合理选择
    - 多类型输入的统一处理

    Args:
        date: 需要转换的日期
        format: 日期格式字符串，默认为 "%Y-%m-%d"
                常用格式："%Y/%m/%d", "%Y年%m月%d日", "%Y-%m-%d %H:%M:%S"

    Returns:
        str: 格式化的日期字符串

    Raises:
        ValueError: 日期格式无效

    Examples:
        >>> date_to_str("2024-01-26")
        '2024-01-26'
        >>> date_to_str(20240126, "%Y/%m/%d")
        '2024/01/26'
        >>> date_to_str(None, "%Y年%m月%d日")
        '2025年01月22日'
    """
    if date is None:
        return datetime.date.today().strftime(format)

    # 直接处理datetime对象（最高效）
    if isinstance(date, datetime.datetime):
        return date.strftime(format)

    # 直接处理date对象
    if isinstance(date, datetime.date):
        return date.strftime(format)

    # 处理整数和字符串：先转换为date对象
    try:
        if isinstance(date, int):
            date_str = str(date)
            if len(date_str) != 8:
                raise ValueError(f"整数日期必须是8位数字，实际: {len(date_str)}")
            dt = datetime.datetime.strptime(date_str, '%Y%m%d')
        elif isinstance(date, str):
            # 尝试多种格式
            date_clean = date.replace('-', '').replace('/', '').replace('.', '').strip()
            if len(date_clean) == 8:
                dt = datetime.datetime.strptime(date_clean, '%Y%m%d')
            else:
                # 尝试直接解析ISO格式
                dt = datetime.datetime.fromisoformat(date.replace('/', '-'))
        else:
            raise ValueError(f"不支持的日期类型: {type(date).__name__}")

        return dt.strftime(format)
    except (ValueError, TypeError) as e:
        raise ValueError(f"日期转换失败 '{date}': {str(e)}") from e


def util_make_date_stamp(
    cursor_date: DateLike = None,
    format: str = "%Y-%m-%d"
) -> float:
    """
    将日期转换为Unix时间戳

    教学要点：
    1. Unix时间戳的概念和应用
    2. 时区处理（本函数使用本地时间）
    3. 统一时间点选择（00:00:00）

    将指定格式的日期转换为Unix时间戳（秒级精度）。
    时间戳对应当天00:00:00（本地时间）。

    应用场景：
    - 数据库索引（时间戳查询比日期字符串快）
    - 跨时区数据处理
    - 时间范围计算

    Args:
        cursor_date: 需要转换的日期，支持多种格式
                    如果为None，则使用当前日期
        format: 日期格式字符串（保留参数，向后兼容）

    Returns:
        float: Unix时间戳（秒）

    Raises:
        ValueError: 日期格式无效

    Examples:
        >>> util_make_date_stamp("2024-01-26")
        1706227200.0  # 对应 2024-01-26 00:00:00
    """
    if cursor_date is None:
        dt = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
    elif isinstance(cursor_date, datetime.datetime):
        # 取日期部分，时间设为00:00:00
        # 教学要点：统一时间点，避免时间精度导致的查询问题
        dt = datetime.datetime.combine(cursor_date.date(), datetime.time.min)
    elif isinstance(cursor_date, datetime.date):
        dt = datetime.datetime.combine(cursor_date, datetime.time.min)
    else:
        # 对于整数和字符串，先转换为整数日期，再转为datetime
        date_int = date_to_int(cursor_date)
        date_str = str(date_int)
        dt = datetime.datetime.strptime(date_str, '%Y%m%d')

    return dt.timestamp()


# ==================== 交易日查询函数 ====================

@lru_cache(maxsize=1024)
def is_trade_date(
    cursor_date: DateLike = None,
    exchange: str = 'SHFE'
) -> bool:
    """
    判断指定日期是否为交易日

    教学要点：
    1. LRU缓存优化高频查询
       - maxsize=1024: 缓存最近1024次查询结果
       - 适用于重复查询场景（如回测中频繁检查同一日期）
    2. MongoDB查询优化（使用date_int索引）
    3. 默认参数的合理设计（使用SHFE期货交易所）
    4. 异常容错（格式错误返回False而不是抛异常）

    性能优化：
    - 使用整数格式查询（比字符串快）
    - LRU缓存避免重复查询数据库
    - find_one限制返回字段（{"_id": 0}）减少数据传输

    Args:
        cursor_date: 需要检查的日期（默认今天）
                    支持格式：19981203, "20240910", datetime.date()
        exchange: 交易所代码（默认SHFE）
                 可选值：SHFE, DCE, CZCE, CFFEX, INE, GFEX, SHSE, SZSE等

    Returns:
        bool: 是否为交易日

    Examples:
        >>> is_trade_date("2024-01-26", "SHFE")
        True
        >>> is_trade_date()  # 检查今天是否为交易日
        False  # 假设今天是周末
        >>> is_trade_date("invalid_date", "SHFE")
        False  # 格式错误，返回False而不抛异常
    """
    # 统一转换为整数格式进行查询（性能更好）
    try:
        date_int = date_to_int(cursor_date)
    except (ValueError, TypeError):
        # 教学要点：异常容错设计
        # 日期格式错误时返回False，而不是抛出异常
        # 这样可以避免在批量处理中因个别数据错误而中断
        logger.debug(f"日期格式错误，返回False: {cursor_date}")
        return False

    # 构建查询条件
    # 教学要点：复合索引查询（exchange + date_int）
    query = {
        "exchange": exchange,
        "date_int": date_int
    }

    db = _get_database()
    result = db.trade_date.find_one(query, {"_id": 0})

    return result is not None


@lru_cache(maxsize=1024)
def get_pre_trade_date(
    cursor_date: DateLike = None,
    exchange: str = 'SHFE',
    n: int = 1,
    include_input: bool = False
) -> Optional[dict[str, Any]]:
    """
    获取指定日期之前的第n个交易日

    教学要点：
    1. 灵活的参数设计（include_input参数的巧妙应用）
    2. MongoDB聚合查询（sort + skip + limit组合）
    3. LRU缓存优化
    4. 边界条件处理（没找到返回None）

    应用场景：
    - 计算N日均线：需要前N个交易日的数据
    - 工作日回溯：跳过周末和节假日
    - 历史数据对比

    Args:
        cursor_date: 指定日期，默认为当前日期
        exchange: 交易所代码，默认为SHFE
        n: 往前回溯的天数，默认为1
        include_input: 是否将输入日期考虑在内（如果输入日期是交易日）
                      True: 如果输入日期是交易日，则将其计入n个交易日中
                      False: 不论输入日期是否为交易日，都从比输入日期更早的日期开始计数

    Returns:
        Optional[dict[str, Any]]: 交易日信息字典，如果没有找到则返回None
        返回字段包括：
        - exchange: 交易所代码
        - trade_date: 交易日期（字符串格式）
        - pretrade_date: 前一交易日
        - datestamp: 日期时间戳
        - date_int: 整数格式的日期(YYYYMMDD)

    Raises:
        ValueError: n < 1

    Examples:
        >>> result = get_pre_trade_date("2024-01-26", "SHFE", 1)
        >>> print(result['trade_date'])
        '2024-01-25'

        >>> # include_input的区别
        >>> get_pre_trade_date("2024-01-26", "SHFE", 1, include_input=False)
        # 返回1月25日（不包括26日本身）
        >>> get_pre_trade_date("2024-01-26", "SHFE", 1, include_input=True)
        # 如果26日是交易日，返回26日；否则返回25日
    """
    if n < 1:
        raise ValueError(f"n必须 >= 1，实际值: {n}")

    date_int = date_to_int(cursor_date)

    # 构建查询条件
    # 教学要点：$lte vs $lt 的区别
    if include_input and is_trade_date(date_int, exchange):
        # 包含输入日期：<= date_int
        query = {
            "exchange": exchange,
            "date_int": {"$lte": date_int}
        }
    else:
        # 不包含输入日期：< date_int
        query = {
            "exchange": exchange,
            "date_int": {"$lt": date_int}
        }

    # 查询前n个交易日
    # 教学要点：sort + skip + limit 的组合使用
    # - sort("date_int", -1): 降序排列（最新的在前）
    # - skip(n - 1): 跳过前n-1个（因为我们要第n个）
    # - limit(1): 只取一个结果
    db = _get_database()
    cursor = db.trade_date.find(
        query,
        {"_id": 0}
    ).sort("date_int", -1).skip(n - 1).limit(1)

    try:
        return cursor[0]
    except (IndexError, KeyError):
        # 没有找到符合条件的交易日
        logger.debug(f"未找到前{n}个交易日: {cursor_date}, {exchange}")
        return None


@lru_cache(maxsize=1024)
def get_next_trade_date(
    cursor_date: DateLike = None,
    exchange: str = 'SHFE',
    n: int = 1,
    include_input: bool = False
) -> Optional[dict[str, Any]]:
    """
    获取指定日期之后的第n个交易日

    教学要点：
    1. 与get_pre_trade_date对称的设计
    2. 升序排列（sort("date_int", 1)）
    3. $gte vs $gt 的区别

    应用场景：
    - 计算未来N个交易日的日期
    - 期货合约交割日计算
    - 工作日预测

    Args:
        cursor_date: 指定日期，默认为当前日期
        exchange: 交易所代码，默认为SHFE
        n: 往后推进的天数，默认为1
        include_input: 是否将输入日期考虑在内

    Returns:
        Optional[dict[str, Any]]: 交易日信息，没找到返回None

    Examples:
        >>> result = get_next_trade_date("2024-01-26", "SHFE", 1)
        >>> print(result['trade_date'])
        '2024-01-29'  # 周一
    """
    if n < 1:
        raise ValueError(f"n必须 >= 1，实际值: {n}")

    date_int = date_to_int(cursor_date)

    # 构建查询条件
    if include_input and is_trade_date(date_int, exchange):
        # 包含输入日期：>= date_int
        query = {
            "exchange": exchange,
            "date_int": {"$gte": date_int}
        }
    else:
        # 不包含输入日期：> date_int
        query = {
            "exchange": exchange,
            "date_int": {"$gt": date_int}
        }

    # 查询后n个交易日
    # 教学要点：升序排列（1表示升序）
    db = _get_database()
    cursor = db.trade_date.find(
        query,
        {"_id": 0}
    ).sort("date_int", 1).skip(n - 1).limit(1)

    try:
        return cursor[0]
    except (IndexError, KeyError):
        logger.debug(f"未找到后{n}个交易日: {cursor_date}, {exchange}")
        return None


def get_trade_calendar(
    start_date: DateLike = None,
    end_date: DateLike = None,
    exchange: str = 'SHFE'
) -> list[dict[str, Any]]:
    """
    获取指定日期范围内的交易日历

    教学要点：
    1. 范围查询（$gte + $lte）
    2. 索引优化（date_int字段建立索引）
    3. 批量数据返回（list(cursor)）
    4. 默认日期范围设计

    应用场景：
    - 回测系统：获取回测期间的所有交易日
    - 数据下载：批量下载多个交易日的数据
    - 统计分析：计算某时间段的交易日数量

    Args:
        start_date: 起始日期，默认为2010-01-01
        end_date: 结束日期，默认为当前日期
        exchange: 交易所代码，默认为SHFE

    Returns:
        list[dict[str, Any]]: 交易日历数据列表，每个字典包含：
        - exchange: 交易所代码
        - trade_date: 交易日期（字符串）
        - pretrade_date: 前一交易日
        - datestamp: 日期时间戳
        - date_int: 整数格式的日期

    Examples:
        >>> calendar = get_trade_calendar("2024-01-01", "2024-01-31", "SHFE")
        >>> print(f"1月共有 {len(calendar)} 个交易日")
        1月共有 21 个交易日

        >>> for day in calendar[:3]:
        ...     print(day['trade_date'])
        2024-01-02
        2024-01-03
        2024-01-04
    """
    # 设置合理的默认日期
    # 教学要点：默认值选择的考虑
    if start_date is None:
        start_date = datetime.date(2010, 1, 1)  # 大多数市场数据从2010年开始
    if end_date is None:
        end_date = datetime.date.today()

    # 转换为整数格式（使用整数查询比时间戳更高效）
    start_int = date_to_int(start_date)
    end_int = date_to_int(end_date)

    # 构建查询条件
    # 教学要点：范围查询的标准写法
    query = {
        'exchange': exchange,
        'date_int': {
            '$gte': start_int,  # >=
            '$lte': end_int     # <=
        }
    }

    # 执行查询
    db = _get_database()
    cursor = db.trade_date.find(
        query,
        {'_id': 0}  # 排除_id字段，减少数据传输
    ).sort('date_int', 1)  # 升序排列

    # 教学要点：cursor转list
    # cursor是迭代器，需要转为list才能多次使用
    return list(cursor)


def get_trade_dates(
    start_date: DateLike = None,
    end_date: DateLike = None,
    exchange: str = 'SHFE'
) -> list[str]:
    """
    获取指定日期范围内的交易日期列表（仅返回日期字符串）

    这是get_trade_calendar的简化版本，只返回日期字符串列表。

    教学要点：
    1. 便捷函数设计（wrapper function）
    2. 列表推导式的应用
    3. 简化API，提供多层次接口

    应用场景：
    - 只需要日期列表，不需要完整信息
    - 与pandas等库配合使用

    Args:
        start_date: 起始日期
        end_date: 结束日期
        exchange: 交易所代码

    Returns:
        list[str]: 交易日期字符串列表，格式为'YYYY-MM-DD'

    Examples:
        >>> dates = get_trade_dates("2024-01-01", "2024-01-05", "SHFE")
        >>> print(dates)
        ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
    """
    calendar = get_trade_calendar(start_date, end_date, exchange)
    # 教学要点：列表推导式 - 简洁高效的数据提取
    return [item['trade_date'] for item in calendar]


# ==================== 模块使用示例 ====================

if __name__ == "__main__":
    # 基础使用示例
    print("=" * 60)
    print("CherryQuant 日期工具模块示例")
    print("=" * 60)

    # 1. 日期格式转换
    print("\n1. 日期格式转换:")
    print(f"  字符串转整数: '2024-01-26' -> {date_to_int('2024-01-26')}")
    print(f"  整数转字符串: 20240126 -> {int_to_date_str(20240126)}")
    print(f"  自定义格式: {date_to_str('2024-01-26', '%Y年%m月%d日')}")

    # 2. 交易日查询（需要MongoDB连接）
    print("\n2. 交易日查询:")
    try:
        is_trading = is_trade_date("2024-01-26", "SHFE")
        print(f"  2024-01-26是否为SHFE交易日: {is_trading}")
    except Exception as e:
        print(f"  ⚠️ 交易日查询需要MongoDB连接: {e}")

    print("\n" + "=" * 60)
