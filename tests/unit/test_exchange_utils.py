"""
Unit tests for exchange_utils module

测试覆盖：
1. 交易所代码标准化 (normalize_exchange)
2. 交易所代码反标准化 (denormalize_exchange)
3. 交易所类型判断 (is_futures_exchange, is_stock_exchange)
4. 交易所信息查询 (get_exchange_info)
5. 交易所验证 (validate_exchanges)
"""
import pytest
from cherryquant.utils.exchange_utils import (
    ExchangeType,
    normalize_exchange,
    denormalize_exchange,
    is_futures_exchange,
    is_stock_exchange,
    get_exchange_info,
    validate_exchanges,
    STANDARD_EXCHANGES,
    FUTURES_EXCHANGES,
    STOCK_EXCHANGES,
)


class TestNormalizeExchange:
    """测试交易所代码标准化"""

    def test_normalize_futures_exchanges(self):
        """测试期货交易所标准化"""
        # 上期所
        assert normalize_exchange("SHFE") == "SHFE"
        assert normalize_exchange("SHF") == "SHFE"
        assert normalize_exchange("shfe") == "SHFE"

        # 大商所
        assert normalize_exchange("DCE") == "DCE"
        assert normalize_exchange("dce") == "DCE"

        # 郑商所
        assert normalize_exchange("CZCE") == "CZCE"
        assert normalize_exchange("ZCE") == "CZCE"
        assert normalize_exchange("czce") == "CZCE"

        # 中金所
        assert normalize_exchange("CFFEX") == "CFFEX"
        assert normalize_exchange("CFX") == "CFFEX"
        assert normalize_exchange("cffex") == "CFFEX"

        # 能源所
        assert normalize_exchange("INE") == "INE"
        assert normalize_exchange("ine") == "INE"

        # 广期所
        assert normalize_exchange("GFEX") == "GFEX"
        assert normalize_exchange("GFE") == "GFEX"

    def test_normalize_stock_exchanges(self):
        """测试股票交易所标准化"""
        # 上交所
        assert normalize_exchange("SHSE") == "SHSE"
        assert normalize_exchange("SSE") == "SHSE"
        assert normalize_exchange("SH") == "SHSE"
        assert normalize_exchange("shse") == "SHSE"

        # 深交所
        assert normalize_exchange("SZSE") == "SZSE"
        assert normalize_exchange("SZ") == "SZSE"
        assert normalize_exchange("szse") == "SZSE"

        # 北交所
        assert normalize_exchange("BSE") == "BSE"
        assert normalize_exchange("BJ") == "BSE"

    def test_normalize_invalid(self):
        """测试无效交易所代码"""
        with pytest.raises(ValueError):
            normalize_exchange("INVALID")

        with pytest.raises(ValueError):
            normalize_exchange("")

        with pytest.raises(ValueError):
            normalize_exchange("   ")


class TestDenormalizeExchange:
    """测试交易所代码反标准化"""

    def test_denormalize_tushare(self):
        """测试转换为Tushare格式"""
        assert denormalize_exchange("SHFE", "tushare") == "SHF"
        assert denormalize_exchange("DCE", "tushare") == "DCE"
        assert denormalize_exchange("CZCE", "tushare") == "ZCE"
        assert denormalize_exchange("CFFEX", "tushare") == "CFX"
        assert denormalize_exchange("INE", "tushare") == "INE"
        assert denormalize_exchange("SHSE", "tushare") == "SH"
        assert denormalize_exchange("SZSE", "tushare") == "SZ"

    def test_denormalize_goldminer(self):
        """测试转换为GoldMiner格式"""
        assert denormalize_exchange("SHFE", "goldminer") == "SHFE"
        assert denormalize_exchange("DCE", "goldminer") == "DCE"
        assert denormalize_exchange("CZCE", "goldminer") == "CZCE"
        assert denormalize_exchange("SHSE", "goldminer") == "SHSE"
        assert denormalize_exchange("SZSE", "goldminer") == "SZSE"

    def test_denormalize_vnpy(self):
        """测试转换为VNPy格式"""
        assert denormalize_exchange("SHFE", "vnpy") == "SHFE"
        assert denormalize_exchange("DCE", "vnpy") == "DCE"
        assert denormalize_exchange("CZCE", "vnpy") == "CZCE"
        assert denormalize_exchange("SHSE", "vnpy") == "SSE"
        assert denormalize_exchange("SZSE", "vnpy") == "SZSE"

    def test_denormalize_invalid_source(self):
        """测试无效数据源"""
        with pytest.raises(ValueError):
            denormalize_exchange("SHFE", "invalid_source")


class TestExchangeTypeCheck:
    """测试交易所类型判断"""

    def test_is_futures_exchange(self):
        """测试期货交易所判断"""
        # 期货交易所
        assert is_futures_exchange("SHFE") is True
        assert is_futures_exchange("DCE") is True
        assert is_futures_exchange("CZCE") is True
        assert is_futures_exchange("CFFEX") is True
        assert is_futures_exchange("INE") is True
        assert is_futures_exchange("GFEX") is True

        # 股票交易所
        assert is_futures_exchange("SHSE") is False
        assert is_futures_exchange("SZSE") is False
        assert is_futures_exchange("BSE") is False

    def test_is_stock_exchange(self):
        """测试股票交易所判断"""
        # 股票交易所
        assert is_stock_exchange("SHSE") is True
        assert is_stock_exchange("SZSE") is True
        assert is_stock_exchange("BSE") is True

        # 期货交易所
        assert is_stock_exchange("SHFE") is False
        assert is_stock_exchange("DCE") is False
        assert is_stock_exchange("CZCE") is False


