"""
PostgreSQL 到 MongoDB 数据迁移脚本
用于将现有 PostgreSQL (TimescaleDB) 数据迁移到 MongoDB
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient
from bson import Decimal128
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataMigrator:
    """数据迁移器"""

    def __init__(self):
        # PostgreSQL 配置
        self.pg_config = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "database": os.getenv("POSTGRES_DB", "cherryquant"),
            "user": os.getenv("POSTGRES_USER", "cherryquant"),
            "password": os.getenv("POSTGRES_PASSWORD", "cherryquant123"),
        }

        # MongoDB 配置
        self.mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.mongo_db_name = os.getenv("MONGODB_DATABASE", "cherryquant")

        self.pg_pool = None
        self.mongo_client = None
        self.mongo_db = None

    async def connect(self):
        """建立数据库连接"""
        try:
            # 连接 PostgreSQL
            self.pg_pool = await asyncpg.create_pool(**self.pg_config)
            logger.info(f"✅ PostgreSQL 连接成功: {self.pg_config['host']}")

            # 连接 MongoDB
            self.mongo_client = AsyncIOMotorClient(self.mongo_uri)
            self.mongo_db = self.mongo_client[self.mongo_db_name]

            # 测试连接
            await self.mongo_db.command("ping")
            logger.info(f"✅ MongoDB 连接成功: {self.mongo_uri}")

        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            raise

    async def disconnect(self):
        """关闭数据库连接"""
        if self.pg_pool:
            await self.pg_pool.close()
            logger.info("✓ PostgreSQL 连接已关闭")
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("✓ MongoDB 连接已关闭")

    async def migrate_market_data(self, batch_size: int = 1000, limit: int = None):
        """
        迁移市场数据

        Args:
            batch_size: 每批处理的记录数
            limit: 最大迁移记录数（None 表示全部）
        """
        logger.info("\n" + "=" * 60)
        logger.info("开始迁移 market_data 表")
        logger.info("=" * 60)

        try:
            # 获取总记录数
            async with self.pg_pool.acquire() as conn:
                total_count = await conn.fetchval("SELECT COUNT(*) FROM market_data")
                logger.info(f"PostgreSQL 总记录数: {total_count:,}")

            if limit:
                total_count = min(total_count, limit)

            # MongoDB 集合
            collection = self.mongo_db["market_data"]

            # 分批迁移
            migrated = 0
            offset = 0

            while migrated < total_count:
                async with self.pg_pool.acquire() as conn:
                    # 查询一批数据
                    query = f"""
                        SELECT time, symbol, exchange, timeframe,
                               open_price, high_price, low_price, close_price,
                               volume, open_interest, turnover, settlement_price
                        FROM market_data
                        ORDER BY time
                        LIMIT {batch_size} OFFSET {offset}
                    """
                    rows = await conn.fetch(query)

                if not rows:
                    break

                # 转换为 MongoDB 文档
                documents = []
                for row in rows:
                    doc = {
                        "time": row["time"],
                        "metadata": {
                            "symbol": row["symbol"],
                            "exchange": row["exchange"],
                            "timeframe": row["timeframe"]
                        },
                        "open_price": Decimal128(str(row["open_price"])) if row["open_price"] else None,
                        "high_price": Decimal128(str(row["high_price"])) if row["high_price"] else None,
                        "low_price": Decimal128(str(row["low_price"])) if row["low_price"] else None,
                        "close_price": Decimal128(str(row["close_price"])) if row["close_price"] else None,
                        "volume": int(row["volume"]) if row["volume"] else None,
                        "open_interest": int(row["open_interest"]) if row["open_interest"] else None,
                        "turnover": Decimal128(str(row["turnover"])) if row["turnover"] else None,
                        "settlement_price": Decimal128(str(row["settlement_price"])) if row["settlement_price"] else None,
                        "created_at": datetime.now()
                    }
                    documents.append(doc)

                # 批量插入 MongoDB（使用 update_one + upsert 避免重复）
                if documents:
                    from pymongo import UpdateOne
                    operations = [
                        UpdateOne(
                            {
                                "time": doc["time"],
                                "metadata.symbol": doc["metadata"]["symbol"],
                                "metadata.exchange": doc["metadata"]["exchange"],
                                "metadata.timeframe": doc["metadata"]["timeframe"]
                            },
                            {"$set": doc},
                            upsert=True
                        )
                        for doc in documents
                    ]
                    result = await collection.bulk_write(operations, ordered=False)
                    migrated += len(documents)
                    offset += batch_size

                    logger.info(f"  已迁移: {migrated:,} / {total_count:,} ({migrated/total_count*100:.1f}%)")

            logger.info(f"✅ market_data 迁移完成: {migrated:,} 条记录")

        except Exception as e:
            logger.error(f"❌ market_data 迁移失败: {e}")
            raise

    async def migrate_trades(self):
        """迁移交易记录"""
        logger.info("\n" + "=" * 60)
        logger.info("开始迁移 trades 表")
        logger.info("=" * 60)

        try:
            async with self.pg_pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM trades ORDER BY entry_time")

            if not rows:
                logger.info("  trades 表无数据，跳过")
                return

            collection = self.mongo_db["trades"]
            documents = []

            for row in rows:
                doc = {
                    "symbol": row["symbol"],
                    "exchange": row["exchange"],
                    "direction": row["direction"],
                    "quantity": row["quantity"],
                    "entry_price": Decimal128(str(row["entry_price"])) if row.get("entry_price") else None,
                    "exit_price": Decimal128(str(row["exit_price"])) if row.get("exit_price") else None,
                    "entry_time": row["entry_time"],
                    "exit_time": row.get("exit_time"),
                    "entry_fee": Decimal128(str(row["entry_fee"])) if row.get("entry_fee") else None,
                    "exit_fee": Decimal128(str(row["exit_fee"])) if row.get("exit_fee") else None,
                    "gross_pnl": Decimal128(str(row["gross_pnl"])) if row.get("gross_pnl") else None,
                    "net_pnl": Decimal128(str(row["net_pnl"])) if row.get("net_pnl") else None,
                    "pnl_percentage": Decimal128(str(row["pnl_percentage"])) if row.get("pnl_percentage") else None,
                    "ai_decision_id": str(row["ai_decision_id"]) if row.get("ai_decision_id") else None,
                    "created_at": row.get("created_at", datetime.now()),
                    "updated_at": row.get("updated_at", datetime.now())
                }
                documents.append(doc)

            if documents:
                await collection.insert_many(documents)
                logger.info(f"✅ trades 迁移完成: {len(documents)} 条记录")

        except Exception as e:
            logger.error(f"❌ trades 迁移失败: {e}")

    async def migrate_ai_decisions(self):
        """迁移 AI 决策记录"""
        logger.info("\n" + "=" * 60)
        logger.info("开始迁移 ai_decisions 表")
        logger.info("=" * 60)

        try:
            async with self.pg_pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM ai_decisions ORDER BY decision_time")

            if not rows:
                logger.info("  ai_decisions 表无数据，跳过")
                return

            collection = self.mongo_db["ai_decisions"]
            documents = []

            for row in rows:
                doc = {
                    "decision_time": row["decision_time"],
                    "symbol": row["symbol"],
                    "exchange": row["exchange"],
                    "action": row.get("action"),
                    "quantity": row.get("quantity"),
                    "leverage": row.get("leverage"),
                    "entry_price": Decimal128(str(row["entry_price"])) if row.get("entry_price") else None,
                    "profit_target": Decimal128(str(row["profit_target"])) if row.get("profit_target") else None,
                    "stop_loss": Decimal128(str(row["stop_loss"])) if row.get("stop_loss") else None,
                    "confidence": Decimal128(str(row["confidence"])) if row.get("confidence") else None,
                    "opportunity_score": row.get("opportunity_score"),
                    "selection_rationale": row.get("selection_rationale"),
                    "technical_analysis": row.get("technical_analysis"),
                    "risk_factors": row.get("risk_factors"),
                    "market_regime": row.get("market_regime"),
                    "volatility_index": row.get("volatility_index"),
                    "status": row.get("status", "pending"),
                    "executed_at": row.get("executed_at"),
                    "execution_price": Decimal128(str(row["execution_price"])) if row.get("execution_price") else None,
                    "created_at": row.get("created_at", datetime.now())
                }
                documents.append(doc)

            if documents:
                await collection.insert_many(documents)
                logger.info(f"✅ ai_decisions 迁移完成: {len(documents)} 条记录")

        except Exception as e:
            logger.error(f"❌ ai_decisions 迁移失败: {e}")

    async def migrate_futures_contracts(self):
        """迁移期货合约信息"""
        logger.info("\n" + "=" * 60)
        logger.info("开始迁移 futures_contracts 表")
        logger.info("=" * 60)

        try:
            async with self.pg_pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM futures_contracts")

            if not rows:
                logger.info("  futures_contracts 表无数据，跳过")
                return

            collection = self.mongo_db["futures_contracts"]
            documents = []

            for row in rows:
                doc = {
                    "symbol": row["symbol"],
                    "exchange": row["exchange"],
                    "name": row.get("name"),
                    "contract_size": row.get("contract_size"),
                    "margin_rate": Decimal128(str(row["margin_rate"])) if row.get("margin_rate") else None,
                    "price_tick": Decimal128(str(row["price_tick"])) if row.get("price_tick") else None,
                    "trading_unit": row.get("trading_unit"),
                    "created_at": row.get("created_at", datetime.now()),
                    "updated_at": row.get("updated_at", datetime.now())
                }
                documents.append(doc)

            if documents:
                from pymongo import UpdateOne
                operations = [
                    UpdateOne(
                        {"symbol": doc["symbol"], "exchange": doc["exchange"]},
                        {"$set": doc},
                        upsert=True
                    )
                    for doc in documents
                ]
                result = await collection.bulk_write(operations)
                logger.info(f"✅ futures_contracts 迁移完成: {len(documents)} 条记录")

        except Exception as e:
            logger.error(f"❌ futures_contracts 迁移失败: {e}")

    async def verify_migration(self):
        """验证迁移结果"""
        logger.info("\n" + "=" * 60)
        logger.info("验证迁移结果")
        logger.info("=" * 60)

        tables = ["market_data", "ai_decisions", "trades", "futures_contracts"]

        for table in tables:
            try:
                # PostgreSQL 计数
                async with self.pg_pool.acquire() as conn:
                    pg_count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")

                # MongoDB 计数
                collection = self.mongo_db[table]
                mongo_count = await collection.count_documents({})

                status = "✅" if pg_count == mongo_count else "⚠️ "
                logger.info(f"  {status} {table}: PG={pg_count:,}, Mongo={mongo_count:,}")

            except Exception as e:
                logger.error(f"  ❌ {table} 验证失败: {e}")

    async def run_full_migration(self, market_data_limit: int = None):
        """
        运行完整迁移流程

        Args:
            market_data_limit: 市场数据最大迁移条数（None = 全部）
        """
        try:
            await self.connect()

            # 迁移各个表
            await self.migrate_futures_contracts()  # 先迁移合约信息（小表）
            await self.migrate_ai_decisions()  # AI 决策
            await self.migrate_trades()  # 交易记录
            await self.migrate_market_data(limit=market_data_limit)  # 市场数据（大表）

            # 验证
            await self.verify_migration()

            logger.info("\n" + "="*60)
            logger.info("🎉 数据迁移完成！")
            logger.info("="*60)

        except Exception as e:
            logger.error(f"\n❌ 迁移过程中出现错误: {e}")
            raise
        finally:
            await self.disconnect()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="PostgreSQL 到 MongoDB 数据迁移")
    parser.add_argument("--limit", type=int, default=None, help="限制 market_data 迁移条数（测试用）")
    parser.add_argument("--verify-only", action="store_true", help="仅验证，不迁移")

    args = parser.parse_args()

    migrator = DataMigrator()

    if args.verify_only:
        await migrator.connect()
        await migrator.verify_migration()
        await migrator.disconnect()
    else:
        await migrator.run_full_migration(market_data_limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
