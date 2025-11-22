"""
CherryQuant 常量定义
"""

# 品种代码与交易所映射
COMMODITY_EXCHANGE_MAP = {
    # 上海期货交易所 SHFE
    "cu": "SHFE",  # 铜
    "al": "SHFE",  # 铝
    "zn": "SHFE",  # 锌
    "pb": "SHFE",  # 铅
    "ni": "SHFE",  # 镍
    "sn": "SHFE",  # 锡
    "au": "SHFE",  # 黄金
    "ag": "SHFE",  # 白银
    "rb": "SHFE",  # 螺纹钢
    "hc": "SHFE",  # 热轧卷板
    "fu": "SHFE",  # 燃料油
    "bu": "SHFE",  # 沥青
    "ru": "SHFE",  # 橡胶
    "ss": "SHFE",  # 不锈钢
    "sp": "SHFE",  # 纸浆

    # 大连商品交易所 DCE
    "a": "DCE",    # 豆一
    "b": "DCE",    # 豆二
    "c": "DCE",    # 玉米
    "m": "DCE",    # 豆粕
    "y": "DCE",    # 豆油
    "p": "DCE",    # 棕榈油
    "i": "DCE",    # 铁矿石
    "j": "DCE",    # 焦炭
    "jm": "DCE",   # 焦煤
    "l": "DCE",    # 塑料
    "v": "DCE",    # PVC
    "pp": "DCE",   # 聚丙烯
    "eg": "DCE",   # 乙二醇
    "eb": "DCE",   # 苯乙烯
    "pg": "DCE",   # 液化石油气
    "lh": "DCE",   # 生猪
    "jd": "DCE",   # 鸡蛋
    "fb": "DCE",   # 纤维板
    "bb": "DCE",   # 胶合板
    "cs": "DCE",   # 玉米淀粉
    "rr": "DCE",   # 粳米

    # 郑州商品交易所 CZCE
    "sr": "CZCE",  # 白糖
    "cf": "CZCE",  # 棉花
    "ta": "CZCE",  # PTA
    "oi": "CZCE",  # 菜油
    "ma": "CZCE",  # 甲醇
    "fg": "CZCE",  # 玻璃
    "rm": "CZCE",  # 菜粕
    "zc": "CZCE",  # 动力煤
    "sf": "CZCE",  # 硅铁
    "sm": "CZCE",  # 锰硅
    "ur": "CZCE",  # 尿素
    "sa": "CZCE",  # 纯碱
    "pf": "CZCE",  # 短纤
    "pk": "CZCE",  # 花生
    "cy": "CZCE",  # 棉纱

    # 中金所 CFFEX
    "IF": "CFFEX",  # 沪深300股指期货
    "IC": "CFFEX",  # 中证500股指期货
    "IH": "CFFEX",  # 上证50股指期货
    "IM": "CFFEX",  # 中证1000股指期货
    "T": "CFFEX",   # 10年期国债
    "TF": "CFFEX",  # 5年期国债
    "TS": "CFFEX",  # 2年期国债
    "TL": "CFFEX",  # 30年期国债
}

# Tushare交易所代码映射
EXCHANGE_TO_TUSHARE = {
    "SHFE": "SHF",
    "DCE": "DCE",
    "CZCE": "ZCE",
    "CFFEX": "CFX",
    "INE": "INE",  # 上海国际能源交易中心
}


# ==================== Backtest Constants ====================

class BacktestConstants:
    """回测系统常量"""

    # 默认回测参数
    DEFAULT_INITIAL_CAPITAL = 1_000_000.0  # 初始资金：100万
    DEFAULT_COMMISSION_RATE = 0.0003       # 手续费率：万分之3
    DEFAULT_SLIPPAGE = 0.0001              # 滑点：万分之1

    # 性能指标计算参数
    TRADING_DAYS_PER_YEAR = 250            # 一年交易日数
    RISK_FREE_RATE = 0.03                  # 无风险利率：3%

    # 订单类型
    ORDER_TYPE_MARKET = "MARKET"           # 市价单
    ORDER_TYPE_LIMIT = "LIMIT"             # 限价单
    ORDER_TYPE_STOP = "STOP"               # 止损单

    # 订单方向
    ORDER_SIDE_BUY = "BUY"                 # 买入
    ORDER_SIDE_SELL = "SELL"               # 卖出

    # 订单状态
    ORDER_STATUS_PENDING = "PENDING"       # 待成交
    ORDER_STATUS_FILLED = "FILLED"         # 已成交
    ORDER_STATUS_CANCELLED = "CANCELLED"   # 已取消
    ORDER_STATUS_REJECTED = "REJECTED"     # 已拒绝

    # 持仓方向
    POSITION_LONG = "LONG"                 # 多头
    POSITION_SHORT = "SHORT"               # 空头
    POSITION_FLAT = "FLAT"                 # 空仓
