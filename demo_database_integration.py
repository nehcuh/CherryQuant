"""
CherryQuant 数据库集成演示
展示多时间维度数据获取、缓存和AI决策集成
"""

import asyncio
import logging
from datetime import datetime, timedelta


from cherryquant.adapters.data_storage.database_manager import get_database_manager
from cherryquant.adapters.data_storage.timeframe_data_manager import TimeFrame, TimeFrameDataManager, MarketDataPoint, TechnicalIndicators
from config.database_config import get_database_config

def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

async def demo_database_connections():
    """演示数据库连接"""
    logger = logging.getLogger(__name__)
    logger.info("🔗 测试数据库连接...")

    try:
        db_config = get_database_config()
        db_manager = await get_database_manager(db_config)
        stats = await db_manager.get_data_statistics()

        logger.info("✅ 数据库连接成功!")
        logger.info(f"📊 数据库统计:")
        if stats.get("market_data"):
            logger.info(f"   市场数据: {stats['market_data'].get('total_records', 0)} 条记录")
            logger.info(f"   涵盖品种: {stats['market_data'].get('unique_symbols', 0)} 个")
            logger.info(f"   时间范围: {stats['market_data'].get('earliest_time', 'N/A')} 至 {stats['market_data'].get('latest_time', 'N/A')}")

        if stats.get("cache_info"):
            logger.info(f"   缓存状态: {stats['cache_info'].get('status', 'unknown')}")
            logger.info(f"   内存使用: {stats['cache_info'].get('used_memory', 'N/A')}")

        return db_manager

    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        return None

async def demo_timeframe_data_generation():
    """演示多时间维度数据生成"""
    logger = logging.getLogger(__name__)
    logger.info("📈 生成多时间维度测试数据...")

    timeframe_manager = TimeFrameDataManager()

    # 模拟获取螺纹钢(rb)的多时间维度数据
    symbol = "rb"
    exchange = "SHFE"
    timeframes = [TimeFrame.DAILY, TimeFrame.FOUR_HOURLY, TimeFrame.HOURLY, TimeFrame.FIFTEEN_MIN, TimeFrame.FIVE_MIN]

    all_data = {}
    for timeframe in timeframes:
        try:
            # 获取数据（这里使用模拟数据）
            data = await timeframe_manager.get_multi_timeframe_data(symbol, exchange, [timeframe], limit=50)
            if timeframe in data:
                all_data[timeframe] = data[timeframe]
                logger.info(f"   {timeframe.value}: {len(data[timeframe])} 条数据")

                # 显示最新价格
                latest = data[timeframe].iloc[-1]
                logger.info(f"      最新价格: ¥{latest['close']:.2f}")
                logger.info(f"      涨跌幅: {latest.get('change_pct', 0):+.2f}%")

        except Exception as e:
            logger.error(f"获取{timeframe.value}数据失败: {e}")

    return all_data, timeframe_manager

async def demo_technical_indicators(timeframe_manager):
    """演示技术指标计算"""
    logger = logging.getLogger(__name__)
    logger.info("🔢 计算技术指标...")

    try:
        # 获取螺纹钢的技术指标
        indicators = await timeframe_manager.get_multi_timeframe_indicators("rb", "SHFE")

        for timeframe, indicator_list in indicators.items():
            if indicator_list:
                latest = indicator_list[-1]
                logger.info(f"   {timeframe.value}:")
                logger.info(f"      RSI: {latest.rsi:.1f}")
                logger.info(f"      MACD: {latest.macd:.4f}")
                logger.info(f"      KDJ-K: {latest.kdj_k:.1f}")
                logger.info(f"      ATR: {latest.atr:.2f}")
                if latest.ma20:
                    logger.info(f"      MA20: ¥{latest.ma20:.2f}")

        return indicators

    except Exception as e:
        logger.error(f"技术指标计算失败: {e}")
        return {}

