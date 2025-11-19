#!/usr/bin/env python3
"""
测试风险配置加载功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings.base import CONFIG
from src.cherryquant.ai.agents.agent_manager import AgentManager, PortfolioRiskConfig

def test_risk_config_from_env():
    """测试从 .env 加载风险配置"""
    print("\n" + "="*60)
    print("测试 1: 从 .env 加载风险配置")
    print("="*60)

    print(f"✅ 最大资金使用率: {CONFIG.risk.max_total_capital_usage}")
    print(f"✅ 最大相关性阈值: {CONFIG.risk.max_correlation_threshold}")
    print(f"✅ 最大板块集中度: {CONFIG.risk.max_sector_concentration}")
    print(f"✅ 组合止损比例: {CONFIG.risk.portfolio_stop_loss}")
    print(f"✅ 每日亏损限制: {CONFIG.risk.daily_loss_limit}")
    print(f"✅ 最大总杠杆: {CONFIG.risk.max_leverage_total}")

    # 验证默认值
    assert CONFIG.risk.max_total_capital_usage == 0.8, "默认值应为 0.8"
    assert CONFIG.risk.max_leverage_total == 3.0, "默认杠杆应为 3.0"

    print("✅ 从 .env 加载风险配置测试通过！\n")

def test_portfolio_risk_config_from_config():
    """测试 PortfolioRiskConfig.from_config()"""
    print("="*60)
    print("测试 2: PortfolioRiskConfig.from_config()")
    print("="*60)

    risk_config = PortfolioRiskConfig.from_config()

    print(f"✅ max_total_capital_usage: {risk_config.max_total_capital_usage}")
    print(f"✅ max_correlation_threshold: {risk_config.max_correlation_threshold}")
    print(f"✅ max_sector_concentration: {risk_config.max_sector_concentration}")
    print(f"✅ portfolio_stop_loss: {risk_config.portfolio_stop_loss}")
    print(f"✅ daily_loss_limit: {risk_config.daily_loss_limit}")
    print(f"✅ max_leverage_total: {risk_config.max_leverage_total}")

    assert risk_config.max_total_capital_usage == CONFIG.risk.max_total_capital_usage
    assert risk_config.max_leverage_total == CONFIG.risk.max_leverage_total

    print("✅ PortfolioRiskConfig.from_config() 测试通过！\n")

def test_agent_manager_initialization():
    """测试 AgentManager 初始化（无参数）"""
    print("="*60)
    print("测试 3: AgentManager 初始化（向后兼容性）")
    print("="*60)

    # 不传入 risk_config，应该从 CONFIG 自动加载
    manager = AgentManager()

    print(f"✅ 风险配置已加载: {manager.risk_config}")
    print(f"   - 最大资金使用率: {manager.risk_config.max_total_capital_usage}")
    print(f"   - 组合止损: {manager.risk_config.portfolio_stop_loss}")
    print(f"   - 最大杠杆: {manager.risk_config.max_leverage_total}")

    assert manager.risk_config.max_total_capital_usage == 0.8
    assert manager.risk_config.max_leverage_total == 3.0

    print("✅ AgentManager 初始化测试通过！\n")

def test_sector_mapping_loading():
    """测试板块映射加载"""
    print("="*60)
    print("测试 4: 板块映射加载")
    print("="*60)

    manager = AgentManager()

    print(f"✅ 成功加载 {len(manager.sector_mapping)} 个品种的板块映射")

    # 测试几个品种
    test_symbols = [
        ("rb2501", "黑色金属"),
        ("cu2501", "有色金属"),
        ("au2506", "贵金属"),
        ("a2501", "农产品"),
        ("IF2501", "金融"),
        ("pp2501", "化工"),
    ]

    for symbol, expected_sector in test_symbols:
        sector = manager._get_symbol_sector(symbol)
        print(f"✅ {symbol} -> {sector}")
        assert sector == expected_sector, f"{symbol} 应属于 {expected_sector}，实际为 {sector}"

    print("✅ 板块映射加载测试通过！\n")

def test_custom_risk_config():
    """测试传入自定义风险配置"""
    print("="*60)
    print("测试 5: 自定义风险配置")
    print("="*60)

    # 创建自定义风险配置
    custom_config = PortfolioRiskConfig(
        max_total_capital_usage=0.6,
        max_correlation_threshold=0.5,
        max_sector_concentration=0.3,
        portfolio_stop_loss=0.05,
        daily_loss_limit=0.03,
        max_leverage_total=2.0,
    )

    manager = AgentManager(risk_config=custom_config)

    print(f"✅ 自定义最大资金使用率: {manager.risk_config.max_total_capital_usage}")
    print(f"✅ 自定义组合止损: {manager.risk_config.portfolio_stop_loss}")
    print(f"✅ 自定义最大杠杆: {manager.risk_config.max_leverage_total}")

    assert manager.risk_config.max_total_capital_usage == 0.6
    assert manager.risk_config.max_leverage_total == 2.0

    print("✅ 自定义风险配置测试通过！\n")

if __name__ == "__main__":
    try:
        test_risk_config_from_env()
        test_portfolio_risk_config_from_config()
        test_agent_manager_initialization()
        test_sector_mapping_loading()
        test_custom_risk_config()

        print("="*60)
        print("✅ 所有测试通过！风险配置系统工作正常")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
