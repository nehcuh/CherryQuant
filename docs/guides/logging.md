# CherryQuant 日志使用指南

## 概述

CherryQuant 使用 `structlog` 提供结构化日志记录，支持开发和生产环境的不同输出格式。

## 基本用法

### 1. 导入日志器

```python
from cherryquant.logging_config import get_logger

logger = get_logger(__name__)
```

### 2. 记录日志

#### 旧的方式（不推荐）

```python
# ❌ 避免使用字符串格式化和 emoji
logger.info("✅ Connected to MongoDB")
logger.error(f"❌ Failed to connect: {error}")
```

#### 新的方式（推荐）

```python
# ✅ 使用结构化日志，键值对表示上下文
logger.info("mongodb_connected", database="cherryquant", host="localhost")
logger.error("connection_failed", error=str(error), component="mongodb")
```

## 日志级别

```python
logger.debug("debug_info", details="...")
logger.info("operation_complete", result="success")
logger.warning("potential_issue", reason="...")
logger.error("operation_failed", error="...", traceback=True)
logger.critical("system_failure", severity="high")
```

## 结构化上下文

### 添加持久上下文

```python
from cherryquant.logging_config import get_logger
import structlog

logger = get_logger(__name__)

# 绑定上下文到logger实例
logger = logger.bind(user_id="123", session_id="abc")

# 后续所有日志都会包含这些字段
logger.info("user_action", action="login")
# 输出: {"event": "user_action", "action": "login", "user_id": "123", "session_id": "abc"}
```

### 临时上下文

```python
from structlog import contextvars

# 在整个请求/任务期间绑定上下文
contextvars.bind_contextvars(request_id="req-123")

# 所有logger都会包含这个上下文
logger.info("processing_request")

# 清理上下文
contextvars.clear_contextvars()
```

## 实际示例

### 交易决策日志

```python
from cherryquant.logging_config import get_logger

logger = get_logger(__name__)

class FuturesEngine:
    async def make_decision(self, symbol: str, data: dict):
        logger.info(
            "ai_decision_started",
            symbol=symbol,
            data_points=len(data),
            model=self.config.ai.model
        )

        try:
            decision = await self.llm_client.get_decision(data)

            logger.info(
                "ai_decision_complete",
                symbol=symbol,
                decision=decision.action,
                confidence=decision.confidence,
                reasoning=decision.reason
            )

            return decision

        except Exception as e:
            logger.error(
                "ai_decision_failed",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True  # 包含完整堆栈跟踪
            )
            raise
```

### 数据获取日志

```python
from cherryquant.logging_config import get_logger
import time

logger = get_logger(__name__)

class MarketDataManager:
    async def fetch_data(self, symbols: list[str], start_date: str):
        start_time = time.time()

        logger.info(
            "data_fetch_started",
            symbols=symbols,
            symbol_count=len(symbols),
            start_date=start_date
        )

        try:
            data = await self._fetch_from_source(symbols, start_date)

            duration = time.time() - start_time
            logger.info(
                "data_fetch_complete",
                symbols=symbols,
                records=len(data),
                duration_seconds=round(duration, 2),
                source=self.data_source
            )

            return data

        except Exception as e:
            logger.error(
                "data_fetch_failed",
                symbols=symbols,
                error=str(e),
                duration_seconds=round(time.time() - start_time, 2),
                exc_info=True
            )
            raise
```

### 风险管理日志

```python
from cherryquant.logging_config import get_logger

logger = get_logger(__name__)

class RiskManager:
    def check_position_limits(self, symbol: str, quantity: int, price: float):
        position_value = quantity * price

        if position_value > self.max_position_value:
            logger.warning(
                "position_limit_exceeded",
                symbol=symbol,
                quantity=quantity,
                value=position_value,
                limit=self.max_position_value,
                excess_pct=round((position_value / self.max_position_value - 1) * 100, 2)
            )
            return False

        logger.info(
            "position_limit_check_passed",
            symbol=symbol,
            quantity=quantity,
            value=position_value,
            limit_usage_pct=round(position_value / self.max_position_value * 100, 2)
        )
        return True
```

## 配置

### 环境变量

```bash
# 日志级别
LOG_LEVEL=INFO

# JSON格式输出（生产环境推荐）
LOG_JSON=true

# 彩色输出（开发环境）
LOG_COLORS=true
```

### 在代码中配置

```python
from cherryquant.logging_config import configure_logging

# 开发环境：彩色、人类可读
configure_logging(
    log_level="DEBUG",
    json_logs=False,
    enable_colors=True
)

# 生产环境：JSON格式，便于日志聚合
configure_logging(
    log_level="INFO",
    json_logs=True,
    enable_colors=False
)
```

## 输出示例

### 开发环境（彩色格式）

