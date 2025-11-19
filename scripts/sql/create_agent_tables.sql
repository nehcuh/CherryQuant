-- CherryQuant 代理系统数据库表结构
-- 执行前请确保已连接到CherryQuant数据库

-- 策略交易记录表
CREATE TABLE IF NOT EXISTS strategy_trades (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(100) NOT NULL UNIQUE,
    strategy_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(15,4) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    commission DECIMAL(15,4) NOT NULL DEFAULT 0,
    pnl DECIMAL(15,4) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'executed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_strategy_id (strategy_id),
    INDEX idx_symbol (symbol),
    INDEX idx_timestamp (timestamp),
    INDEX idx_status (status)
);

-- 组合状态表
CREATE TABLE IF NOT EXISTS portfolio_status (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    portfolio_value DECIMAL(20,4) NOT NULL,
    total_pnl DECIMAL(20,4) NOT NULL DEFAULT 0,
    daily_pnl DECIMAL(20,4) NOT NULL DEFAULT 0,
    total_trades INTEGER NOT NULL DEFAULT 0,
    active_strategies INTEGER NOT NULL DEFAULT 0,
    total_strategies INTEGER NOT NULL DEFAULT 0,
    capital_usage DECIMAL(8,4) NOT NULL DEFAULT 0,
    sector_concentration DECIMAL(8,4) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_timestamp (timestamp)
);

-- 策略性能表
CREATE TABLE IF NOT EXISTS strategy_performance (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    strategy_id VARCHAR(50) NOT NULL,
    account_value DECIMAL(20,4) NOT NULL,
    cash_available DECIMAL(20,4) NOT NULL,
    positions_count INTEGER NOT NULL DEFAULT 0,
    total_trades INTEGER NOT NULL DEFAULT 0,
    win_rate DECIMAL(8,4) NOT NULL DEFAULT 0,
    total_pnl DECIMAL(20,4) NOT NULL DEFAULT 0,
    max_drawdown DECIMAL(8,4) NOT NULL DEFAULT 0,
    return_pct DECIMAL(8,4) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_strategy_timestamp (strategy_id, timestamp),
    INDEX idx_timestamp (timestamp),
    INDEX idx_strategy_id (strategy_id)
);

-- 策略配置表
CREATE TABLE IF NOT EXISTS strategy_configs (
    id SERIAL PRIMARY KEY,
    strategy_id VARCHAR(50) NOT NULL UNIQUE,
    strategy_name VARCHAR(100) NOT NULL,
    config_json JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_strategy_id (strategy_id),
    INDEX idx_is_active (is_active)
);

-- 风险事件记录表
CREATE TABLE IF NOT EXISTS risk_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    strategy_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    current_capital_usage DECIMAL(8,4) NOT NULL DEFAULT 0,
    current_drawdown DECIMAL(8,4) NOT NULL DEFAULT 0,
    position_correlation DECIMAL(8,4) NOT NULL DEFAULT 0,
    action_taken VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_strategy_timestamp (strategy_id, timestamp),
    INDEX idx_timestamp (timestamp),
    INDEX idx_severity (severity),
    INDEX idx_event_type (event_type)
);

-- 持仓快照表
CREATE TABLE IF NOT EXISTS position_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    strategy_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(15,4) NOT NULL,
    current_price DECIMAL(15,4) NOT NULL,
    unrealized_pnl DECIMAL(20,4) NOT NULL DEFAULT 0,
    leverage DECIMAL(8,4) NOT NULL DEFAULT 1,
    stop_loss DECIMAL(15,4),
    take_profit DECIMAL(15,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_strategy_timestamp (strategy_id, timestamp),
    INDEX idx_symbol (symbol),
    INDEX idx_timestamp (timestamp)
);

-- AI决策日志表（扩展原有表）
ALTER TABLE ai_decisions ADD COLUMN IF NOT EXISTS strategy_id VARCHAR(50);
ALTER TABLE ai_decisions ADD COLUMN IF NOT EXISTS execution_result VARCHAR(200);
ALTER TABLE ai_decisions ADD COLUMN IF NOT EXISTS execution_time_ms INTEGER;

-- 添加索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_ai_decisions_strategy_id ON ai_decisions(strategy_id);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_decision_time ON ai_decisions(decision_time);

-- 更新现有表的时间分区（如果使用TimescaleDB）
-- 注意：这些语句需要TimescaleDB扩展，如果没有安装可以忽略

-- DO $$
-- BEGIN
--     -- 为市场数据表创建超表（如果还没有）
--     IF NOT EXISTS (
--         SELECT 1 FROM timescaledb_information.hypertables
--         WHERE hypertable_name = 'market_data'
--     ) THEN
--         PERFORM create_hypertable('market_data', 'time', chunk_time_interval => INTERVAL '1 day');
--     END IF;

--     -- 为AI决策表创建超表
--     IF NOT EXISTS (
--         SELECT 1 FROM timescaledb_information.hypertables
--         WHERE hypertable_name = 'ai_decisions'
--     ) THEN
--         PERFORM create_hypertable('ai_decisions', 'decision_time', chunk_time_interval => INTERVAL '1 day');
--     END IF;

--     -- 为策略交易表创建超表
--     PERFORM create_hypertable('strategy_trades', 'timestamp', chunk_time_interval => INTERVAL '1 day');

--     -- 为组合状态表创建超表
--     PERFORM create_hypertable('portfolio_status', 'timestamp', chunk_time_interval => INTERVAL '1 day');

--     -- 为策略性能表创建超表
--     PERFORM create_hypertable('strategy_performance', 'timestamp', chunk_time_interval => INTERVAL '1 day');

