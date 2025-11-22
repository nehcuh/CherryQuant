"""
Unit tests for contract_utils module

测试覆盖：
1. 合约代码解析 (parse_contract)
2. 合约代码格式转换 (format_contract)
3. 合约代码验证 (validate_contract)
4. 合约信息提取 (get_underlying, get_contract_month)
5. 特殊合约类型识别
6. 编码约定处理
"""
import pytest
from cherryquant.utils.contract_utils import (
    parse_contract,
    format_contract,
    format_contracts,
    validate_contract,
    split_contract,
    get_underlying,
    get_contract_month,
    is_main_contract,
    normalize_contract,
    ContractFormat,
    AssetType,
    ContractType,
    ContractInfo,
    EncodingConvention,
)


class TestParseContract:
    """测试合约代码解析"""

    def test_parse_futures_contract_standard_format(self):
        """测试标准格式期货合约解析"""
        # 上期所 - 小写品种代码
        info = parse_contract("SHFE.rb2501")
        assert info.exchange == "SHFE"
        assert info.symbol == "rb2501"
        assert info.underlying == "rb"
        assert info.year == 2025
        assert info.month == 1
        assert info.asset_type == AssetType.FUTURES
        assert info.contract_type == ContractType.REGULAR

        # 郑商所 - 大写品种代码
        info = parse_contract("CZCE.SR2501")
        assert info.exchange == "CZCE"
        assert info.symbol == "SR2501"
        assert info.underlying == "SR"
        assert info.year == 2025
        assert info.month == 1

    def test_parse_futures_contract_tushare_format(self):
        """测试Tushare格式期货合约解析"""
        # RB2501.SHF 格式
        info = parse_contract("RB2501.SHF")
        assert info.exchange == "SHFE"
        assert info.symbol == "rb2501"
        assert info.underlying == "rb"
        assert info.year == 2025
        assert info.month == 1

        # SR2501.ZCE 格式
        info = parse_contract("SR2501.ZCE")
        assert info.exchange == "CZCE"
        assert info.symbol == "SR2501"
        assert info.underlying == "SR"

    def test_parse_futures_contract_vnpy_format(self):
        """测试VNPy格式期货合约解析"""
        info = parse_contract("RB2501.SHFE")
        assert info.exchange == "SHFE"
        assert info.symbol == "rb2501"
        assert info.underlying == "rb"

    def test_parse_futures_with_default_exchange(self):
        """测试使用默认交易所解析"""
        info = parse_contract("rb2501", default_exchange="SHFE")
        assert info.exchange == "SHFE"
        assert info.symbol == "rb2501"
        assert info.underlying == "rb"

    def test_parse_stock_contract_standard_format(self):
        """测试股票合约解析 - 标准格式"""
        # 上交所
        info = parse_contract("SHSE.600000")
        assert info.exchange == "SHSE"
        assert info.symbol == "600000"
        assert info.asset_type == AssetType.STOCK
        assert info.contract_type == ContractType.REGULAR

        # 深交所
        info = parse_contract("SZSE.000001")
        assert info.exchange == "SZSE"
        assert info.symbol == "000001"
        assert info.asset_type == AssetType.STOCK

    def test_parse_stock_contract_tushare_format(self):
        """测试股票合约解析 - Tushare格式"""
        info = parse_contract("600000.SH")
        assert info.exchange == "SHSE"
        assert info.symbol == "600000"
        assert info.asset_type == AssetType.STOCK

        info = parse_contract("000001.SZ")
        assert info.exchange == "SZSE"
        assert info.symbol == "000001"

    def test_parse_index_contract(self):
        """测试指数代码解析"""
        # 上证指数
        info = parse_contract("SHSE.000001")
        assert info.exchange == "SHSE"
        assert info.symbol == "000001"
        assert info.asset_type == AssetType.INDEX

        # 深证成指
        info = parse_contract("SZSE.399001")
        assert info.exchange == "SZSE"
        assert info.symbol == "399001"
        assert info.asset_type == AssetType.INDEX

    def test_parse_invalid_contract(self):
        """测试无效合约代码"""
        with pytest.raises(ValueError):
            parse_contract("")

        with pytest.raises(ValueError):
            parse_contract("INVALID")

        with pytest.raises(ValueError):
            parse_contract("rb2501")  # 缺少交易所且无默认交易所