class TestGetExchangeInfo:
    """测试交易所信息查询"""

    def test_get_futures_exchange_info(self):
        """测试期货交易所信息"""
        info = get_exchange_info("SHFE")
        assert info is not None
        assert info["name"] == "上海期货交易所"
        assert info["type"] == ExchangeType.FUTURES
        assert "SHFE" in info["aliases"]

        info = get_exchange_info("CZCE")
        assert info is not None
        assert info["name"] == "郑州商品交易所"
        assert info["type"] == ExchangeType.FUTURES

    def test_get_stock_exchange_info(self):
        """测试股票交易所信息"""
        info = get_exchange_info("SHSE")
        assert info is not None
        assert info["name"] == "上海证券交易所"
        assert info["type"] == ExchangeType.STOCK
        assert "SSE" in info["aliases"]

        info = get_exchange_info("SZSE")
        assert info is not None
        assert info["name"] == "深圳证券交易所"
        assert info["type"] == ExchangeType.STOCK

    def test_get_invalid_exchange_info(self):
        """测试无效交易所信息查询"""
        info = get_exchange_info("INVALID")
        assert info is None


class TestValidateExchanges:
    """测试交易所验证"""

    def test_validate_single_exchange(self):
        """测试单个交易所验证"""
        assert validate_exchanges("SHFE") is True
        assert validate_exchanges("SHSE") is True
        assert validate_exchanges("INVALID") is False

    def test_validate_multiple_exchanges(self):
        """测试多个交易所验证"""
        # 所有有效
        assert validate_exchanges(["SHFE", "DCE", "CZCE"]) is True

        # 包含无效
        assert validate_exchanges(["SHFE", "INVALID", "CZCE"]) is False

    def test_validate_with_type_filter(self):
        """测试带类型过滤的验证"""
        # 只验证期货交易所
        assert validate_exchanges(
            ["SHFE", "DCE", "CZCE"],
            exchange_type=ExchangeType.FUTURES
        ) is True

        # 包含股票交易所
        assert validate_exchanges(
            ["SHFE", "SHSE"],
            exchange_type=ExchangeType.FUTURES
        ) is False


class TestConstants:
    """测试常量定义"""

    def test_standard_exchanges_complete(self):
        """测试标准交易所列表完整性"""
        assert "SHFE" in STANDARD_EXCHANGES
        assert "DCE" in STANDARD_EXCHANGES
        assert "CZCE" in STANDARD_EXCHANGES
        assert "CFFEX" in STANDARD_EXCHANGES
        assert "INE" in STANDARD_EXCHANGES
        assert "GFEX" in STANDARD_EXCHANGES
        assert "SHSE" in STANDARD_EXCHANGES
        assert "SZSE" in STANDARD_EXCHANGES
        assert "BSE" in STANDARD_EXCHANGES

    def test_futures_exchanges_set(self):
        """测试期货交易所集合"""
        assert "SHFE" in FUTURES_EXCHANGES
        assert "DCE" in FUTURES_EXCHANGES
        assert "CZCE" in FUTURES_EXCHANGES
        assert "CFFEX" in FUTURES_EXCHANGES
        assert "INE" in FUTURES_EXCHANGES
        assert "GFEX" in FUTURES_EXCHANGES
        # 股票交易所不应该在期货集合中
        assert "SHSE" not in FUTURES_EXCHANGES
        assert "SZSE" not in FUTURES_EXCHANGES

    def test_stock_exchanges_set(self):
        """测试股票交易所集合"""
        assert "SHSE" in STOCK_EXCHANGES
        assert "SZSE" in STOCK_EXCHANGES
        assert "BSE" in STOCK_EXCHANGES
        # 期货交易所不应该在股票集合中
        assert "SHFE" not in STOCK_EXCHANGES
        assert "DCE" not in STOCK_EXCHANGES


class TestCaseInsensitivity:
    """测试大小写不敏感"""

    def test_normalize_case_variations(self):
        """测试各种大小写变体"""
        # 全大写
        assert normalize_exchange("SHFE") == "SHFE"
        # 全小写
        assert normalize_exchange("shfe") == "SHFE"
        # 混合大小写
        assert normalize_exchange("ShFe") == "SHFE"
        assert normalize_exchange("sHfE") == "SHFE"

    def test_alias_case_variations(self):
        """测试别名的大小写变体"""
        # 上期所别名
        assert normalize_exchange("shf") == "SHFE"
        assert normalize_exchange("SHF") == "SHFE"
        # 郑商所别名
        assert normalize_exchange("zce") == "CZCE"
        assert normalize_exchange("ZCE") == "CZCE"


class TestEdgeCases:
    """测试边界条件"""

    def test_whitespace_handling(self):
        """测试空白字符处理"""
        assert normalize_exchange(" SHFE ") == "SHFE"
        assert normalize_exchange("\tDCE\n") == "DCE"

    def test_empty_input(self):
        """测试空输入"""
        with pytest.raises(ValueError):
            normalize_exchange("")

        with pytest.raises(ValueError):
            normalize_exchange("   ")

    def test_none_input(self):
        """测试None输入"""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            normalize_exchange(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
