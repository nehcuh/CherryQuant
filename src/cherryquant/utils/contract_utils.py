"""
Contract utilities - 合约代码解析与标准化工具

该模块提供期货和股票合约代码的标准化、解析、验证和格式转换功能。
支持多种数据源格式（掘金、Tushare、VNPy等），统一内部表示。

教学要点：
    1. 编码约定管理 - 不同交易所的大小写规则、日期格式规则
    2. 模式匹配与正则表达式 - 高效解析合约代码
    3. 缓存优化 - 使用LRU缓存减少重复解析
    4. 优雅降级 - 配置系统不可用时的后备方案
    5. 函数式编程 - 纯函数设计便于测试和复用

标准格式说明：
    内部标准格式：EXCHANGE.symbol（例如：SHFE.rb2501, SHSE.600000）
    - 交易所使用标准化代码（SHFE, DCE, CZCE, CFFEX, INE, SHSE, SZSE等）
    - 期货品种代码按交易所规范（上期所等小写，郑商所、中金所大写）
    - 期货合约月份统一4位数字（2501表示2025年1月）

数据源编码约定：
    - 上期所、大商所、上期能源、广期所：期货合约小写（rb2501）
    - 中金所：期货合约大写（IF2401）
    - 郑商所：期货合约大写，年月可能3位或4位（SR2501或SR501）

外部格式：
    - 掘金/GoldMiner: SHFE.rb2501, CZCE.SR2501
    - Tushare: RB2501.SHF, SR2501.ZCE（所有品种代码大写）
    - vnpy: RB2501.SHFE, SR2501.CZCE（所有品种代码大写，交易所使用标准代码）

来源: 整合自 quantbox.util.contract_utils
"""
from __future__ import annotations

from typing import Optional
from enum import Enum
import re
from functools import lru_cache
import logging
from datetime import datetime

