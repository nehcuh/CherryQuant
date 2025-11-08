"""
OpenAI客户端封装
用于调用GPT模型进行交易决策
"""

import os
import json
import asyncio
import re
from typing import Dict, Any, Optional, Protocol
from openai import AsyncOpenAI
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """LLM客户端协议定义"""

    async def get_trading_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> Optional[Dict[str, Any]]:
        """获取AI交易决策"""
        ...

    async def test_connection(self) -> bool:
        """测试连接"""
        ...


class AsyncOpenAIClient:
    """异步OpenAI客户端类"""

    def __init__(self):
        """初始化OpenAI客户端"""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("OPENAI_MODEL") or os.getenv("MODEL_NAME") or "gpt-4"
        # 可配置的超时、重试与限速
        self.timeout = int(os.getenv("OPENAI_TIMEOUT", os.getenv("API_TIMEOUT", "30")))
        self.max_retries = int(os.getenv("OPENAI_MAX_RETRIES", os.getenv("MAX_RETRIES", "3")))
        self.requests_per_minute = int(os.getenv("OPENAI_REQUESTS_PER_MINUTE", "30"))
        self._min_interval = 60.0 / self.requests_per_minute if self.requests_per_minute > 0 else 0.0
        self._last_request_time = 0.0

        # 允许无密钥初始化（演示/测试降级），在调用时再做可用性判断
        if not self.api_key:
            self.client = None
            logger.info("OPENAI_API_KEY 未设置，将使用降级/模拟模式")
        else:
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        self._closed = False

    async def get_trading_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> Optional[Dict[str, Any]]:
        """
        获取AI交易决策

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词（包含市场数据）
            model: 使用的模型，如果为None则使用配置的默认模型
            temperature: 温度参数（控制随机性）
            max_tokens: 最大token数

        Returns:
            交易决策字典，或None（如果失败）
        """
        try:
            # 无可用客户端时降级返回 None（由上层选择模拟路径）
            if not self.client:
                logger.info("OpenAI 客户端未初始化，跳过真实调用")
                return None

            # 调用OpenAI API（超时、重试、限速）
            model_to_use = model or self.model
            last_exc = None
            for attempt in range(1, self.max_retries + 1):
                await self._wait_for_rate_limit()
                try:
                    coro = self.client.chat.completions.create(
                        model=model_to_use,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    response = await asyncio.wait_for(coro, timeout=self.timeout)
                    self._last_request_time = asyncio.get_event_loop().time()
                    break
                except asyncio.TimeoutError as e:
                    last_exc = e
                    logger.warning(f"OpenAI 请求超时（{self.timeout}s），重试 {attempt}/{self.max_retries}")
                except Exception as e:
                    last_exc = e
                    logger.warning(f"OpenAI 请求失败（第 {attempt} 次）: {e}")
                # 指数退避
                await asyncio.sleep(min(2 ** (attempt - 1), 10))
            else:
                logger.error(f"OpenAI 多次重试后仍失败: {last_exc}")
                return None

            # 获取回复内容
            content = response.choices[0].message.content
            logger.info(f"AI原始回复: {content}")

            # 解析JSON（容忍 ```json 代码块 包裹）
            decision = self._parse_decision_json(content)

            # 验证必需字段
            self._validate_decision(decision)

            return decision

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"原始内容: {content}")
            return None

        except Exception as e:
            logger.error(f"调用OpenAI API失败: {e}")
            return None

    def _validate_decision(self, decision: Dict[str, Any]) -> bool:
        """
        验证交易决策的格式和字段

        Args:
            decision: 交易决策字典

        Returns:
            验证是否通过

        Raises:
            ValueError: 验证失败时抛出
        """
        required_fields = [
            "signal",
            "symbol",
            "quantity",
            "leverage",
            "profit_target",
            "stop_loss",
            "confidence",
            "invalidation_condition",
            "justification",
        ]

        for field in required_fields:
            if field not in decision:
                raise ValueError(f"缺少必需字段: {field}")

        # 验证信号类型
        valid_signals = ["buy_to_enter", "sell_to_enter", "hold", "close"]
        if decision["signal"] not in valid_signals:
            raise ValueError(f"无效的信号类型: {decision['signal']}")

        # 验证数值范围
        if not 0 <= decision["confidence"] <= 1:
            raise ValueError("confidence必须在0-1之间")

        if not 1 <= decision["leverage"] <= 10:
            raise ValueError("leverage必须在1-10之间")

        # 如果不是hold信号，quantity必须大于0
        if decision["signal"] != "hold" and decision["quantity"] <= 0:
            raise ValueError("非hold信号的quantity必须大于0")

        return True

    def _parse_decision_json(self, content: str) -> Dict[str, Any]:
        """从模型回复中提取 JSON（支持 ```json 代码块、前后噪声）"""
        text = (content or "").strip()
        # 优先匹配 ```json ... ``` 代码块
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if m:
            text = m.group(1).strip()
        # 退化：截取第一个大括号块
        if not text.startswith("{"):
            brace_start = text.find("{")
            brace_end = text.rfind("}")
            if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                text = text[brace_start:brace_end+1]
        return json.loads(text)

    async def _wait_for_rate_limit(self) -> None:
        """简单的每分钟速率限制"""
        if self._min_interval <= 0:
            return
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)

    async def test_connection(self) -> bool:
        """
        测试API连接

        Returns:
            连接是否正常
        """
        try:
            if not self.client:
                logger.info("OpenAI 客户端未初始化（无 API Key），连接测试返回 False")
                return False
            await self._wait_for_rate_limit()
            try:
                coro = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=10,
                )
                _ = await asyncio.wait_for(coro, timeout=self.timeout)
                self._last_request_time = asyncio.get_event_loop().time()
                logger.info(f"API连接测试成功，使用模型: {self.model}")
                return True
            except asyncio.TimeoutError:
                logger.error(f"API连接测试超时（{self.timeout}s）")
                return False
        except Exception as e:
            logger.error(f"API连接测试失败: {e}")
            return False


# 向后兼容的同步版本
    # 兼容调用方期望的异步方法名（_async 后缀）
    async def get_trading_decision_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> Optional[Dict[str, Any]]:
        return await self.get_trading_decision(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def test_connection_async(self) -> bool:
        return await self.test_connection()

    async def aclose(self) -> None:
        """安全关闭底层HTTP客户端，避免事件循环关闭后的异常"""
        try:
            if self.client and not self._closed:
                if hasattr(self.client, "aclose"):
                    await self.client.aclose()  # type: ignore[attr-defined]
                elif hasattr(self.client, "close"):
                    await self.client.close()  # type: ignore[attr-defined]
                self._closed = True
        except RuntimeError as e:  # 例如: Event loop is closed
            if "Event loop is closed" in str(e):
                logger.debug("忽略在事件循环关闭后的HTTP客户端关闭异常")
            else:
                logger.debug(f"关闭OpenAI客户端时异常: {e}")
        except Exception as e:
            logger.debug(f"关闭OpenAI客户端时异常: {e}")

class OpenAIClient:
    """同步OpenAI客户端类（保留向后兼容）"""

    def __init__(self):
        self.async_client = AsyncOpenAIClient()

    def get_trading_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> Optional[Dict[str, Any]]:
        """同步版本 - 仍然使用事件循环执行异步操作"""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.async_client.get_trading_decision(
                    system_prompt,
                    user_prompt,
                    model,
                    temperature,
                    max_tokens
                )
            )
        finally:
            loop.close()

    def test_connection(self) -> bool:
        """同步测试连接"""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.async_client.test_connection()
            )
        finally:
            loop.close()