async def demo_ai_optimized_data(timeframe_manager):
    """演示AI优化数据格式"""
    logger = logging.getLogger(__name__)
    logger.info("🤖 生成AI优化数据...")

    try:
        ai_data = await timeframe_manager.get_ai_optimized_data("rb", "SHFE")

        logger.info("📊 AI分析数据:")
        logger.info(f"   品种: {ai_data.get('symbol', 'N/A')}")
        logger.info(f"   更新时间: {ai_data.get('update_time', 'N/A')}")

        # 趋势分析
        trend_analysis = ai_data.get('trend_analysis', {})
        if trend_analysis:
            logger.info("   趋势分析:")
            for tf, trend in trend_analysis.items():
                logger.info(f"      {tf}: {trend.get('trend', 'unknown')} (价格vsMA20: {trend.get('price_vs_ma20_pct', 0):+.2f}%)")

        # 关键价位
        key_levels = ai_data.get('key_levels', {})
        if key_levels:
            logger.info("   关键价位:")
            logger.info(f"      当前价格: ¥{key_levels.get('current_price', 0):.2f}")
            support_levels = key_levels.get('support_levels', [])
            resistance_levels = key_levels.get('resistance_levels', [])
            if support_levels:
                logger.info(f"      支撑位: {', '.join([f'¥{s:.2f}' for s in support_levels])}")
            if resistance_levels:
                logger.info(f"      阻力位: {', '.join([f'¥{r:.2f}' for r in resistance_levels])}")

        # 技术摘要
        tech_summary = ai_data.get('technical_summary', {})
        if tech_summary:
            logger.info("   技术摘要:")
            logger.info(f"      总体信号: {tech_summary.get('overall_signal', 'unknown')}")
            logger.info(f"      置信度: {tech_summary.get('confidence', 0):.2f}")

        return ai_data

    except Exception as e:
        logger.error(f"AI优化数据生成失败: {e}")
        return {}

async def demo_database_storage(db_manager, timeframe_data, technical_indicators):
    """演示数据库存储"""
    logger = logging.getLogger(__name__)
    logger.info("💾 存储数据到数据库...")

    try:
        # 存储市场数据
        for timeframe, df in timeframe_data.items():
            # 转换为MarketDataPoint列表
            data_points = []
            for index, row in df.iterrows():
                point = MarketDataPoint(
                    timestamp=index if hasattr(index, 'to_pydatetime') else datetime.now(),
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=int(row['volume']),
                    open_interest=0,
                    turnover=0.0
                )
                data_points.append(point)

            success = await db_manager.store_market_data("rb", "SHFE", timeframe, data_points)
            if success:
                logger.info(f"   ✅ 存储{timeframe.value}数据: {len(data_points)}条")

        # 存储技术指标
        for timeframe, indicators in technical_indicators.items():
            success = await db_manager.store_technical_indicators("rb", "SHFE", timeframe, indicators)
            if success:
                logger.info(f"   ✅ 存储{timeframe.value}技术指标: {len(indicators)}条")

        # 模拟AI决策存储
        ai_decision = {
            "decision_time": datetime.now(),
            "symbol": "rb",
            "exchange": "SHFE",
            "action": "buy_to_enter",
            "quantity": 3,
            "leverage": 5,
            "entry_price": 3520.0,
            "profit_target": 3580.0,
            "stop_loss": 3460.0,
            "confidence": 0.78,
            "opportunity_score": 85,
            "selection_rationale": "技术指标显示上涨趋势，RSI处于健康区间，成交量放大",
            "technical_analysis": "价格突破MA20，MACD金叉，KDJ向上发散",
            "risk_factors": "市场波动性中等，需关注整体市场情绪",
            "market_regime": "trending",
            "volatility_index": "medium",
            "status": "pending"
        }

        success = await db_manager.store_ai_decision(ai_decision)
        if success:
            logger.info(f"   ✅ 存储AI决策: {ai_decision['action']} {ai_decision['symbol']}")

        return True

    except Exception as e:
        logger.error(f"数据库存储失败: {e}")
        return False