class TestSpecialContractTypes:
    """测试特殊合约类型"""

    def test_parse_main_contract(self):
        """测试主力合约"""
        info = parse_contract("SHFE.rb888")
        assert info.contract_type == ContractType.MAIN
        assert info.underlying == "rb"
        assert info.year is None
        assert info.month is None

        info = parse_contract("SHFE.rb000")
        assert info.contract_type == ContractType.MAIN

    def test_parse_weighted_contract(self):
        """测试加权合约"""
        info = parse_contract("SHFE.rb99")
        assert info.contract_type == ContractType.WEIGHTED
        assert info.underlying == "rb"

    def test_parse_current_month_contract(self):
        """测试当月合约"""
        info = parse_contract("SHFE.rb00")
        assert info.contract_type == ContractType.CURRENT_MONTH

    def test_parse_next_month_contract(self):
        """测试下月合约"""
        info = parse_contract("SHFE.rb01")
        assert info.contract_type == ContractType.NEXT_MONTH

    def test_is_main_contract_helper(self):
        """测试is_main_contract辅助函数"""
        assert is_main_contract("SHFE.rb888") is True
        assert is_main_contract("SHFE.rb000") is True
        assert is_main_contract("SHFE.rb2501") is False


class TestFormatContract:
    """测试合约格式转换"""

    def test_format_to_standard(self):
        """测试转换为标准格式"""
        result = format_contract("RB2501.SHF", ContractFormat.STANDARD)
        assert result == "SHFE.rb2501"

        result = format_contract("SR2501.ZCE", ContractFormat.STANDARD)
        assert result == "CZCE.SR2501"

    def test_format_to_tushare(self):
        """测试转换为Tushare格式"""
        result = format_contract("SHFE.rb2501", ContractFormat.TUSHARE)
        assert result == "RB2501.SHF"

        result = format_contract("CZCE.SR2501", ContractFormat.TUSHARE)
        assert result == "SR2501.ZCE"

        result = format_contract("SHSE.600000", ContractFormat.TUSHARE)
        assert result == "600000.SH"

    def test_format_to_goldminer(self):
        """测试转换为GoldMiner格式"""
        result = format_contract("SHFE.rb2501", ContractFormat.GOLDMINER)
        assert result == "SHFE.rb2501"

        result = format_contract("CZCE.SR2501", ContractFormat.GOLDMINER)
        # 郑商所转换为3位年月格式
        assert result == "CZCE.SR501"

    def test_format_to_vnpy(self):
        """测试转换为VNPy格式"""
        result = format_contract("SHFE.rb2501", ContractFormat.VNPy)
        assert result == "RB2501.SHFE"

        result = format_contract("SHSE.600000", ContractFormat.VNPy)
        assert result == "600000.SSE"

    def test_format_to_plain(self):
        """测试转换为纯代码格式"""
        result = format_contract("SHFE.rb2501", ContractFormat.PLAIN)
        assert result == "rb2501"

        result = format_contract("SHSE.600000", ContractFormat.PLAIN)
        assert result == "600000"

    def test_format_contracts_batch(self):
        """测试批量格式转换"""
        contracts = ["SHFE.rb2501", "CZCE.SR2501", "SHSE.600000"]
        results = format_contracts(contracts, ContractFormat.TUSHARE)
        assert len(results) == 3
        assert "RB2501.SHF" in results
        assert "SR2501.ZCE" in results
        assert "600000.SH" in results

    def test_format_contracts_from_string(self):
        """测试从逗号分隔字符串批量转换"""
        contracts = "SHFE.rb2501, CZCE.SR2501, SHSE.600000"
        results = format_contracts(contracts, ContractFormat.TUSHARE)
        assert len(results) == 3


