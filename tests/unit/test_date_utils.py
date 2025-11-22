"""
Unit tests for date_utils module

测试覆盖：
1. 日期格式转换 (date_to_int, int_to_date_str, date_to_str)
2. 交易日查询 (is_trade_date, get_pre_trade_date, get_next_trade_date)
3. 交易日历范围查询 (get_trade_calendar)
4. 边界条件和异常处理
"""
import pytest
from datetime import datetime, date
from cherryquant.utils.date_utils import (
    date_to_int,
    int_to_date_str,
    date_to_str,
    DateLike,
)


class TestDateConversion:
    """测试日期转换函数"""

    def test_date_to_int_from_string(self):
        """测试字符串日期转整数"""
        # YYYY-MM-DD 格式
        assert date_to_int("2024-01-26") == 20240126
        assert date_to_int("2025-12-31") == 20251231

        # YYYYMMDD 格式
        assert date_to_int("20240126") == 20240126

    def test_date_to_int_from_int(self):
        """测试整数日期保持不变"""
        assert date_to_int(20240126) == 20240126
        assert date_to_int(20251231) == 20251231

    def test_date_to_int_from_datetime(self):
        """测试datetime对象转整数"""
        dt = datetime(2024, 1, 26)
        assert date_to_int(dt) == 20240126

        dt = datetime(2024, 1, 26, 15, 30, 45)
        assert date_to_int(dt) == 20240126

    def test_date_to_int_from_date(self):
        """测试date对象转整数"""
        d = date(2024, 1, 26)
        assert date_to_int(d) == 20240126

    def test_date_to_int_none(self):
        """测试None返回今天日期"""
        result = date_to_int(None)
        expected = int(datetime.now().strftime("%Y%m%d"))
        assert result == expected

    def test_date_to_int_invalid(self):
        """测试无效日期格式"""
        with pytest.raises(ValueError):
            date_to_int("invalid")

        with pytest.raises(ValueError):
            date_to_int("2024-13-01")  # 无效月份

        with pytest.raises(ValueError):
            date_to_int("2024-01-32")  # 无效日期

    def test_int_to_date_str(self):
        """测试整数转日期字符串"""
        date_str = int_to_date_str(20240126)
        assert date_str == "2024-01-26"

        date_str = int_to_date_str(20251231)
        assert date_str == "2025-12-31"

    def test_date_to_str(self):
        """测试日期转字符串"""
        # 默认格式
        result = date_to_str("2024-01-26")
        assert result == "2024-01-26"

        result = date_to_str(20240126)
        assert result == "2024-01-26"

        result = date_to_str(datetime(2024, 1, 26))
        assert result == "2024-01-26"


class TestEdgeCases:
    """测试边界条件"""

    def test_leap_year(self):
        """测试闰年日期"""
        # 2024是闰年
        assert date_to_int("2024-02-29") == 20240229

        # 2023不是闰年 - 会抛出异常
        with pytest.raises(ValueError):
            date_to_int("2023-02-29")

    def test_year_2000_boundary(self):
        """测试2000年边界"""
        assert date_to_int("1999-12-31") == 19991231
        assert date_to_int("2000-01-01") == 20000101

    def test_century_boundary(self):
        """测试世纪边界"""
        assert date_to_int("2099-12-31") == 20991231
        assert date_to_int("2100-01-01") == 21000101

    def test_empty_string(self):
        """测试空字符串"""
        with pytest.raises(ValueError):
            date_to_int("")

        with pytest.raises(ValueError):
            date_to_int("   ")

    def test_special_dates(self):
        """测试特殊日期（月末、季末、年末）"""
        # 月末
        assert date_to_int("2024-01-31") == 20240131
        assert date_to_int("2024-04-30") == 20240430

        # 季末
        assert date_to_int("2024-03-31") == 20240331
        assert date_to_int("2024-06-30") == 20240630
        assert date_to_int("2024-09-30") == 20240930
        assert date_to_int("2024-12-31") == 20241231


# 注意：交易日查询测试需要MongoDB连接，这里提供测试框架
# 实际测试需要在集成测试中进行

class TestTradeDateMock:
    """交易日查询测试（Mock版本，不需要实际数据库）"""

    def test_trade_date_signature(self):
        """测试交易日查询函数签名是否正确"""
        from cherryquant.utils.date_utils import (
            is_trade_date,
            get_pre_trade_date,
            get_next_trade_date,
            get_trade_calendar,
        )

        # 这些函数应该可以导入
        assert callable(is_trade_date)
        assert callable(get_pre_trade_date)
        assert callable(get_next_trade_date)
        assert callable(get_trade_calendar)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