async def demo_data_retrieval(db_manager):
    """演示数据检索"""
    logger = logging.getLogger(__name__)
    logger.info("🔍 从数据库检索数据...")

    try:
        # 检索市场数据
        market_data = await db_manager.get_market_data("rb", "SHFE", TimeFrame.DAILY, limit=10)
        if market_data:
            logger.info(f"   📈 检索到日线数据: {len(market_data)}条")
            latest = market_data[0]
            logger.info(f"      最新价格: ¥{latest.close:.2f}")
            logger.info(f"      成交量: {latest.volume:,}")

        # 检索技术指标
        indicators = await db_manager.get_technical_indicators("rb", "SHFE", TimeFrame.DAILY, limit=5)
        if indicators:
            logger.info(f"   🔢 检索到技术指标: {len(indicators)}条")
            latest = indicators[0]
            logger.info(f"      RSI: {latest.rsi:.1f}")
            logger.info(f"      MACD: {latest.macd:.4f}")

        # 检索AI决策
        decisions = await db_manager.get_ai_decisions(limit=5)
        if decisions:
            logger.info(f"   🤖 检索到AI决策: {len(decisions)}条")
            latest = decisions[0]
            logger.info(f"      最新决策: {latest['action']} {latest['symbol']}")
            logger.info(f"      置信度: {latest['confidence']:.2f}")

        # 获取数据库统计
        stats = await db_manager.get_data_statistics()
        logger.info("   📊 更新后的数据库统计:")
        if stats.get("market_data"):
            logger.info(f"      市场数据记录: {stats['market_data'].get('total_records', 0)}")
        if stats.get("ai_decisions"):
            logger.info(f"      AI决策记录: {stats['ai_decisions'].get('total_decisions', 0)}")

    except Exception as e:
        logger.error(f"数据检索失败: {e}")

async def demo_cache_performance(db_manager, timeframe_manager):
    """演示缓存性能"""
    logger = logging.getLogger(__name__)
    logger.info("⚡ 测试缓存性能...")

    try:
        import time

        # 第一次查询（从数据库获取）
        start_time = time.time()
        data1 = await db_manager.get_market_data("rb", "SHFE", TimeFrame.DAILY, limit=100)
        db_time = time.time() - start_time
        logger.info(f"   数据库查询耗时: {db_time:.3f}秒 ({len(data1)}条)")

        # 第二次查询（从缓存获取）
        start_time = time.time()
        data2 = await db_manager.get_market_data("rb", "SHFE", TimeFrame.DAILY, limit=100)
        cache_time = time.time() - start_time
        logger.info(f"   缓存查询耗时: {cache_time:.3f}秒 ({len(data2)}条)")

        if cache_time < db_time:
            speedup = db_time / cache_time
            logger.info(f"   🚀 缓存加速比: {speedup:.1f}x")

        # 获取缓存信息
        stats = await db_manager.get_data_statistics()
        cache_info = stats.get('cache_info', {})
        if cache_info:
            logger.info(f"   缓存内存使用: {cache_info.get('used_memory', 'N/A')}")
            logger.info(f"   总缓存键数: {cache_info.get('total_keys', 0)}")

    except Exception as e:
        logger.error(f"缓存性能测试失败: {e}")

async def main():
    """主函数"""
    logger = setup_logging()
    logger.info("🍒 CherryQuant 数据库集成演示开始")
    logger.info("=" * 80)

    try:
        # 1. 测试数据库连接
        db_manager = await demo_database_connections()
        if not db_manager:
            logger.error("❌ 数据库连接失败，演示结束")
            return

        # 2. 生成多时间维度数据
        timeframe_data, timeframe_manager = await demo_timeframe_data_generation()

        # 3. 计算技术指标
        technical_indicators = await demo_technical_indicators(timeframe_manager)

        # 4. 生成AI优化数据
        ai_data = await demo_ai_optimized_data(timeframe_manager)

        # 5. 存储到数据库
        success = await demo_database_storage(db_manager, timeframe_data, technical_indicators)

        if success:
            # 6. 数据检索演示
            await demo_data_retrieval(db_manager)

            # 7. 缓存性能测试
            await demo_cache_performance(db_manager, timeframe_manager)

        logger.info("🎉 数据库集成演示完成！")
        logger.info("=" * 80)

        # 8. 清理资源
        await db_manager.close()
        logger.info("🧹 资源清理完成")

    except Exception as e:
        logger.error(f"❌ 演示过程出错: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