class TestEncodingConvention:
    """测试编码约定"""

    def test_get_case_rule(self):
        """测试获取大小写规则"""
        assert EncodingConvention.get_case_rule("SHFE") == "lowercase"
        assert EncodingConvention.get_case_rule("DCE") == "lowercase"
        assert EncodingConvention.get_case_rule("CZCE") == "uppercase"
        assert EncodingConvention.get_case_rule("CFFEX") == "uppercase"

    def test_apply_case_rule(self):
        """测试应用大小写规则"""
        # 上期所 - 小写
        assert EncodingConvention.apply_case_rule("RB", "SHFE") == "rb"
        # 郑商所 - 大写
        assert EncodingConvention.apply_case_rule("sr", "CZCE") == "SR"
        # 中金所 - 大写
        assert EncodingConvention.apply_case_rule("if", "CFFEX") == "IF"

    def test_detect_contract_type(self):
        """测试合约类型检测"""
        assert EncodingConvention.detect_contract_type("2501") == ContractType.REGULAR
        assert EncodingConvention.detect_contract_type("888") == ContractType.MAIN
        assert EncodingConvention.detect_contract_type("000") == ContractType.MAIN
        assert EncodingConvention.detect_contract_type("99") == ContractType.WEIGHTED
        assert EncodingConvention.detect_contract_type("00") == ContractType.CURRENT_MONTH
        assert EncodingConvention.detect_contract_type("01") == ContractType.NEXT_MONTH

    def test_normalize_czce_year(self):
        """测试郑商所年份推断"""
        # 假设当前年份为2024
        year = EncodingConvention.normalize_czce_year("501")
        # 501 -> 2025年01月
        assert year == 2025

        year = EncodingConvention.normalize_czce_year("312")
        # 312 -> 2023年12月
        assert year == 2023


class TestContractInfo:
    """测试ContractInfo类"""

    def test_to_standard(self):
        """测试转换为标准格式"""
        info = ContractInfo(
            exchange="SHFE",
            symbol="rb2501",
            asset_type=AssetType.FUTURES,
            underlying="rb",
            year=2025,
            month=1,
            contract_type=ContractType.REGULAR,
        )
        assert info.to_standard() == "SHFE.rb2501"

    def test_is_futures(self):
        """测试期货判断"""
        info = ContractInfo(
            exchange="SHFE",
            symbol="rb2501",
            asset_type=AssetType.FUTURES,
        )
        assert info.is_futures() is True
        assert info.is_stock() is False

    def test_is_regular_contract(self):
        """测试普通合约判断"""
        info = ContractInfo(
            exchange="SHFE",
            symbol="rb2501",
            asset_type=AssetType.FUTURES,
            contract_type=ContractType.REGULAR,
        )
        assert info.is_regular_contract() is True
        assert info.is_main_contract() is False


class TestValidateContract:
    """测试合约验证"""

    def test_validate_valid_contracts(self):
        """测试有效合约验证"""
        assert validate_contract("SHFE.rb2501") is True
        assert validate_contract("CZCE.SR2501") is True
        assert validate_contract("SHSE.600000") is True

    def test_validate_invalid_contracts(self):
        """测试无效合约验证"""
        assert validate_contract("INVALID") is False
        assert validate_contract("") is False
        assert validate_contract("rb2501") is False  # 缺少交易所

    def test_validate_with_exchange_filter(self):
        """测试带交易所过滤的验证"""
        assert validate_contract("SHFE.rb2501", exchange="SHFE") is True
        assert validate_contract("SHFE.rb2501", exchange="DCE") is False

    def test_validate_with_asset_type_filter(self):
        """测试带资产类型过滤的验证"""
        assert validate_contract(
            "SHFE.rb2501",
            asset_type=AssetType.FUTURES
        ) is True
        assert validate_contract(
            "SHFE.rb2501",
            asset_type=AssetType.STOCK
        ) is False