from cherryquant.utils.exchange_utils import (
    ExchangeType,
    normalize_exchange,
    denormalize_exchange,
    is_futures_exchange,
    is_stock_exchange,
    STANDARD_EXCHANGES,
    STOCK_EXCHANGES,
    FUTURES_EXCHANGES,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 枚举类型定义
# ============================================================================

class ContractFormat(str, Enum):
    """合约代码格式枚举

    教学要点：
    1. str继承使得枚举值直接可用作字符串
    2. 统一管理所有支持的格式
    """
    STANDARD = "standard"  # 标准格式: EXCHANGE.symbol
    GOLDMINER = "goldminer"  # 掘金格式: EXCHANGE.symbol
    TUSHARE = "tushare"  # Tushare格式: SYMBOL.EXCHANGE
    VNPy = "vnpy"  # vnpy格式: symbol.EXCHANGE
    PLAIN = "plain"  # 纯代码: symbol (不含交易所)


class AssetType(str, Enum):
    """资产类型枚举"""
    STOCK = "stock"  # 股票
    FUTURES = "futures"  # 期货
    INDEX = "index"  # 指数
    FUND = "fund"  # 基金
    UNKNOWN = "unknown"  # 未知


class ContractType(str, Enum):
    """合约类型枚举

    教学要点：
    1. 识别特殊合约类型（主力、连续、加权等）
    2. 这些特殊合约在量化交易中有特殊用途
    """
    REGULAR = "regular"  # 普通合约（如 rb2501）
    MAIN = "main"  # 主力合约（如 rb888）
    CONTINUOUS = "continuous"  # 连续合约（如 rb000）
    WEIGHTED = "weighted"  # 加权指数（如 rb99）
    CURRENT_MONTH = "current_month"  # 当月合约（如 rb00）
    NEXT_MONTH = "next_month"  # 下月合约（如 rb01）
    NEXT_QUARTER = "next_quarter"  # 下季合约（如 rb02）
    NEXT_NEXT_QUARTER = "next_next_quarter"  # 隔季合约（如 rb03）
    UNKNOWN = "unknown"  # 未知类型


# ============================================================================
# 编码约定管理器
# ============================================================================

class EncodingConvention:
    """编码约定管理器 - 统一处理不同交易所的编码规则

    教学要点：
    1. 集中管理复杂的编码规则，避免逻辑散落各处
    2. 使用类方法实现工具类模式
    3. 预定义规则表提高查询效率
    """

    # 交易所大小写规则（基于实际交易所规范）
    CASE_RULES = {
        'lowercase': {'SHFE', 'DCE', 'INE', 'GFEX'},  # 品种代码小写
        'uppercase': {'CZCE', 'CFFEX'},  # 品种代码大写
    }

    # 特殊合约类型标识
    SPECIAL_CONTRACTS = {
        'main': {'888', '000'},
        'weighted': {'99'},
        'current_month': {'00'},
        'next_month': {'01'},
        'next_quarter': {'02'},
        'next_next_quarter': {'03'},
    }

    @classmethod
    def get_case_rule(cls, exchange: str) -> str:
        """获取交易所的大小写规则

        教学要点：
        1. 线性查找字典集合
        2. 提供合理的默认值
        """
        for rule, exchanges in cls.CASE_RULES.items():
            if exchange in exchanges:
                return rule
        return 'lowercase'  # 默认小写

    @classmethod
    def apply_case_rule(cls, symbol: str, exchange: str) -> str:
        """应用大小写规则

        教学要点：
        1. 封装规则查询和应用逻辑
        2. 调用者无需关心规则细节
        """
        rule = cls.get_case_rule(exchange)
        if rule == 'uppercase':
            return symbol.upper()
        return symbol.lower()

    @classmethod
    def detect_contract_type(cls, date_part: str) -> ContractType:
        """检测合约类型

        教学要点：
        1. 基于日期部分的模式识别
        2. 特殊合约优先判断
        3. 普通合约作为后备
        """
        date_part_lower = date_part.lower()

        for contract_type, identifiers in cls.SPECIAL_CONTRACTS.items():
            if date_part_lower in identifiers:
                return ContractType(contract_type)

        # 普通合约判断
        if len(date_part) == 4 or (len(date_part) == 3 and date_part.isdigit()):
            return ContractType.REGULAR

        return ContractType.UNKNOWN

    @classmethod
    def normalize_czce_year(cls, year_part: str) -> int:
        """智能处理郑商所3位年月格式的年份推断

        教学要点：
        1. 历史遗留格式的兼容处理
        2. 基于当前时间的智能推断
        3. 边界条件的处理（避免跨十年错误）

        示例:
            当前年份2024年，输入"501"（表示25年1月）
            - 提取年份数字 5
            - 候选年份: 2020 + 5 = 2025
            - 2025 - 2024 = 1 < 8，不调整
            - 返回 2025
        """
        if len(year_part) != 3:
            raise ValueError(f"郑商所年月格式错误: {year_part}")

        year_last_digit = int(year_part[0])
        current_year = datetime.now().year
        current_decade = current_year // 10 * 10

        # 智能推断：基于当前年份判断是哪个十年
        candidate_year = current_decade + year_last_digit

        # 如果推断的年份比当前年份晚超过8年，则认为是上一个十年
        if candidate_year - current_year > 8:
            candidate_year -= 10

        return candidate_year


# ============================================================================
# 合约信息类
# ============================================================================

class ParsedContractInfo:
    """解析后的合约信息类（重命名避免与base_collector.ContractInfo冲突）

    教学要点：
    1. 数据类模式 - 封装相关数据和行为
    2. 便利方法 - 提供语义化的查询接口
    3. 类型安全 - 使用枚举类型避免字符串错误

    注意：此类用于合约代码解析，与base_collector.ContractInfo（合约完整规格）不同
    """

    def __init__(
        self,
        exchange: str,
        symbol: str,
        asset_type: AssetType = AssetType.UNKNOWN,
        underlying: str | None = None,
        year: int | None = None,
        month: int | None = None,
        contract_type: ContractType = ContractType.UNKNOWN,
    ):
        self.exchange = exchange
        self.symbol = symbol
        self.asset_type = asset_type
        self.underlying = underlying
        self.year = year
        self.month = month
        self.contract_type = contract_type

    def __repr__(self) -> str:
        return (
            f"ParsedContractInfo(exchange={self.exchange}, symbol={self.symbol}, "
            f"asset_type={self.asset_type.value}, underlying={self.underlying}, "
            f"year={self.year}, month={self.month}, contract_type={self.contract_type.value})"
        )

    def to_standard(self) -> str:
        """转换为标准格式代码"""
        return f"{self.exchange}.{self.symbol}"

    # 便利方法
    def is_futures(self) -> bool:
        return self.asset_type == AssetType.FUTURES

    def is_stock(self) -> bool:
        return self.asset_type == AssetType.STOCK

    def is_regular_contract(self) -> bool:
        return self.contract_type == ContractType.REGULAR

    def is_main_contract(self) -> bool:
        return self.contract_type == ContractType.MAIN

    def is_continuous_contract(self) -> bool:
        return self.contract_type == ContractType.CONTINUOUS

    def is_weighted_contract(self) -> bool:
        return self.contract_type == ContractType.WEIGHTED

    def is_current_month_contract(self) -> bool:
        return self.contract_type == ContractType.CURRENT_MONTH

    def is_next_month_contract(self) -> bool:
        return self.contract_type == ContractType.NEXT_MONTH

    def is_next_quarter_contract(self) -> bool:
        return self.contract_type == ContractType.NEXT_QUARTER

    def is_next_next_quarter_contract(self) -> bool:
        return self.contract_type == ContractType.NEXT_NEXT_QUARTER


# 向后兼容性别名（已弃用，请使用ParsedContractInfo）
ContractInfo = ParsedContractInfo


# ============================================================================
# 正则表达式模式（预编译优化）
# ============================================================================

# 教学要点：模块级别预编译正则表达式，避免重复编译开销
_FUTURES_PATTERN = re.compile(r"^([A-Za-z]+)(\d+)$")
_STOCK_PATTERN = re.compile(r"^\d{6}$")


# ============================================================================
# 核心解析函数模块化
# ============================================================================

def _parse_exchange_and_symbol(
    contract: str,
    default_exchange: str | None = None
) -> tuple[str, str]:
    """解析交易所和合约代码部分

    教学要点：
    1. 处理多种输入格式（带/不带交易所）
    2. 智能识别交易所位置（前缀或后缀）
    3. 使用异常处理进行格式验证

    Args:
        contract: 合约代码（如 "SHFE.rb2501" 或 "rb2501"）
        default_exchange: 默认交易所（当合约代码不含交易所时使用）

    Returns:
        (交易所, 代码) 元组
    """
    if "." in contract:
        parts = contract.split(".")
        if len(parts) != 2:
            raise ValueError(f"合约代码格式无效: {contract}")

        part1, part2 = parts

        # 尝试识别交易所部分
        for candidate_exchange, candidate_symbol in [(part1, part2), (part2, part1)]:
            if candidate_exchange.isalpha() and len(candidate_exchange) <= 6:
                try:
                    exchange = normalize_exchange(candidate_exchange)
                    return exchange, candidate_symbol
                except ValueError:
                    continue

        raise ValueError(f"无法识别交易所: {contract}")
    else:
        # 纯合约代码，需要默认交易所
        if not default_exchange:
            raise ValueError(
                f"合约代码 '{contract}' 未包含交易所信息，需要提供 default_exchange"
            )
        exchange = normalize_exchange(default_exchange)
        return exchange, contract


def _parse_contract_year_month(
    underlying: str,
    date_part: str,
    exchange: str
) -> tuple[int, int, str]:
    """解析合约年月并格式化

    教学要点：
    1. 处理不同的日期格式（4位标准格式 vs 3位郑商所格式）
    2. 智能年份推断
    3. 应用交易所特定的格式规则

    Args:
        underlying: 品种代码（如 "rb", "SR"）
        date_part: 日期部分（如 "2501", "501"）
        exchange: 交易所代码

    Returns:
        (年份, 月份, 格式化后的完整代码) 元组
    """
    if len(date_part) == 4:
        # 标准年月格式 YYMM
        year = 2000 + int(date_part[:2])
        month = int(date_part[2:])
    elif len(date_part) == 3 and exchange == "CZCE":
        # 郑商所3位年月格式 YMM
        year = EncodingConvention.normalize_czce_year(date_part)
        month = int(date_part[1:])
        # 转换为4位标准格式
        date_part = f"{year % 100:02d}{month:02d}"
    else:
        raise ValueError(f"期货合约日期格式无效: {date_part}")

    # 应用交易所大小写规则
    symbol_formatted = EncodingConvention.apply_case_rule(underlying, exchange) + date_part
    if exchange in ['CZCE', 'CFFEX']:
        symbol_formatted = symbol_formatted.upper()

    return year, month, symbol_formatted


def _parse_futures_contract(symbol: str, exchange: str) -> ParsedContractInfo:
    """解析期货合约

    教学要点：
    1. 使用正则表达式进行模式匹配
    2. 区分普通合约和特殊合约
    3. 应用交易所特定规则

    Args:
        symbol: 合约代码（如 "rb2501", "RB888"）
        exchange: 交易所代码

    Returns:
        ParsedContractInfo对象
    """
    match = _FUTURES_PATTERN.match(symbol)
    if not match:
        raise ValueError(f"期货合约代码格式无效: {symbol}")

    underlying = match.group(1)
    date_part = match.group(2)

    # 检测合约类型
    contract_type = EncodingConvention.detect_contract_type(date_part)

    # 特殊合约类型处理
    if contract_type != ContractType.REGULAR:
        symbol_formatted = (
            EncodingConvention.apply_case_rule(underlying, exchange) +
            date_part.upper()
        )
        return ParsedContractInfo(
            exchange=exchange,
            symbol=symbol_formatted,
            asset_type=AssetType.FUTURES,
            underlying=EncodingConvention.apply_case_rule(underlying, exchange),
            year=None,
            month=None,
            contract_type=contract_type,
        )

    # 普通合约处理
    year, month, symbol_formatted = _parse_contract_year_month(
        underlying, date_part, exchange
    )

    return ParsedContractInfo(
        exchange=exchange,
        symbol=symbol_formatted,
        asset_type=AssetType.FUTURES,
        underlying=EncodingConvention.apply_case_rule(underlying, exchange),
        year=year,
        month=month,
        contract_type=ContractType.REGULAR,
    )


def _detect_stock_hardcoded(symbol: str, exchange: str) -> AssetType:
    """硬编码的股票类型检测

    教学要点：
    1. 基于代码前缀的快速判断
    2. 不同交易所的编码规则差异
    3. 提供合理的默认值（UNKNOWN）

    编码规则：
        上交所(SHSE):
            - 600-601: 主板股票
            - 688: 科创板
            - 000: 指数
        深交所(SZSE):
            - 000-002: 主板
            - 003-004: 中小板
            - 300: 创业板
            - 399: 指数

    Args:
        symbol: 股票代码（6位数字）
        exchange: 交易所代码

    Returns:
        AssetType枚举值
    """
    if exchange == "SHSE":
        code_prefix = int(symbol[:3])
        # 主板：600-601，科创板：688
        if 600 <= code_prefix <= 601 or code_prefix == 688:
            return AssetType.STOCK
        # 指数：000开头
        elif symbol.startswith('000'):
            return AssetType.INDEX
    elif exchange == "SZSE":
        code_prefix = int(symbol[:3])
        # 主板：000-002，中小板：003-004，创业板：300
        if 0 <= code_prefix <= 4 or code_prefix == 300:
            return AssetType.STOCK
        # 指数：399开头
        elif code_prefix == 399:
            return AssetType.INDEX

    return AssetType.UNKNOWN


def _parse_stock_contract(symbol: str, exchange: str) -> ParsedContractInfo:
    """解析股票合约

    教学要点：
    1. 股票代码格式验证（6位数字）
    2. 区分股票和指数

    Args:
        symbol: 股票代码（如 "600000", "000001"）
        exchange: 交易所代码

    Returns:
        ParsedContractInfo对象
    """
    if not _STOCK_PATTERN.match(symbol):
        raise ValueError(f"股票代码格式无效: {symbol}")

    asset_type = _detect_stock_hardcoded(symbol, exchange)

    return ParsedContractInfo(
        exchange=exchange,
        symbol=symbol,
        asset_type=asset_type,
        contract_type=ContractType.REGULAR,
    )


def _detect_asset_type(symbol: str, exchange: str) -> AssetType:
    """检测资产类型

    教学要点：
    1. 基于交易所类型的初步判断
    2. 股票需要进一步细分（股票 vs 指数）

    Args:
        symbol: 合约代码
        exchange: 交易所代码

    Returns:
        AssetType枚举值
    """
    if is_futures_exchange(exchange):
        return AssetType.FUTURES
    elif is_stock_exchange(exchange):
        return _detect_stock_hardcoded(symbol, exchange)
    else:
        return AssetType.UNKNOWN


# ============================================================================
# 数据源格式转换
# ============================================================================

@lru_cache(maxsize=32)
def _get_data_source_exchange_mapping(data_source: str) -> dict[str, str]:
    """获取数据源交易所映射

    教学要点：
    1. LRU缓存避免重复构建映射表
    2. 集中管理所有数据源的映射关系
    3. 使用字典实现O(1)查询

    Args:
        data_source: 数据源名称（goldminer/tushare/vnpy）

    Returns:
        交易所代码映射字典
    """
    mappings = {
        "goldminer": {
            "SHFE": "SHFE",
            "DCE": "DCE",
            "CZCE": "CZCE",
            "CFFEX": "CFFEX",
            "INE": "INE",
            "GFEX": "GFEX",
            "SHSE": "SHSE",
            "SZSE": "SZSE"
        },
        "tushare": {
            "SHFE": "SHF",
            "DCE": "DCE",
            "CZCE": "ZCE",
            "CFFEX": "CFFEX",
            "INE": "INE",
            "GFEX": "GFEX",
            "SHSE": "SH",  # 上交所
            "SZSE": "SZ",  # 深交所
        },
        "vnpy": {
            "SHFE": "SHFE",
            "DCE": "DCE",
            "CZCE": "CZCE",
            "CFFEX": "CFFEX",
            "INE": "INE",
            "GFEX": "GFEX",
            "SSE": "SSE",
            "SZSE": "SZSE",
            "BSE": "BSE"
        }
    }
    return mappings.get(data_source, {})


# ============================================================================
# 主要API函数
# ============================================================================

def parse_contract(
    contract: str,
    default_exchange: str | None = None,
    asset_type: AssetType | None = None,
) -> ParsedContractInfo:
    """解析合约代码，提取交易所、品种、年月等信息

    教学要点：
    1. 统一的API入口
    2. 自动检测资产类型
    3. 详细的错误信息

    使用示例：
        >>> info = parse_contract("SHFE.rb2501")
        >>> print(info.exchange)  # "SHFE"
        >>> print(info.underlying)  # "rb"
        >>> print(info.year, info.month)  # 2025 1

        >>> info = parse_contract("rb2501", default_exchange="SHFE")
        >>> print(info.to_standard())  # "SHFE.rb2501"

    Args:
        contract: 合约代码
        default_exchange: 默认交易所
        asset_type: 资产类型提示（可选，通常自动检测）

    Returns:
        ParsedContractInfo: 解析后的合约信息

    Raises:
        ValueError: 合约代码格式无效
    """
    if not contract or not contract.strip():
        raise ValueError("合约代码不能为空")

    contract = contract.strip()

    # 解析交易所和合约代码
    exchange, symbol = _parse_exchange_and_symbol(contract, default_exchange)

    # 检测资产类型
    detected_asset_type = asset_type or _detect_asset_type(symbol, exchange)

    if detected_asset_type == AssetType.FUTURES:
        return _parse_futures_contract(symbol, exchange)
    elif detected_asset_type == AssetType.STOCK:
        return _parse_stock_contract(symbol, exchange)
    else:
        raise ValueError(f"不支持的资产类型: {detected_asset_type}")


def format_contract(
    contract: str,
    target_format: ContractFormat | str,
    default_exchange: str | None = None,
    asset_type: AssetType | None = None,
) -> str:
    """将合约代码转换为指定格式

    教学要点：
    1. 先解析再格式化的两阶段处理
    2. 支持多种目标格式
    3. 数据源特定规则的应用

    使用示例：
        >>> format_contract("SHFE.rb2501", "tushare")
        "RB2501.SHF"

        >>> format_contract("SHFE.rb2501", "goldminer")
        "SHFE.rb2501"

    Args:
        contract: 输入合约代码
        target_format: 目标格式（ContractFormat枚举或字符串）
        default_exchange: 默认交易所
        asset_type: 资产类型提示

    Returns:
        str: 转换后的合约代码

    Raises:
        ValueError: 合约代码无效或格式不支持
    """
    # 解析合约代码
    info = parse_contract(contract, default_exchange, asset_type)

    # 转换为枚举
    if isinstance(target_format, str):
        try:
            target_format = ContractFormat(target_format.lower())
        except ValueError:
            raise ValueError(f"不支持的格式: {target_format}")

    # 根据目标格式生成代码
    if target_format == ContractFormat.STANDARD:
        return f"{info.exchange}.{info.symbol}"

    elif target_format == ContractFormat.GOLDMINER:
        mapping = _get_data_source_exchange_mapping("goldminer")
        exchange_gm = mapping.get(info.exchange, info.exchange)

        if info.exchange in ["CFFEX", "CZCE"]:
            # 中金所和郑商所使用大写
            if info.exchange == "CZCE" and info.asset_type == AssetType.FUTURES:
                # 郑商所期货合约使用3位年月格式
                if len(info.symbol) >= 4 and info.symbol[-4:].isdigit():
                    symbol = info.symbol[:-4] + info.symbol[-3:]
                else:
                    symbol = info.symbol
                return f"{exchange_gm}.{symbol.upper()}"
            else:
                return f"{exchange_gm}.{info.symbol.upper()}"
        else:
            # 上期所、大商所、上期能源、广期所使用小写
            return f"{exchange_gm}.{info.symbol.lower()}"

    elif target_format == ContractFormat.TUSHARE:
        mapping = _get_data_source_exchange_mapping("tushare")
        exchange_ts = mapping.get(info.exchange, info.exchange)

        # Tushare 所有合约品种都使用大写
        return f"{info.symbol.upper()}.{exchange_ts}"

    elif target_format == ContractFormat.VNPy:
        mapping = _get_data_source_exchange_mapping("vnpy")
        exchange_vnpy = mapping.get(info.exchange, info.exchange)

        # vnpy也使用大写品种代码
        return f"{info.symbol.upper()}.{exchange_vnpy}"

    elif target_format == ContractFormat.PLAIN:
        return info.symbol

    else:
        raise ValueError(f"不支持的目标格式: {target_format}")


def format_contracts(
    contracts: str | list[str],
    target_format: ContractFormat | str,
    default_exchange: str | None = None,
    asset_type: AssetType | None = None,
) -> list[str]:
    """批量转换合约代码格式

    教学要点：
    1. 支持逗号分隔的字符串或列表输入
    2. 批量处理提高效率
    3. 统一的错误处理

    Args:
        contracts: 合约代码列表或逗号分隔的字符串
        target_format: 目标格式
        default_exchange: 默认交易所
        asset_type: 资产类型提示

    Returns:
        List[str]: 转换后的合约代码列表
    """
    if isinstance(contracts, str):
        contracts = [c.strip() for c in contracts.split(",") if c.strip()]

    results = []
    for contract in contracts:
        try:
            formatted = format_contract(contract, target_format, default_exchange, asset_type)
            results.append(formatted)
        except ValueError as e:
            raise ValueError(f"转换合约代码 '{contract}' 失败: {str(e)}")

    return results


def validate_contract(
    contract: str,
    exchange: str | None = None,
    asset_type: AssetType | None = None,
) -> bool:
    """验证合约代码格式是否有效

    教学要点：
    1. 使用异常处理进行验证
    2. 支持额外的约束条件

    Args:
        contract: 合约代码
        exchange: 期望的交易所
        asset_type: 期望的资产类型

    Returns:
        bool: 是否有效
    """
    try:
        info = parse_contract(contract)

        if exchange is not None:
            expected_exchange = normalize_exchange(exchange)
            if info.exchange != expected_exchange:
                return False

        if asset_type is not None and info.asset_type != asset_type:
            return False

        return True
    except (ValueError, Exception):
        return False


def validate_contracts(
    contracts: str | list[str],
    exchange: str | None = None,
    asset_type: AssetType | None = None,
    skip_invalid: bool = False,
) -> bool | list[bool]:
    """批量验证合约代码

    Args:
        contracts: 合约代码列表
        exchange: 期望的交易所
        asset_type: 期望的资产类型
        skip_invalid: 是否跳过无效代码

    Returns:
        Union[bool, List[bool]]: 验证结果
    """
    if isinstance(contracts, str):
        contracts = [c.strip() for c in contracts.split(",") if c.strip()]

    results = [validate_contract(c, exchange, asset_type) for c in contracts]

    if skip_invalid:
        return any(results)
    else:
        return results


def split_contract(contract: str) -> tuple[str, str]:
    """分离合约代码的交易所和代码部分

    Args:
        contract: 合约代码

    Returns:
        Tuple[str, str]: (交易所, 代码)
    """
    info = parse_contract(contract)
    return (info.exchange, info.symbol)


def get_underlying(contract: str) -> str | None:
    """获取期货合约的标的品种代码

    Args:
        contract: 期货合约代码

    Returns:
        Optional[str]: 品种代码
    """
    try:
        info = parse_contract(contract)
        return info.underlying
    except (ValueError, Exception):
        return None


def get_contract_month(contract: str) -> tuple[int, int] | None:
    """获取期货合约的年月

    Args:
        contract: 期货合约代码

    Returns:
        Optional[Tuple[int, int]]: (年份, 月份)
    """
    try:
        info = parse_contract(contract)
        if info.year is not None and info.month is not None:
            return (info.year, info.month)
        return None
    except (ValueError, Exception):
        return None


def is_main_contract(contract: str) -> bool:
    """判断是否为主力合约代码

    Args:
        contract: 合约代码

    Returns:
        bool: 是否为主力合约
    """
    try:
        info = parse_contract(contract)
        if info.asset_type != AssetType.FUTURES:
            return False
        return info.is_main_contract()
    except (ValueError, Exception):
        return False


def normalize_contract(
    contract: str,
    default_exchange: str | None = None,
) -> str:
    """标准化合约代码为内部统一格式

    Args:
        contract: 输入合约代码
        default_exchange: 默认交易所

    Returns:
        str: 标准化后的合约代码
    """
    return format_contract(contract, ContractFormat.STANDARD, default_exchange)


def normalize_contracts(
    contracts: str | list[str],
    default_exchange: str | None = None,
) -> list[str]:
    """批量标准化合约代码

    Args:
        contracts: 合约代码列表
        default_exchange: 默认交易所

    Returns:
        List[str]: 标准化后的合约代码列表
    """
    return format_contracts(contracts, ContractFormat.STANDARD, default_exchange)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "SHFE.rb2501",
        "RB2501.SHF",
        "rb2501.SHFE",
        "CZCE.SR501",
        "SR2501.ZCE",
        "SHSE.600000",
        "600000.SH",
    ]

    print("=" * 70)
    print("合约代码解析测试")
    print("=" * 70)

    for contract in test_cases:
        try:
            info = parse_contract(contract)
            print(f"\n输入: {contract}")
            print(f"  交易所: {info.exchange}")
            print(f"  代码: {info.symbol}")
            print(f"  资产类型: {info.asset_type.value}")
            if info.underlying:
                print(f"  标的: {info.underlying}")
            if info.year and info.month:
                print(f"  年月: {info.year}年{info.month}月")
            print(f"  标准格式: {info.to_standard()}")
            print(f"  Tushare格式: {format_contract(contract, 'tushare')}")
        except Exception as e:
            print(f"\n输入: {contract}")
            print(f"  ❌ 错误: {e}")
