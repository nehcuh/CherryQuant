-- CherryQuant 数据库初始化脚本
-- 创建时序数据库结构

-- 启用 TimescaleDB 扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 创建期货合约主表
CREATE TABLE IF NOT EXISTS futures_contracts (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    name VARCHAR(100),
    contract_size INTEGER,
    margin_rate DECIMAL(5,4),
    price_tick DECIMAL(10,4),
    trading_unit VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_futures_contracts_symbol_exchange
ON futures_contracts (symbol, exchange);

-- 创建市场数据表（时序数据）
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open_price DECIMAL(15,4),
    high_price DECIMAL(15,4),
    low_price DECIMAL(15,4),
    close_price DECIMAL(15,4),
    volume BIGINT,
    open_interest BIGINT,
    turnover DECIMAL(20,4),
    settlement_price DECIMAL(15,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建市场数据表的复合索引
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time
ON market_data (symbol, time DESC);

CREATE INDEX IF NOT EXISTS idx_market_data_timeframe_time
ON market_data (timeframe, time DESC);

-- 为UPSERT提供唯一约束
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_data_unique
ON market_data (time, symbol, exchange, timeframe);

-- 转换为时序表（TimescaleDB）
SELECT create_hypertable('market_data', 'time', chunk_time_interval => INTERVAL '1 day');

-- 创建技术指标表
CREATE TABLE IF NOT EXISTS technical_indicators (
    time TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,

    -- 移动平均线
    ma5 DECIMAL(15,4),
    ma10 DECIMAL(15,4),
    ma20 DECIMAL(15,4),
    ma60 DECIMAL(15,4),
    ema12 DECIMAL(15,4),
    ema26 DECIMAL(15,4),

    -- MACD指标
    macd DECIMAL(10,6),
    macd_signal DECIMAL(10,6),
    macd_histogram DECIMAL(10,6),

    -- KDJ指标
    kdj_k DECIMAL(6,2),
    kdj_d DECIMAL(6,2),
    kdj_j DECIMAL(6,2),

    -- RSI指标
    rsi DECIMAL(6,2),

    -- 布林带
    bb_upper DECIMAL(15,4),
    bb_middle DECIMAL(15,4),
    bb_lower DECIMAL(15,4),

    -- 其他指标
    atr DECIMAL(10,4),
    cci DECIMAL(10,2),
    williams_r DECIMAL(6,2),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建技术指标表的复合索引
CREATE INDEX IF NOT EXISTS idx_technical_indicators_symbol_time
ON technical_indicators (symbol, time DESC);

-- 为UPSERT提供唯一约束
CREATE UNIQUE INDEX IF NOT EXISTS idx_technical_indicators_unique
ON technical_indicators (time, symbol, exchange, timeframe);

-- 转换为时序表
SELECT create_hypertable('technical_indicators', 'time', chunk_time_interval => INTERVAL '1 day');

-- 创建AI决策记录表
CREATE TABLE IF NOT EXISTS ai_decisions (
    id SERIAL PRIMARY KEY,
    decision_time TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) NOT NULL,

    -- 决策内容
    action VARCHAR(20),
    quantity INTEGER,
    leverage INTEGER,
    entry_price DECIMAL(15,4),
    profit_target DECIMAL(15,4),
    stop_loss DECIMAL(15,4),

    -- AI分析信息
    confidence DECIMAL(4,3),
    opportunity_score INTEGER,
    selection_rationale TEXT,
    technical_analysis TEXT,
    risk_factors TEXT,

    -- 市场环境
    market_regime VARCHAR(20),
    volatility_index VARCHAR(10),

    -- 执行状态
    status VARCHAR(20) DEFAULT 'pending',
    executed_at TIMESTAMP,
    execution_price DECIMAL(15,4),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_decisions_time
ON ai_decisions (decision_time DESC);

CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol
ON ai_decisions (symbol, decision_time DESC);

-- 创建交易记录表
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) NOT NULL,

    -- 交易信息
    direction VARCHAR(10) NOT NULL, -- 'long' or 'short'
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(15,4) NOT NULL,
    exit_price DECIMAL(15,4),
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,

    -- 成本和收益
    entry_fee DECIMAL(10,2),
    exit_fee DECIMAL(10,2),
    gross_pnl DECIMAL(15,2),
    net_pnl DECIMAL(15,2),
    pnl_percentage DECIMAL(8,4),

    -- 风险管理
    stop_loss_price DECIMAL(15,4),
    take_profit_price DECIMAL(15,4),
    max_favorable_move DECIMAL(15,4),
    max_adverse_move DECIMAL(15,4),

    -- 关联信息
    ai_decision_id INTEGER REFERENCES ai_decisions(id),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time
ON trades (symbol, entry_time DESC);

CREATE INDEX IF NOT EXISTS idx_trades_ai_decision
ON trades (ai_decision_id);

-- 创建投资组合表
CREATE TABLE IF NOT EXISTS portfolio (
    id SERIAL PRIMARY KEY,
    as_of TIMESTAMP NOT NULL,

    -- 资金信息
    total_value DECIMAL(20,2) NOT NULL,
    available_cash DECIMAL(20,2) NOT NULL,
    used_margin DECIMAL(20,2) NOT NULL,
    unrealized_pnl DECIMAL(20,2) DEFAULT 0,

    -- 持仓信息
    positions_count INTEGER DEFAULT 0,
    total_exposure DECIMAL(20,2) DEFAULT 0,

    -- 风险指标
    max_drawdown DECIMAL(10,6),
    daily_var DECIMAL(15,2),
    sharpe_ratio DECIMAL(8,4),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_portfolio_as_of
ON portfolio (as_of DESC);

-- 创建市场统计表
CREATE TABLE IF NOT EXISTS market_statistics (
    time TIMESTAMP NOT NULL,
    exchange VARCHAR(10),

    -- 市场整体统计
    total_contracts INTEGER,
    active_contracts INTEGER,
    total_volume BIGINT,
    total_turnover DECIMAL(20,4),

    -- 市场情绪
    gainers_count INTEGER,
    losers_count INTEGER,
    unchanged_count INTEGER,

    -- 波动性指标
    avg_volatility DECIMAL(8,4),
    volatility_index VARCHAR(10),

    -- 市场状态
    market_regime VARCHAR(20),
    sentiment_score DECIMAL(6,4),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 转换为时序表
SELECT create_hypertable('market_statistics', 'time', chunk_time_interval => INTERVAL '1 hour');

-- 创建数据更新日志表
CREATE TABLE IF NOT EXISTS data_update_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    update_type VARCHAR(20) NOT NULL, -- 'insert', 'update', 'delete'
    records_count INTEGER DEFAULT 0,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'running', -- 'running', 'completed', 'failed'
    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建更新触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为需要的表创建更新触发器
CREATE TRIGGER update_futures_contracts_updated_at
    BEFORE UPDATE ON futures_contracts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trades_updated_at
    BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 插入一些基础期货合约数据
INSERT INTO futures_contracts (symbol, exchange, name, contract_size, margin_rate, price_tick) VALUES
('rb', 'SHFE', '螺纹钢', 10, 0.08, 1),
('i', 'DCE', '铁矿石', 100, 0.08, 0.5),
('cu', 'SHFE', '沪铜', 5, 0.08, 10),
('al', 'SHFE', '沪铝', 5, 0.08, 10),
('zn', 'SHFE', '沪锌', 5, 0.08, 5),
('au', 'SHFE', '沪金', 1000, 0.08, 0.1),
('ag', 'SHFE', '沪银', 15, 0.08, 1),
('ni', 'SHFE', '沪镍', 1, 0.08, 10),
('j', 'DCE', '焦炭', 100, 0.08, 0.5),
('jm', 'DCE', '焦煤', 60, 0.08, 0.5),
('a', 'DCE', '豆一', 10, 0.05, 1),
('c', 'DCE', '玉米', 10, 0.05, 1),
('m', 'DCE', '豆粕', 10, 0.05, 1),
('y', 'DCE', '豆油', 10, 0.05, 2),
('p', 'DCE', '棕榈油', 10, 0.05, 2),
('IF', 'CFFEX', '沪深300', 300, 0.15, 0.2),
('IC', 'CFFEX', '中证500', 200, 0.15, 0.2),
('IH', 'CFFEX', '上证50', 300, 0.15, 0.2),
('T', 'CFFEX', '10年期国债', 10000, 0.02, 0.005)
ON CONFLICT (symbol, exchange) DO NOTHING;

-- 创建数据保留策略
-- 保留1分钟数据3天
SELECT add_retention_policy('market_data', INTERVAL '3 days'),
       add_retention_policy('technical_indicators', INTERVAL '3 days');

-- 保留5分钟数据7天
-- 注意：这里通过创建不同的表来实现，或者使用数据压缩策略

-- 创建连续聚合视图用于降采样
-- 1分钟数据聚合为5分钟数据
CREATE MATERIALIZED VIEW market_data_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    symbol,
    exchange,
    timeframe,
    first(open_price, time) AS open_price,
    max(high_price) AS high_price,
    min(low_price) AS low_price,
    last(close_price, time) AS close_price,
    sum(volume) AS volume,
    avg(open_interest) AS open_interest,
    sum(turnover) AS turnover
FROM market_data
WHERE timeframe = '1m'
GROUP BY bucket, symbol, exchange, timeframe;

-- 创建连续聚合策略
SELECT add_continuous_aggregate_policy('market_data_5min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '5 minutes');

-- 创建数据压缩策略（用于历史数据压缩）
SELECT add_compression_policy('market_data', INTERVAL '7 days');

-- 创建用户和权限
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'cherryquant_user') THEN
        CREATE USER cherryquant_user WITH PASSWORD 'cherryquant_user123';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE cherryquant TO cherryquant_user;
GRANT USAGE ON SCHEMA public TO cherryquant_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cherryquant_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO cherryquant_user;

-- 创建视图用于简化查询
CREATE OR REPLACE VIEW latest_market_data AS
SELECT DISTINCT ON (symbol, exchange, timeframe)
    symbol, exchange, timeframe,
    close_price,
    volume,
    time
FROM market_data
ORDER BY symbol, exchange, timeframe, time DESC;

CREATE OR REPLACE VIEW latest_technical_indicators AS
SELECT DISTINCT ON (symbol, exchange, timeframe)
    symbol, exchange, timeframe,
    ma20, rsi, macd, kdj_k,
    time
FROM technical_indicators
ORDER BY symbol, exchange, timeframe, time DESC;

-- 创建存储过程用于数据清理
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS void AS $$
BEGIN
    -- 删除超过1年的1分钟数据
    DELETE FROM market_data
    WHERE timeframe = '1m'
    AND time < NOW() - INTERVAL '1 year';

    -- 删除超过2年的技术指标数据
    DELETE FROM technical_indicators
    WHERE time < NOW() - INTERVAL '2 years';

    -- 记录清理日志
    INSERT INTO data_update_log (table_name, update_type, records_count, start_time, end_time, status)
    VALUES ('market_data', 'cleanup', 0, NOW(), NOW(), 'completed');
END;
$$ LANGUAGE plpgsql;

-- 创建定时任务（需要pg_cron扩展）
-- SELECT cron.schedule('cleanup-old-data', '0 2 * * 0', 'SELECT cleanup_old_data();');

COMMIT;