"""
合约代码标准化工具

统一处理不同数据源和交易接口之间的合约代码格式差异
主要解决郑商所(CZCE)合约代码格式不一致的问题
"""

import re
import logging

logger = logging.getLogger(__name__)


class SymbolStandardizer:
    """
    合约代码标准化器

    处理不同格式间的转换:
    - Tushare格式: RB2501.SHF, SR2501.ZCE, I2501.DCE, IF2501.CFX
    - VNPy/CTP格式: rb2501.SHFE, SR501.CZCE, i2501.DCE, IF2501.CFFEX

    关键差异:
    1. 郑商所(CZCE)合约代码在VNPy中使用3位数字(SR501)，而Tushare使用4位(SR2501)
    2. 交易所代码映射不同
    3. 大小写规则不同
    """

    # 交易所代码映射: Tushare -> VNPy
    EXCHANGE_TUSHARE_TO_VNPY = {
        "SHF": "SHFE",   # 上海期货交易所
        "DCE": "DCE",    # 大连商品交易所
        "ZCE": "CZCE",   # 郑州商品交易所
        "CFX": "CFFEX",  # 中国金融期货交易所
        "INE": "INE",    # 上海国际能源交易中心
    }

    # 交易所代码映射: VNPy -> Tushare
    EXCHANGE_VNPY_TO_TUSHARE = {v: k for k, v in EXCHANGE_TUSHARE_TO_VNPY.items()}

    # 需要大写的交易所 (VNPy标准)
    UPPERCASE_EXCHANGES = {"CZCE", "CFFEX"}

    @classmethod
    def tushare_to_vnpy(cls, ts_symbol: str) -> tuple[str, str]:
        """
        将Tushare格式的合约代码转换为VNPy格式

        Args:
            ts_symbol: Tushare格式，如 "RB2501.SHF", "SR2501.ZCE"

        Returns:
            (symbol, exchange): VNPy格式，如 ("rb2501", "SHFE"), ("SR501", "CZCE")

        Examples:
            >>> SymbolStandardizer.tushare_to_vnpy("RB2501.SHF")
            ('rb2501', 'SHFE')
            >>> SymbolStandardizer.tushare_to_vnpy("SR2501.ZCE")
            ('SR501', 'CZCE')
            >>> SymbolStandardizer.tushare_to_vnpy("I2501.DCE")
            ('i2501', 'DCE')
        """
        if '.' not in ts_symbol:
            raise ValueError(f"Invalid Tushare symbol format: {ts_symbol}")

        parts = ts_symbol.split('.')
        if len(parts) != 2:
            raise ValueError(f"Invalid Tushare symbol format: {ts_symbol}")

        symbol, ts_exchange = parts

        # 转换交易所代码
        vnpy_exchange = cls.EXCHANGE_TUSHARE_TO_VNPY.get(ts_exchange)
        if not vnpy_exchange:
            logger.warning(f"Unknown Tushare exchange: {ts_exchange}, using as-is")
            vnpy_exchange = ts_exchange

        # 提取品种代码和合约月份
        match = re.match(r'([A-Za-z]+)(\d+)', symbol)
        if not match:
            raise ValueError(f"Invalid symbol format: {symbol}")

        commodity = match.group(1)
        month_code = match.group(2)

        # 处理郑商所特殊格式: 4位数字转3位数字
        if vnpy_exchange == "CZCE":
            # SR2501 -> SR501 (去掉年份的千位)
            if len(month_code) == 4:
                month_code = month_code[1:]  # 去掉第一位
            vnpy_symbol = f"{commodity.upper()}{month_code}"
        else:
            # 其他交易所保持4位数字
            # 上期所和大商所: 小写
            # 中金所: 大写
            if vnpy_exchange in cls.UPPERCASE_EXCHANGES:
                vnpy_symbol = f"{commodity.upper()}{month_code}"
            else:
                vnpy_symbol = f"{commodity.lower()}{month_code}"

        return vnpy_symbol, vnpy_exchange

    @classmethod
    def vnpy_to_tushare(cls, vnpy_symbol: str, vnpy_exchange: str) -> str:
        """
        将VNPy格式的合约代码转换为Tushare格式

        Args:
            vnpy_symbol: VNPy合约代码，如 "rb2501", "SR501", "IF2501"
            vnpy_exchange: VNPy交易所代码，如 "SHFE", "CZCE"

        Returns:
            Tushare格式的合约代码，如 "RB2501.SHF", "SR2501.ZCE"

        Examples:
            >>> SymbolStandardizer.vnpy_to_tushare("rb2501", "SHFE")
            'RB2501.SHF'
            >>> SymbolStandardizer.vnpy_to_tushare("SR501", "CZCE")
            'SR2501.ZCE'
        """
        # 转换交易所代码
        ts_exchange = cls.EXCHANGE_VNPY_TO_TUSHARE.get(vnpy_exchange)
        if not ts_exchange:
            logger.warning(f"Unknown VNPy exchange: {vnpy_exchange}, using as-is")
            ts_exchange = vnpy_exchange

        # 提取品种代码和合约月份
        match = re.match(r'([A-Za-z]+)(\d+)', vnpy_symbol)
        if not match:
            raise ValueError(f"Invalid VNPy symbol format: {vnpy_symbol}")

        commodity = match.group(1)
        month_code = match.group(2)

        # 处理郑商所特殊格式: 3位数字转4位数字
        if vnpy_exchange == "CZCE":
            # SR501 -> SR2501 (补充年份的千位)
            if len(month_code) == 3:
                # 根据月份推断年份
                year = int(month_code[0])
                month = int(month_code[1:])

                # 简单推断：假设是2020-2029年
                full_year = 2000 + (20 + year) if year < 10 else 2000 + year
                month_code = f"{full_year % 100:02d}{month:02d}"

            ts_symbol = f"{commodity.upper()}{month_code}"
        else:
            # 其他交易所直接转大写
            ts_symbol = f"{commodity.upper()}{month_code}"

        return f"{ts_symbol}.{ts_exchange}"

    @classmethod
    def standardize_for_database(cls, ts_symbol: str) -> tuple[str, str]:
        """
        标准化合约代码用于数据库存储（使用VNPy格式）

        Args:
            ts_symbol: Tushare格式的合约代码

        Returns:
            (symbol, exchange): 适合VNPy使用的格式
        """
        return cls.tushare_to_vnpy(ts_symbol)

    @classmethod
    def get_vt_symbol(cls, symbol: str, exchange: str) -> str:
        """
        生成VNPy的vt_symbol格式

        Args:
            symbol: 合约代码（VNPy格式）
            exchange: 交易所代码（VNPy格式）

        Returns:
            vt_symbol: 如 "rb2501.SHFE", "SR501.CZCE"
        """
        return f"{symbol}.{exchange}"

    @classmethod
    def parse_vt_symbol(cls, vt_symbol: str) -> tuple[str, str]:
        """
        解析VNPy的vt_symbol

        Args:
            vt_symbol: 如 "rb2501.SHFE"

        Returns:
            (symbol, exchange)
        """
        if '.' not in vt_symbol:
            raise ValueError(f"Invalid vt_symbol format: {vt_symbol}")

        parts = vt_symbol.split('.')
        if len(parts) != 2:
            raise ValueError(f"Invalid vt_symbol format: {vt_symbol}")

        return parts[0], parts[1]


def standardize_tushare_contract(ts_code: str) -> tuple[str, str]:
    """
    便捷函数：标准化Tushare合约代码为VNPy格式

    Args:
        ts_code: Tushare格式，如 "RB2501.SHF"

    Returns:
        (symbol, exchange): VNPy格式
    """
    return SymbolStandardizer.tushare_to_vnpy(ts_code)


def create_vt_symbol(symbol: str, exchange: str) -> str:
    """
    便捷函数：创建vt_symbol

    Args:
        symbol: VNPy格式的合约代码
        exchange: VNPy格式的交易所代码

    Returns:
        vt_symbol: 如 "rb2501.SHFE"
    """
    return SymbolStandardizer.get_vt_symbol(symbol, exchange)
