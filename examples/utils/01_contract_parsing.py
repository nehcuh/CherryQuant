"""
合约代码解析示例 - Quantbox 工具整合

演示如何使用 contract_utils 解析和转换合约代码，
支持多种数据源格式（掘金、Tushare、VNPy等）。

运行: python examples/utils/01_contract_parsing.py
"""

from cherryquant.utils.contract_utils import (
    parse_contract,
    format_contract,
    format_contracts,
    ParsedContractInfo,
    normalize_contract,
    get_underlying,
    get_contract_month,
    is_main_contract,
)


def example_1_basic_parsing():
    """示例1: 基础解析"""
    print("=" * 70)
    print("示例1: 基础合约代码解析")
    print("=" * 70)

    # 解析标准格式
    info = parse_contract("SHFE.rb2501")
    print(f"\n输入: SHFE.rb2501")
    print(f"  交易所: {info.exchange}")
    print(f"  代码: {info.symbol}")
    print(f"  标的: {info.underlying}")
    print(f"  年月: {info.year}年{info.month}月")
    print(f"  类型: {info.asset_type.value}")

    # 解析 Tushare 格式
    info2 = parse_contract("RB2501.SHF")
    print(f"\n输入: RB2501.SHF (Tushare格式)")
    print(f"  标准格式: {info2.to_standard()}")  # SHFE.rb2501

    # 解析郑商所 3 位年月格式
    info3 = parse_contract("CZCE.SR501")
    print(f"\n输入: CZCE.SR501 (郑商所3位年月)")
    print(f"  标准格式: {info3.to_standard()}")  # CZCE.SR2501
    print(f"  年月: {info3.year}年{info3.month}月")  # 2025年1月


def example_2_format_conversion():
    """示例2: 格式转换"""
    print("\n" + "=" * 70)
    print("示例2: 多数据源格式转换")
    print("=" * 70)

    symbol = "SHFE.rb2501"

    # 转换为不同数据源格式
    formats = {
        "标准格式": format_contract(symbol, "standard"),
        "掘金格式": format_contract(symbol, "goldminer"),
        "Tushare格式": format_contract(symbol, "tushare"),
        "VNPy格式": format_contract(symbol, "vnpy"),
    }

    print(f"\n原始合约: {symbol}")
    for name, code in formats.items():
        print(f"  {name}: {code}")


def example_3_batch_conversion():
    """示例3: 批量转换"""
    print("\n" + "=" * 70)
    print("示例3: 批量合约转换")
    print("=" * 70)

    # 内部标准格式的合约列表
    contracts = [
        "SHFE.rb2501",
        "DCE.m2501",
        "CZCE.SR501",  # 郑商所3位年月
        "CFFEX.IF2501",
    ]

    print("\n转换为 Tushare 格式:")
    tushare_codes = format_contracts(contracts, "tushare")
    for std, ts in zip(contracts, tushare_codes):
        print(f"  {std:20s} → {ts}")

    print("\n转换为 VNPy 格式:")
    vnpy_codes = format_contracts(contracts, "vnpy")
    for std, vnpy in zip(contracts, vnpy_codes):
        print(f"  {std:20s} → {vnpy}")


def example_4_special_contracts():
    """示例4: 特殊合约类型"""
    print("\n" + "=" * 70)
    print("示例4: 特殊合约类型识别")
    print("=" * 70)

    special_contracts = {
        "SHFE.rb888": "主力合约",
        "SHFE.rb000": "连续合约",
        "SHFE.rb99": "加权指数",
        "SHFE.rb00": "当月合约",
        "SHFE.rb01": "下月合约",
    }

    print()
    for code, desc in special_contracts.items():
        info = parse_contract(code)
        print(f"{code:15s} - {desc:12s} - 类型: {info.contract_type.value}")


def example_5_utility_functions():
    """示例5: 便利函数"""
    print("\n" + "=" * 70)
    print("示例5: 便利函数使用")
    print("=" * 70)

    contracts = ["SHFE.rb2501", "SHFE.rb888", "CZCE.SR501"]

    print()
    for code in contracts:
        # 获取标的代码
        underlying = get_underlying(code)

        # 获取年月
        month_info = get_contract_month(code)

        # 判断是否主力
        is_main = is_main_contract(code)

        print(f"{code:15s}:")
        print(f"  标的: {underlying}")
        if month_info:
            year, month = month_info
            print(f"  年月: {year}年{month}月")
        else:
            print(f"  年月: (特殊合约)")
        print(f"  主力: {'是' if is_main else '否'}")


def example_6_real_world_usage():
    """示例6: 实际应用场景"""
    print("\n" + "=" * 70)
    print("示例6: 实际应用场景")
    print("=" * 70)

    print("\n场景1: 从 Tushare 采集数据前转换合约格式")
    print("-" * 50)

    def prepare_tushare_query(symbols):
        """准备 Tushare API 查询参数"""
        return [format_contract(sym, "tushare") for sym in symbols]

    internal_symbols = ["SHFE.rb2501", "DCE.m2501", "CZCE.SR501"]
    tushare_symbols = prepare_tushare_query(internal_symbols)

    print("内部格式:", internal_symbols)
    print("Tushare格式:", tushare_symbols)

    print("\n场景2: 判断合约是否临近到期")
    print("-" * 50)

    def is_near_expiry(symbol, target_year, target_month):
        """判断合约是否临近到期"""
        info = parse_contract(symbol)
        if info.year == target_year and info.month == target_month:
            return True
        return False

    test_symbols = ["SHFE.rb2412", "SHFE.rb2501", "SHFE.rb2502"]
    for sym in test_symbols:
        near = is_near_expiry(sym, 2024, 12)
        print(f"{sym}: {'临近到期' if near else '未到期'}")

    print("\n场景3: 从合约代码提取信息用于数据库查询")
    print("-" * 50)

    def build_query_filter(symbol):
        """构建数据库查询过滤器"""
        info = parse_contract(symbol)
        return {
            "exchange": info.exchange,
            "underlying": info.underlying,
            "year": info.year,
            "month": info.month,
        }

    query = build_query_filter("SHFE.rb2501")
    print(f"查询过滤器: {query}")


def main():
    """运行所有示例"""
    print("\n")
    print("🎯 " + "=" * 68)
    print("🎯  合约代码解析与转换示例 - Quantbox 工具整合")
    print("🎯 " + "=" * 68)

    example_1_basic_parsing()
    example_2_format_conversion()
    example_3_batch_conversion()
    example_4_special_contracts()
    example_5_utility_functions()
    example_6_real_world_usage()

    print("\n" + "=" * 70)
    print("✅ 所有示例运行完成!")
    print("=" * 70)
    print("\n📖 更多信息:")
    print("   - 文档: docs/quantbox_integration_p0.md")
    print("   - 迁移指南: docs/MIGRATION_GUIDE.md")
    print("   - 源代码: src/cherryquant/utils/contract_utils.py")
    print()


if __name__ == "__main__":
    main()