```
2025-11-18T10:30:45.123456Z [info     ] ai_decision_started       symbol=rb2501 data_points=100 model=gpt-4
2025-11-18T10:30:47.456789Z [info     ] ai_decision_complete      symbol=rb2501 decision=BUY confidence=0.85 reasoning="Strong uptrend"
```

### 生产环境（JSON格式）

```json
{"event": "ai_decision_started", "level": "info", "timestamp": "2025-11-18T10:30:45.123456Z", "app": "cherryquant", "logger": "cherryquant.ai.decision_engine", "symbol": "rb2501", "data_points": 100, "model": "gpt-4"}
{"event": "ai_decision_complete", "level": "info", "timestamp": "2025-11-18T10:30:47.456789Z", "app": "cherryquant", "logger": "cherryquant.ai.decision_engine", "symbol": "rb2501", "decision": "BUY", "confidence": 0.85, "reasoning": "Strong uptrend"}
```

## 最佳实践

### ✅ 推荐做法

1. **使用描述性的事件名称**
   ```python
   logger.info("user_login_successful", user_id=123)  # ✅ 清晰
   ```

2. **包含相关上下文**
   ```python
   logger.error("database_query_failed",
                query=query,
                table=table,
                duration_ms=duration,
                error=str(e))  # ✅ 完整信息
   ```

3. **使用一致的命名规范**
   ```python
   # ✅ 使用 snake_case，描述性名称
   logger.info("order_executed", order_id=123, symbol="rb2501")
   ```

4. **避免敏感信息**
   ```python
   # ✅ 脱敏处理
   logger.info("api_call", api_key="****" + api_key[-4:])
   ```

### ❌ 避免的做法

1. **不要使用字符串格式化**
   ```python
   logger.info(f"User {user_id} logged in")  # ❌ 难以解析
   logger.info("user_logged_in", user_id=user_id)  # ✅
   ```

2. **不要使用 emoji**
   ```python
   logger.info("✅ Success")  # ❌ 难以搜索和过滤
   logger.info("operation_successful")  # ✅
   ```

3. **不要记录巨大的对象**
   ```python
   logger.info("data_loaded", data=huge_dataframe)  # ❌ 日志膨胀
   logger.info("data_loaded", rows=len(huge_dataframe))  # ✅
   ```

4. **不要在循环中打印无意义的日志**
   ```python
   for item in items:
       logger.debug("processing_item", item=item)  # ❌ 日志爆炸

   logger.info("batch_processing_started", item_count=len(items))  # ✅
   # ... 处理 ...
   logger.info("batch_processing_complete", processed=len(results))  # ✅
   ```

## 日志查询和分析

### 使用 jq 查询 JSON 日志

```bash
# 查找所有错误
cat logs/app.log | jq 'select(.level == "error")'

# 查找特定symbol的交易决策
cat logs/app.log | jq 'select(.symbol == "rb2501" and .event | startswith("ai_decision"))'

# 统计事件类型
cat logs/app.log | jq -r '.event' | sort | uniq -c | sort -rn

# 查找慢查询（超过1秒）
cat logs/app.log | jq 'select(.duration_seconds > 1.0)'
```

### 集成 ELK Stack

JSON 格式的日志可以直接导入 Elasticsearch：

```bash
# 使用 Filebeat 收集日志
filebeat.yml:
  filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /path/to/cherryquant/logs/*.log
    json.keys_under_root: true
```

## 迁移现有代码

### 查找需要更新的日志

```bash
# 查找使用了 emoji 的日志
grep -r "logger.*[✅❌]" src/

# 查找使用了字符串格式化的日志
grep -r 'logger.*f"' src/
```

### 批量替换示例

```python
# 旧代码
logger.info("✅ Connected to MongoDB")

# 新代码
logger.info("mongodb_connected")
```

```python
# 旧代码
logger.error(f"❌ Failed to connect: {error}")

# 新代码
logger.error("connection_failed", error=str(error))
```

## 性能考虑

1. **延迟评估**：structlog 会延迟格式化，只在实际输出时才处理
2. **缓存**：logger 实例会被缓存，减少重复创建开销
3. **异步输出**：可以配置异步写入，避免阻塞业务逻辑

## 故障排查

### 问题：日志未显示

检查日志级别配置：
```python
from cherryquant.logging_config import configure_logging
configure_logging(log_level="DEBUG")
```

### 问题：JSON日志格式不正确

确保环境变量正确设置：
```bash
export LOG_JSON=true
```

### 问题：颜色显示异常

禁用颜色输出：
```bash
export LOG_COLORS=false
```

## 参考资源

- [structlog 官方文档](https://www.structlog.org/)
- [结构化日志最佳实践](https://www.structlog.org/en/stable/why.html)
- [Python JSON Logger](https://github.com/madzak/python-json-logger)
