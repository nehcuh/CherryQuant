"""
QuantBox 配置同步器
自动从 CherryQuant .env 同步配置到 QuantBox config.toml
"""
import os
import toml
from pathlib import Path
from typing import Dict, Any
import logging
from dotenv import load_dotenv

from config.settings.base import CherryQuantConfig

logger = logging.getLogger(__name__)


class QuantBoxConfigSynchronizer:
    """QuantBox 配置同步器"""

    def __init__(self, env_file: str = None):
        """
        初始化配置同步器

        Args:
            env_file: .env 文件路径，默认为项目根目录的 .env
        """
        if env_file is None:
            # 默认使用项目根目录的 .env
            project_root = Path(__file__).parent.parent
            env_file = project_root / ".env"

        self.env_file = Path(env_file)

        # QuantBox 配置文件路径
        self.quantbox_config_dir = Path.home() / ".quantbox" / "settings"
        self.quantbox_config_file = self.quantbox_config_dir / "config.toml"

        # 加载环境变量
        if self.env_file.exists():
            load_dotenv(self.env_file)
            logger.info(f"✓ Loaded .env from: {self.env_file}")
        else:
            logger.warning(f"⚠ .env file not found: {self.env_file}")

    def read_cherryquant_config(self) -> Dict[str, Any]:
        """从 CherryQuantConfig 读取 QuantBox 所需配置

        Returns:
            配置字典（Tushare + MongoDB）
        """
        # 通过 CherryQuantConfig 统一加载配置（尊重 .env / 环境变量）
        cfg = CherryQuantConfig.from_env()

        return {
            # Tushare 配置
            "tushare_token": cfg.data_source.tushare_token or "",

            # MongoDB 配置
            "mongodb_uri": cfg.database.mongodb_uri,
            "mongodb_database": cfg.database.mongodb_database,
            "mongodb_username": cfg.database.mongodb_username or "",
            "mongodb_password": cfg.database.mongodb_password or "",
        }

    def generate_quantbox_config(self) -> Dict[str, Any]:
        """
        生成 QuantBox 配置结构

        Returns:
            QuantBox 配置字典
        """
        cherry_config = self.read_cherryquant_config()

        # 构建 MongoDB URI（如果有认证信息）
        mongodb_uri = cherry_config["mongodb_uri"]
        if cherry_config["mongodb_username"] and cherry_config["mongodb_password"]:
            # 解析原有 URI 并添加认证信息
            # mongodb://localhost:27017 -> mongodb://user:pass@localhost:27017
            if "://" in mongodb_uri:
                protocol, rest = mongodb_uri.split("://", 1)
                mongodb_uri = f"{protocol}://{cherry_config['mongodb_username']}:{cherry_config['mongodb_password']}@{rest}"

        quantbox_config = {
            # Tushare Pro 配置
            "TSPRO": {
                "token": cherry_config["tushare_token"]
            },

            # MongoDB 配置
            "MONGODB": {
                "uri": mongodb_uri,
                "database": cherry_config["mongodb_database"]
            },

            # GoldMiner 配置（可选，默认为空）
            "GM": {
                "token": ""
            }
        }

        return quantbox_config

    def read_existing_quantbox_config(self) -> Dict[str, Any]:
        """
        读取现有的 QuantBox 配置文件

        Returns:
            现有配置字典，如果文件不存在则返回空字典
        """
        if self.quantbox_config_file.exists():
            try:
                with open(self.quantbox_config_file, "r", encoding="utf-8") as f:
                    config = toml.load(f)
                logger.info(f"✓ Read existing QuantBox config from: {self.quantbox_config_file}")
                return config
            except Exception as e:
                logger.warning(f"⚠ Failed to read existing config: {e}")
                return {}
        else:
            logger.info("ℹ️  No existing QuantBox config found")
            return {}

    def merge_configs(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并配置，优先使用新配置，但保留现有配置中的特殊字段

        Args:
            existing: 现有配置
            new: 新配置

        Returns:
            合并后的配置
        """
        merged = existing.copy()

        for section, values in new.items():
            if section not in merged:
                merged[section] = {}

            for key, value in values.items():
                # 只有当新值不为空时才覆盖
                if value:
                    merged[section][key] = value
                # 如果新值为空且旧配置中有值，保留旧值
                elif section in existing and key in existing[section]:
                    logger.info(f"  ℹ️  Keeping existing value for {section}.{key}")

        return merged

    def write_quantbox_config(self, config: Dict[str, Any]):
        """
        写入 QuantBox 配置文件

        Args:
            config: 配置字典
        """
        # 确保目录存在
        self.quantbox_config_dir.mkdir(parents=True, exist_ok=True)

        # 写入配置文件
        with open(self.quantbox_config_file, "w", encoding="utf-8") as f:
            toml.dump(config, f)

        logger.info(f"✓ Written QuantBox config to: {self.quantbox_config_file}")

    def sync(self, force: bool = False):
        """
        同步配置：从 CherryQuant .env 更新 QuantBox config.toml

        Args:
            force: 是否强制覆盖现有配置（默认为合并模式）
        """
        logger.info("\n" + "="*60)
        logger.info("🔄 Syncing configuration: CherryQuant -> QuantBox")
        logger.info("="*60 + "\n")

        # 1. 生成新配置
        logger.info("1. Generating QuantBox config from .env...")
        new_config = self.generate_quantbox_config()

        # 2. 读取现有配置
        if not force:
            logger.info("2. Reading existing QuantBox config...")
            existing_config = self.read_existing_quantbox_config()

            # 3. 合并配置
            logger.info("3. Merging configurations...")
            final_config = self.merge_configs(existing_config, new_config)
        else:
            logger.info("2. Force mode: Overwriting existing config...")
            final_config = new_config

        # 4. 写入配置文件
        logger.info("4. Writing QuantBox config...")
        self.write_quantbox_config(final_config)

        # 5. 验证配置
        logger.info("\n5. Validating configuration...")
        self.validate_config(final_config)

        logger.info("\n" + "="*60)
        logger.info("✓ Configuration sync completed!")
        logger.info("="*60 + "\n")

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置有效性

        Args:
            config: 配置字典

        Returns:
            是否有效
        """
        issues = []

        # 检查 Tushare Token
        if "TSPRO" in config:
            token = config["TSPRO"].get("token", "")
            if not token or len(token) < 20:
                issues.append("⚠️ Tushare Token 未配置或无效")
            else:
                logger.info("  ✓ Tushare Token: Configured")

        # 检查 MongoDB
        if "MONGODB" in config:
            uri = config["MONGODB"].get("uri", "")
            database = config["MONGODB"].get("database", "")

            if not uri:
                issues.append("⚠️ MongoDB URI 未配置")
            else:
                logger.info(f"  ✓ MongoDB URI: {uri}")

            if not database:
                issues.append("⚠️ MongoDB Database 未配置")
            else:
                logger.info(f"  ✓ MongoDB Database: {database}")

        # 输出问题
        if issues:
            logger.warning("\n配置验证发现问题:")
            for issue in issues:
                logger.warning(f"  {issue}")
            return False
        else:
            logger.info("\n✓ 配置验证通过")
            return True

    def print_config_summary(self):
        """打印配置摘要"""
        if not self.quantbox_config_file.exists():
            logger.warning("⚠️ QuantBox config file not found")
            return

        config = self.read_existing_quantbox_config()

        print("\n" + "="*60)
        print("📋 QuantBox Configuration Summary")
        print("="*60)
        print(f"📁 Config File: {self.quantbox_config_file}")
        print()

        if "TSPRO" in config:
            token = config["TSPRO"].get("token", "")
            if token:
                masked_token = token[:8] + "*" * (len(token) - 12) + token[-4:] if len(token) > 12 else "***"
                print(f"📊 Tushare Token: {masked_token}")
            else:
                print("📊 Tushare Token: Not configured")

        if "MONGODB" in config:
            print(f"💾 MongoDB URI: {config['MONGODB'].get('uri', 'Not configured')}")
            print(f"💾 MongoDB Database: {config['MONGODB'].get('database', 'Not configured')}")

        if "GM" in config:
            gm_token = config["GM"].get("token", "")
            if gm_token:
                print(f"🔑 GoldMiner Token: Configured")
            else:
                print(f"🔑 GoldMiner Token: Not configured (optional)")

        print("="*60 + "\n")


def sync_quantbox_config(force: bool = False):
    """
    便捷函数：同步 QuantBox 配置

    Args:
        force: 是否强制覆盖
    """
    synchronizer = QuantBoxConfigSynchronizer()
    synchronizer.sync(force=force)
    return synchronizer


def print_quantbox_config():
    """便捷函数：打印 QuantBox 配置摘要"""
    synchronizer = QuantBoxConfigSynchronizer()
    synchronizer.print_config_summary()


if __name__ == "__main__":
    import sys

    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )

    # 解析命令行参数
    force = "--force" in sys.argv
    show_only = "--show" in sys.argv

    if show_only:
        # 只显示配置
        print_quantbox_config()
    else:
        # 同步配置
        synchronizer = sync_quantbox_config(force=force)
        synchronizer.print_config_summary()