--     -- 为风险事件表创建超表
--     PERFORM create_hypertable('risk_events', 'timestamp', chunk_time_interval => INTERVAL '1 day');

--     -- 为持仓快照表创建超表
--     PERFORM create_hypertable('position_snapshots', 'timestamp', chunk_time_interval => INTERVAL '1 hour');
-- END $$;

-- 插入一些示例策略配置
INSERT INTO strategy_configs (strategy_id, strategy_name, config_json, is_active) VALUES
(
    'trend_following_01',
    '趋势跟踪策略 01',
    '{
        "symbols": ["rb2501", "i2501", "j2501"],
        "initial_capital": 100000,
        "max_position_size": 5,
        "max_positions": 2,
        "leverage": 3.0,
        "risk_per_trade": 0.02,
        "decision_interval": 300,
        "confidence_threshold": 0.6,
        "ai_model": "gpt-4",
        "ai_temperature": 0.1
    }',
    true
),
(
    'mean_reversion_01',
    '均值回归策略 01',
    '{
        "symbols": ["cu2501", "al2501"],
        "initial_capital": 80000,
        "max_position_size": 3,
        "max_positions": 1,
        "leverage": 2.0,
        "risk_per_trade": 0.015,
        "decision_interval": 180,
        "confidence_threshold": 0.5,
        "ai_model": "gpt-4",
        "ai_temperature": 0.2
    }',
    true
)
ON CONFLICT (strategy_id) DO NOTHING;

-- 创建视图用于常用查询
CREATE OR REPLACE VIEW v_strategy_summary AS
SELECT
    sc.strategy_id,
    sc.strategy_name,
    sc.is_active,
    COALESCE(sp.account_value, sc.config_json->>'initial_capital'::DECIMAL) as current_value,
    COALESCE(sp.total_trades, 0) as total_trades,
    COALESCE(sp.win_rate, 0) as win_rate,
    COALESCE(sp.total_pnl, 0) as total_pnl,
    COALESCE(sp.max_drawdown, 0) as max_drawdown,
    COALESCE(sp.return_pct, 0) as return_pct,
    sp.timestamp as last_updated
FROM strategy_configs sc
LEFT JOIN LATERAL (
    SELECT *
    FROM strategy_performance
    WHERE strategy_id = sc.strategy_id
    ORDER BY timestamp DESC
    LIMIT 1
) sp ON true;

-- 创建当日交易统计视图
CREATE OR REPLACE VIEW v_daily_trade_stats AS
SELECT
    DATE(timestamp) as trade_date,
    strategy_id,
    COUNT(*) as trade_count,
    SUM(quantity) as total_volume,
    SUM(commission) as total_commission,
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl,
    COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades
FROM strategy_trades
WHERE timestamp >= CURRENT_DATE
GROUP BY DATE(timestamp), strategy_id;

-- 设置表级别的注释
COMMENT ON TABLE strategy_trades IS '策略交易记录表，记录每个策略的每笔交易';
COMMENT ON TABLE portfolio_status IS '组合状态表，记录整个投资组合的状态快照';
COMMENT ON TABLE strategy_performance IS '策略性能表，记录每个策略的实时性能指标';
COMMENT ON TABLE strategy_configs IS '策略配置表，存储策略的配置参数';
COMMENT ON TABLE risk_events IS '风险事件表，记录系统中的各种风险事件';
COMMENT ON TABLE position_snapshots IS '持仓快照表，记录策略持仓的定时快照';

-- 设置列级别的注释
COMMENT ON COLUMN strategy_trades.strategy_id IS '策略唯一标识符';
COMMENT ON COLUMN strategy_trades.trade_id IS '交易唯一标识符';
COMMENT ON COLUMN strategy_trades.direction IS '交易方向：buy/sell';
COMMENT ON COLUMN strategy_trades.order_type IS '订单类型：market/limit/stop';
COMMENT ON COLUMN strategy_trades.pnl IS '交易盈亏，平仓时计算';

COMMENT ON COLUMN portfolio_status.capital_usage IS '资金使用率（0-1）';
COMMENT ON COLUMN portfolio_status.sector_concentration IS '板块集中度（0-1）';

COMMENT ON COLUMN strategy_performance.win_rate IS '胜率（0-1）';
COMMENT ON COLUMN strategy_performance.max_drawdown IS '最大回撤（0-1）';
COMMENT ON COLUMN strategy_performance.return_pct IS '收益率（0-1）';

COMMENT ON COLUMN risk_events.severity IS '风险严重程度：low/medium/high/critical';
COMMENT ON COLUMN risk_events.action_taken IS '针对风险事件采取的行动';

-- 创建清理旧数据的函数
CREATE OR REPLACE FUNCTION cleanup_old_data(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
    cutoff_date TIMESTAMP := CURRENT_TIMESTAMP - (days_to_keep || ' days')::INTERVAL;
BEGIN
    -- 清理旧的风险事件
    DELETE FROM risk_events WHERE timestamp < cutoff_date;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- 清理旧的持仓快照（保留更短时间）
    DELETE FROM position_snapshots WHERE timestamp < CURRENT_TIMESTAMP - (30 || ' days')::INTERVAL;

    -- 清理旧的策略性能数据（但保留每个策略的最新数据）
    DELETE FROM strategy_performance WHERE timestamp < cutoff_date
    AND id NOT IN (
        SELECT DISTINCT ON (strategy_id) id
        FROM strategy_performance
        ORDER BY strategy_id, timestamp DESC
    );

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 创建自动清理任务（需要pg_cron扩展）
-- SELECT cron.schedule('cleanup-old-data', '0 2 * * *', 'SELECT cleanup_old_data(90);');

-- 完成提示
SELECT 'CherryQuant 代理系统数据库表创建完成！' as status;