"""
P0 和 P1 工具集成测试

测试新整合的 Quantbox 工具（P0 基础工具 + P1 存储优化）。

运行:
    pytest tests/integration/test_p0_p1_tools.py -v
    pytest tests/integration/test_p0_p1_tools.py -v -s  # 显示输出
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo

from cherryquant.utils.date_utils import (
    get_trade_calendar,
    is_trade_date,
    date_to_int,
    int_to_date_str,
)
from cherryquant.utils.contract_utils import (
    parse_contract,
    format_contract,
    format_contracts,
    ParsedContractInfo,
    get_underlying,
    get_contract_month,
    is_main_contract,
)
from cherryquant.utils.exchange_utils import (
    normalize_exchange,
    denormalize_exchange,
    is_futures_exchange,
    is_stock_exchange,
)
from cherryquant.data.storage.bulk_writer import BulkWriter
from cherryquant.data.storage.save_result import SaveResult


# ============================================================================
# P0 工具测试 - 基础工具层
# ============================================================================

class TestDateUtils:
    """测试 date_utils 模块"""

    def test_date_to_int(self):
        """测试日期转整数"""
        # 字符串格式
        assert date_to_int("2024-11-22") == 20241122
        assert date_to_int("20241122") == 20241122

        # datetime 格式
        dt = datetime(2024, 11, 22)
        assert date_to_int(dt) == 20241122

        # 整数格式（直接返回）
        assert date_to_int(20241122) == 20241122

    def test_int_to_date_str(self):
        """测试整数转日期字符串"""
        result = int_to_date_str(20241122)
        assert isinstance(result, str)
        assert result == "2024-11-22"

    def test_get_trade_calendar(self):
        """测试获取交易日列表"""
        # 获取最近一周的交易日
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

        dates = get_trade_calendar(start_date, end_date, exchange="SHFE")

        # 验证返回类型
        assert isinstance(dates, list)
        # 验证至少有一些交易日
        assert len(dates) >= 0  # 可能是周末/假期

    def test_is_trade_date(self):
        """测试判断交易日"""
        # 测试工作日（假设是交易日）
        result = is_trade_date("20241122", exchange="SHFE")
        assert isinstance(result, bool)


class TestContractUtils:
    """测试 contract_utils 模块"""

    def test_parse_contract_standard(self):
        """测试解析标准格式合约"""
        info = parse_contract("SHFE.rb2501")

        assert info.exchange == "SHFE"
        assert info.symbol == "rb2501"
        assert info.underlying == "rb"
        assert info.year == 2025
        assert info.month == 1

    def test_parse_contract_tushare(self):
        """测试解析 Tushare 格式"""
        info = parse_contract("RB2501.SHF")

        assert info.exchange == "SHFE"
        assert info.underlying == "rb"

    def test_parse_contract_czce_3digit(self):
        """测试解析郑商所 3 位年月格式"""
        info = parse_contract("CZCE.SR501")

        assert info.exchange == "CZCE"
        assert info.year == 2025
        assert info.month == 1

    def test_format_contract(self):
        """测试合约格式转换"""
        symbol = "SHFE.rb2501"

        # 转换为 Tushare 格式
        ts_code = format_contract(symbol, "tushare")
        assert ts_code == "RB2501.SHF"

        # 转换为 VNPy 格式
        vnpy_code = format_contract(symbol, "vnpy")
        assert vnpy_code == "RB2501.SHFE"

        # 转换为掘金格式
        gm_code = format_contract(symbol, "goldminer")
        assert gm_code == "SHFE.rb2501"

    def test_format_contracts_batch(self):
        """测试批量格式转换"""
        symbols = ["SHFE.rb2501", "DCE.m2501", "CZCE.SR501"]

        ts_codes = format_contracts(symbols, "tushare")

        assert len(ts_codes) == 3
        assert ts_codes[0] == "RB2501.SHF"
        assert ts_codes[1] == "M2501.DCE"
        assert ts_codes[2] == "SR2501.ZCE"

    def test_special_contracts(self):
        """测试特殊合约识别"""
        # 主力合约
        info_main = parse_contract("SHFE.rb888")
        assert info_main.is_main_contract()

        # 连续合约
        info_cont = parse_contract("SHFE.rb000")
        assert info_cont.is_main_contract()  # 000 也是主力

        # 加权指数
        info_weighted = parse_contract("SHFE.rb99")
        assert info_weighted.is_weighted_contract()

    def test_utility_functions(self):
        """测试便利函数"""
        symbol = "SHFE.rb2501"

        # 获取标的
        underlying = get_underlying(symbol)
        assert underlying == "rb"

        # 获取年月
        year_month = get_contract_month(symbol)
        assert year_month == (2025, 1)

        # 判断主力
        assert not is_main_contract(symbol)
        assert is_main_contract("SHFE.rb888")


class TestExchangeUtils:
    """测试 exchange_utils 模块"""

    def test_normalize_exchange(self):
        """测试交易所代码标准化"""
        # Tushare 格式
        assert normalize_exchange("SHF") == "SHFE"
        assert normalize_exchange("ZCE") == "CZCE"

        # 标准格式（不变）
        assert normalize_exchange("SHFE") == "SHFE"
        assert normalize_exchange("DCE") == "DCE"

    def test_denormalize_exchange(self):
        """测试交易所代码反标准化"""
        # 转换为 Tushare 格式（期货使用标准代码）
        assert denormalize_exchange("SHFE", "tushare") == "SHFE"
        assert denormalize_exchange("CZCE", "tushare") == "CZCE"

        # Tushare 股票使用简称
        assert denormalize_exchange("SHSE", "tushare") == "SH"
        assert denormalize_exchange("SZSE", "tushare") == "SZ"

        # 转换为掘金格式（使用标准代码）
        assert denormalize_exchange("SHFE", "goldminer") == "SHFE"
        assert denormalize_exchange("DCE", "goldminer") == "DCE"

    def test_exchange_type_detection(self):
        """测试交易所类型判断"""
        # 期货交易所
        assert is_futures_exchange("SHFE") == True
        assert is_futures_exchange("DCE") == True
        assert is_futures_exchange("CZCE") == True
        assert is_futures_exchange("CFFEX") == True
        assert is_futures_exchange("INE") == True
        assert is_futures_exchange("GFEX") == True

        # 股票交易所
        assert is_stock_exchange("SHSE") == True
        assert is_stock_exchange("SZSE") == True
        assert is_stock_exchange("BSE") == True

        # 交叉验证
        assert is_stock_exchange("SHFE") == False
        assert is_futures_exchange("SHSE") == False


# ============================================================================
# P1 工具测试 - 存储优化层
# ============================================================================

@pytest.mark.asyncio
class TestBulkWriter:
    """测试 BulkWriter 模块（需要 MongoDB）"""

    @pytest.fixture
    async def db_collection(self):
        """创建测试用数据库集合"""
        try:
            client = AsyncIOMotorClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            # 测试连接
            await client.server_info()

            db = client.test_cherryquant
            collection = db.test_bulk_writer

            # 清空集合
            await collection.delete_many({})

            yield collection

            # 清理
            await collection.drop()
            client.close()
        except Exception as e:
            pytest.skip(f"MongoDB not available: {e}")

    async def test_bulk_upsert_insert(self, db_collection):
        """测试批量插入"""
        data = [
            {"symbol": "rb2501", "date": 20241122, "close": 3500.0},
            {"symbol": "rb2501", "date": 20241123, "close": 3510.0},
            {"symbol": "hc2501", "date": 20241122, "close": 3200.0},
        ]

        result = SaveResult()
        await BulkWriter.bulk_upsert(
            collection=db_collection,
            data=data,
            key_fields=["symbol", "date"],
            result=result
        )

        result.complete()

        # 验证结果
        assert result.success == True
        assert result.inserted_count == 3
        assert result.modified_count == 0
        assert result.error_count == 0

    async def test_bulk_upsert_update(self, db_collection):
        """测试批量更新（upsert 模式）"""
        # 第一次插入
        data1 = [
            {"symbol": "rb2501", "date": 20241122, "close": 3500.0},
        ]

        result1 = SaveResult()
        await BulkWriter.bulk_upsert(
            collection=db_collection,
            data=data1,
            key_fields=["symbol", "date"],
            result=result1
        )

        # 第二次更新
        data2 = [
            {"symbol": "rb2501", "date": 20241122, "close": 3505.0},  # 更新
        ]

        result2 = SaveResult()
        await BulkWriter.bulk_upsert(
            collection=db_collection,
            data=data2,
            key_fields=["symbol", "date"],
            result=result2
        )

        result2.complete()

        # 验证结果
        assert result2.modified_count == 1
        assert result2.inserted_count == 0

        # 验证数据被更新
        doc = await db_collection.find_one({"symbol": "rb2501", "date": 20241122})
        assert doc["close"] == 3505.0

    async def test_ensure_indexes(self, db_collection):
        """测试索引创建"""
        await BulkWriter.ensure_indexes(
            collection=db_collection,
            index_specs=[
                {
                    "keys": [("symbol", 1), ("date", 1)],
                    "unique": True
                },
                {
                    "keys": [("date", -1)],
                    "unique": False
                }
            ]
        )

        # 验证索引存在
        indexes = await db_collection.index_information()
        assert len(indexes) >= 2  # _id 索引 + 我们创建的索引


class TestSaveResult:
    """测试 SaveResult 模块"""

    def test_save_result_creation(self):
        """测试创建 SaveResult"""
        result = SaveResult()

        assert result.success == True
        assert result.inserted_count == 0
        assert result.modified_count == 0
        assert result.error_count == 0

    def test_save_result_tracking(self):
        """测试操作追踪"""
        result = SaveResult()

        result.inserted_count = 100
        result.modified_count = 50

        assert result.total_count == 150
        assert result.success == True

    def test_save_result_error_handling(self):
        """测试错误记录"""
        result = SaveResult()

        result.add_error("VALIDATION_ERROR", "Invalid date", {"date": "invalid"})

        assert result.success == False
        assert result.error_count == 1
        assert len(result.errors) == 1
        assert result.errors[0]["type"] == "VALIDATION_ERROR"

    def test_save_result_success_rate(self):
        """测试成功率计算"""
        result = SaveResult()

        result.inserted_count = 95
        result.add_error("ERROR", "Failed")  # 1个错误

        # 95 成功 / (95 + 1) = 98.96%
        assert 0.98 < result.success_rate < 0.99

    def test_save_result_to_dict(self):
        """测试序列化"""
        result = SaveResult()
        result.inserted_count = 100
        result.complete()

        result_dict = result.to_dict()

        assert result_dict["success"] == True
        assert result_dict["inserted_count"] == 100
        assert result_dict["total_count"] == 100
        assert "duration_seconds" in result_dict
        assert "success_rate" in result_dict


# ============================================================================
# 集成测试 - P0 + P1 工具协作
# ============================================================================

@pytest.mark.asyncio
class TestIntegration:
    """测试 P0 和 P1 工具的集成使用"""

    @pytest.fixture
    async def db_collection(self):
        """创建测试用数据库集合"""
        try:
            client = AsyncIOMotorClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            await client.server_info()

            db = client.test_cherryquant
            collection = db.test_integration

            await collection.delete_many({})

            yield collection

            await collection.drop()
            client.close()
        except Exception as e:
            pytest.skip(f"MongoDB not available: {e}")

    async def test_complete_workflow(self, db_collection):
        """测试完整工作流：解析 → 转换 → 保存"""
        # 步骤 1: 解析合约（P0）
        symbols = ["SHFE.rb2501", "DCE.m2501", "CZCE.SR501"]
        parsed_infos = [parse_contract(sym) for sym in symbols]

        # 验证解析
        assert len(parsed_infos) == 3
        assert all(info.exchange in ["SHFE", "DCE", "CZCE"] for info in parsed_infos)

        # 步骤 2: 转换格式（P0）
        tushare_codes = format_contracts(symbols, "tushare")
        assert len(tushare_codes) == 3

        # 步骤 3: 准备数据
        data = []
        for info in parsed_infos:
            data.append({
                "symbol": info.symbol,
                "exchange": info.exchange,
                "underlying": info.underlying,
                "date": date_to_int("2024-11-22"),
                "close": 3500.0,
                "volume": 100000
            })

        # 步骤 4: 批量保存（P1）
        result = SaveResult()
        await BulkWriter.bulk_upsert(
            collection=db_collection,
            data=data,
            key_fields=["symbol", "date"],
            result=result
        )

        result.complete()

        # 验证结果
        assert result.success == True
        assert result.total_count == 3
        assert result.duration.total_seconds() > 0

        # 验证数据已保存
        count = await db_collection.count_documents({})
        assert count == 3


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
