-- 创建组合状态表
CREATE TABLE IF NOT EXISTS portfolio_status (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    portfolio_value DECIMAL(20,2) NOT NULL,
    total_pnl DECIMAL(20,2) DEFAULT 0,
    daily_pnl DECIMAL(20,2) DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    active_strategies INTEGER DEFAULT 0,
    total_strategies INTEGER DEFAULT 0,
    capital_usage DECIMAL(6,4) DEFAULT 0,
    sector_concentration DECIMAL(6,4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_portfolio_status_timestamp
ON portfolio_status (timestamp DESC);

-- 创建策略性能表（如果不存在）
CREATE TABLE IF NOT EXISTS strategy_performance (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    strategy_id VARCHAR(100) NOT NULL,
    strategy_name VARCHAR(200),
    account_value DECIMAL(20,2) NOT NULL,
    cash_available DECIMAL(20,2) NOT NULL,
    total_pnl DECIMAL(20,2) DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(6,4) DEFAULT 0,
    max_drawdown DECIMAL(6,4) DEFAULT 0,
    sharpe_ratio DECIMAL(8,4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_strategy_performance_timestamp
ON strategy_performance (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_performance_strategy_id
ON strategy_performance (strategy_id, timestamp DESC);

COMMIT;