class TestHelperFunctions:
    """测试辅助函数"""

    def test_split_contract(self):
        """测试分离交易所和代码"""
        exchange, symbol = split_contract("SHFE.rb2501")
        assert exchange == "SHFE"
        assert symbol == "rb2501"

    def test_get_underlying(self):
        """测试获取标的品种"""
        assert get_underlying("SHFE.rb2501") == "rb"
        assert get_underlying("CZCE.SR2501") == "SR"
        assert get_underlying("SHSE.600000") is None  # 股票没有标的

    def test_get_contract_month(self):
        """测试获取合约年月"""
        year, month = get_contract_month("SHFE.rb2501")
        assert year == 2025
        assert month == 1

        year, month = get_contract_month("CZCE.SR2512")
        assert year == 2025
        assert month == 12

        # 特殊合约没有年月
        assert get_contract_month("SHFE.rb888") is None

    def test_normalize_contract(self):
        """测试合约标准化"""
        assert normalize_contract("RB2501.SHF") == "SHFE.rb2501"
        assert normalize_contract("SR2501.ZCE") == "CZCE.SR2501"
        assert normalize_contract("600000.SH") == "SHSE.600000"


class TestEdgeCases:
    """测试边界条件"""

    def test_different_month_formats(self):
        """测试不同月份格式"""
        # 01-12月
        for month in range(1, 13):
            contract = f"SHFE.rb25{month:02d}"
            info = parse_contract(contract)
            assert info.month == month

    def test_year_boundary(self):
        """测试年份边界"""
        # 2000-2099年
        for year in [2000, 2024, 2050, 2099]:
            yy = year % 100
            contract = f"SHFE.rb{yy:02d}01"
            info = parse_contract(contract)
            assert info.year == year

    def test_exchange_case_variations(self):
        """测试交易所大小写变体"""
        # 应该都能正确解析
        assert parse_contract("shfe.rb2501").exchange == "SHFE"
        assert parse_contract("SHFE.rb2501").exchange == "SHFE"
        assert parse_contract("ShFe.rb2501").exchange == "SHFE"

    def test_symbol_case_variations(self):
        """测试品种代码大小写变体"""
        # 上期所品种应该转为小写
        info = parse_contract("SHFE.RB2501")
        assert info.symbol == "rb2501"

        # 郑商所品种应该转为大写
        info = parse_contract("CZCE.sr2501")
        assert info.symbol == "SR2501"

    def test_whitespace_handling(self):
        """测试空白字符处理"""
        info = parse_contract(" SHFE.rb2501 ")
        assert info.exchange == "SHFE"
        assert info.symbol == "rb2501"


class TestRealWorldExamples:
    """测试真实世界的合约代码"""

    def test_common_futures_contracts(self):
        """测试常见期货合约"""
        test_cases = [
            ("SHFE.rb2501", "rb", 2025, 1),  # 螺纹钢
            ("SHFE.hc2501", "hc", 2025, 1),  # 热卷
            ("DCE.i2501", "i", 2025, 1),     # 铁矿石
            ("DCE.m2501", "m", 2025, 1),     # 豆粕
            ("CZCE.SR2501", "SR", 2025, 1),  # 白糖
            ("CZCE.TA2501", "TA", 2025, 1),  # PTA
            ("CFFEX.IF2501", "IF", 2025, 1), # 沪深300
            ("INE.sc2501", "sc", 2025, 1),   # 原油
        ]

        for contract, underlying, year, month in test_cases:
            info = parse_contract(contract)
            assert info.underlying == underlying
            assert info.year == year
            assert info.month == month

    def test_common_stock_codes(self):
        """测试常见股票代码"""
        test_cases = [
            ("SHSE.600000", "600000", AssetType.STOCK),  # 浦发银行
            ("SHSE.600519", "600519", AssetType.STOCK),  # 茅台
            ("SHSE.688001", "688001", AssetType.STOCK),  # 科创板
            ("SZSE.000001", "000001", AssetType.STOCK),  # 平安银行
            ("SZSE.000002", "000002", AssetType.STOCK),  # 万科A
            ("SZSE.300001", "300001", AssetType.STOCK),  # 创业板
        ]

        for contract, symbol, asset_type in test_cases:
            info = parse_contract(contract)
            assert info.symbol == symbol
            assert info.asset_type == asset_type


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
