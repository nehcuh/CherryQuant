"""
多模型适配器

支持多种LLM：
1. OpenAI (GPT-4)
2. Anthropic (Claude)
3. 本地模型 (Llama, etc.)

教学要点：
1. 适配器模式
2. 统一接口设计
3. 模型性能对比
"""

from abc import ABC, abstractmethod
from typing import Dict, List
from enum import Enum


class ModelProvider(Enum):
    """模型提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class BaseLLMAdapter(ABC):
    """LLM适配器基类"""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> Dict:
        """
        聊天补全

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度
            max_tokens: 最大token数

        Returns:
            响应字典
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict:
        """获取模型信息"""
        pass


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI适配器（已实现）"""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        self.api_key = api_key
        self.model = model

    async def chat_completion(self, messages, temperature=0.2, max_tokens=1000):
        # 实际调用OpenAI API
        # （使用现有的 AsyncOpenAIClient）
        from src.cherryquant.ai.llm_client.openai_client import AsyncOpenAIClient
        from config.settings.settings import AIConfig

        config = AIConfig(
            openai_api_key=self.api_key,
            openai_model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        client = AsyncOpenAIClient(config)
        response = await client.chat_completion(messages, temperature, max_tokens)
        await client.aclose()

        return response

    def get_model_info(self):
        return {
            "provider": ModelProvider.OPENAI.value,
            "model": self.model,
            "max_context": 128000,  # GPT-4 Turbo
            "cost_per_1k_input": 0.01,
            "cost_per_1k_output": 0.03,
        }


class AnthropicAdapter(BaseLLMAdapter):
    """
    Anthropic (Claude) 适配器（真实实现）

    教学要点：
    - Anthropic API使用
    - 消息格式转换（OpenAI格式 → Claude格式）
    - 错误处理和重试
    - Python 3.12+ 类型注解

    安装依赖: pip install anthropic
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str | None = None
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        """延迟初始化客户端"""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                if self.base_url:
                    self._client = AsyncAnthropic(
                        api_key=self.api_key,
                        base_url=self.base_url
                    )
                else:
                    self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. "
                    "Install it with: pip install anthropic"
                )
        return self._client

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1000
    ) -> dict:
        """
        Claude API调用（真实实现）

        Args:
            messages: OpenAI格式消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            OpenAI格式的响应（为了保持接口统一）

        教学要点：
        - OpenAI格式 → Claude格式转换
        - system message特殊处理
        - 响应格式适配
        """
        client = self._get_client()

        # 转换消息格式
        system_message = ""
        claude_messages = []

        for msg in messages:
            if msg["role"] == "system":
                # Claude将system message作为单独参数
                system_message = msg["content"]
            else:
                claude_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # 调用Claude API
        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_message if system_message else None,
                messages=claude_messages
            )

            # 转换为OpenAI格式响应（保持接口统一）
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": response.content[0].text
                    }
                }],
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                },
                "model": response.model,
                "id": response.id
            }

        except Exception as e:
            # 错误处理
            raise RuntimeError(f"Claude API调用失败: {str(e)}") from e

    async def aclose(self):
        """关闭客户端连接"""
        if self._client:
            await self._client.close()

    def get_model_info(self) -> dict:
        """获取模型信息"""
        # 根据模型名称返回不同的配置
        if "claude-3-5-sonnet" in self.model:
            return {
                "provider": ModelProvider.ANTHROPIC.value,
                "model": self.model,
                "max_context": 200000,
                "cost_per_1k_input": 0.003,
                "cost_per_1k_output": 0.015,
                "description": "Claude 3.5 Sonnet - 平衡性能与成本"
            }
        elif "claude-3-opus" in self.model:
            return {
                "provider": ModelProvider.ANTHROPIC.value,
                "model": self.model,
                "max_context": 200000,
                "cost_per_1k_input": 0.015,
                "cost_per_1k_output": 0.075,
                "description": "Claude 3 Opus - 最强性能"
            }
        elif "claude-3-haiku" in self.model:
            return {
                "provider": ModelProvider.ANTHROPIC.value,
                "model": self.model,
                "max_context": 200000,
                "cost_per_1k_input": 0.00025,
                "cost_per_1k_output": 0.00125,
                "description": "Claude 3 Haiku - 最快速度"
            }
        else:
            return {
                "provider": ModelProvider.ANTHROPIC.value,
                "model": self.model,
                "max_context": 200000,
                "cost_per_1k_input": 0.003,
                "cost_per_1k_output": 0.015,
            }


class LocalLLMAdapter(BaseLLMAdapter):
    """
    本地模型适配器（真实实现）

    支持两种后端：
    1. Ollama (推荐) - 简单易用
    2. llama-cpp-python - 更灵活

    教学要点：
    - 本地LLM部署
    - Python 3.12+ async/await
    - 异步HTTP请求

    安装依赖:
    - Ollama: brew install ollama (macOS)
    - llama-cpp-python: pip install llama-cpp-python
    """

    def __init__(
        self,
        model_name: str = "llama3.2:3b",
        backend: str = "ollama",
        ollama_base_url: str = "http://localhost:11434",
        model_path: str | None = None,
    ):
        """
        初始化本地LLM适配器

        Args:
            model_name: 模型名称（ollama）或路径（llama-cpp）
            backend: 后端类型（"ollama" | "llama-cpp"）
            ollama_base_url: Ollama服务地址
            model_path: llama-cpp模型文件路径
        """
        self.model_name = model_name
        self.backend = backend
        self.ollama_base_url = ollama_base_url
        self.model_path = model_path
        self._llm_instance = None

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1000
    ) -> dict:
        """
        本地模型推理（真实实现）

        Args:
            messages: OpenAI格式消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            OpenAI格式的响应

        教学要点：
        - 异步HTTP请求
        - Ollama API调用
        - 响应格式适配
        """
        match self.backend:
            case "ollama":
                return await self._ollama_chat(messages, temperature, max_tokens)
            case "llama-cpp":
                return await self._llama_cpp_chat(messages, temperature, max_tokens)
            case _:
                raise ValueError(f"不支持的后端: {self.backend}")

    async def _ollama_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> dict:
        """使用Ollama进行推理"""
        import httpx

        url = f"{self.ollama_base_url}/api/chat"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                # 转换为OpenAI格式
                return {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": data["message"]["content"]
                        }
                    }],
                    "usage": {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                    },
                    "model": self.model_name,
                }

        except httpx.HTTPError as e:
            raise RuntimeError(
                f"Ollama API调用失败: {str(e)}\n"
                f"请确保Ollama服务已启动: ollama serve"
            ) from e
        except Exception as e:
            raise RuntimeError(f"本地模型推理失败: {str(e)}") from e

    async def _llama_cpp_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> dict:
        """使用llama-cpp-python进行推理"""
        if self._llm_instance is None:
            try:
                from llama_cpp import Llama
                if not self.model_path:
                    raise ValueError("llama-cpp backend需要model_path参数")

                self._llm_instance = Llama(
                    model_path=self.model_path,
                    n_ctx=4096,  # 上下文长度
                    n_threads=4,  # 线程数
                    verbose=False
                )
            except ImportError:
                raise ImportError(
                    "llama-cpp-python not installed. "
                    "Install it with: pip install llama-cpp-python"
                )

        # llama-cpp-python支持OpenAI格式
        response = self._llm_instance.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response

    def get_model_info(self) -> dict:
        """获取模型信息"""
        match self.backend:
            case "ollama":
                context_length = self._guess_context_length(self.model_name)
                return {
                    "provider": ModelProvider.LOCAL.value,
                    "model": self.model_name,
                    "backend": "ollama",
                    "max_context": context_length,
                    "cost_per_1k_input": 0.0,  # 本地免费
                    "cost_per_1k_output": 0.0,
                    "description": f"Ollama本地模型: {self.model_name}"
                }
            case "llama-cpp":
                return {
                    "provider": ModelProvider.LOCAL.value,
                    "model": self.model_path or "local-model",
                    "backend": "llama-cpp",
                    "max_context": 4096,
                    "cost_per_1k_input": 0.0,
                    "cost_per_1k_output": 0.0,
                    "description": "llama-cpp-python本地模型"
                }
            case _:
                return {
                    "provider": ModelProvider.LOCAL.value,
                    "model": "unknown",
                    "max_context": 4096,
                    "cost_per_1k_input": 0.0,
                    "cost_per_1k_output": 0.0,
                }

    def _guess_context_length(self, model_name: str) -> int:
        """根据模型名称推测上下文长度"""
        if "llama3" in model_name or "llama-3" in model_name:
            return 8192
        if "mistral" in model_name:
            return 8192
        if "qwen" in model_name:
            return 32768
        return 4096  # 默认值


class MultiModelManager:
    """
    多模型管理器

    教学要点：
    1. 如何管理多个模型
    2. 成本和性能权衡
    3. A/B测试
    """

    def __init__(self):
        self.adapters: Dict[str, BaseLLMAdapter] = {}
        self.usage_stats: Dict[str, Dict] = {}  # 使用统计

    def register_model(self, name: str, adapter: BaseLLMAdapter):
        """注册模型"""
        self.adapters[name] = adapter
        self.usage_stats[name] = {
            "calls": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

    async def call_model(
        self,
        model_name: str,
        messages: List[Dict],
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> Dict:
        """调用指定模型"""
        if model_name not in self.adapters:
            raise ValueError(f"Model {model_name} not registered")

        adapter = self.adapters[model_name]

        # 调用模型
        response = await adapter.chat_completion(messages, temperature, max_tokens)

        # 更新统计
        self._update_stats(model_name, response, adapter)

        return response

    def _update_stats(self, model_name: str, response: Dict, adapter: BaseLLMAdapter):
        """更新使用统计"""
        stats = self.usage_stats[model_name]
        stats["calls"] += 1

        # 估算token数（简化）
        if "usage" in response:
            tokens = response["usage"].get("total_tokens", 0)
            stats["total_tokens"] += tokens

            # 估算成本
            model_info = adapter.get_model_info()
            cost = (tokens / 1000) * model_info.get("cost_per_1k_input", 0)
            stats["total_cost"] += cost

    def get_stats_summary(self) -> Dict:
        """获取统计摘要"""
        return {
            model: {
                "calls": stats["calls"],
                "total_tokens": stats["total_tokens"],
                "total_cost": f"${stats['total_cost']:.2f}",
                "avg_tokens_per_call": stats["total_tokens"] / stats["calls"] if stats["calls"] > 0 else 0,
            }
            for model, stats in self.usage_stats.items()
        }

    async def ab_test(
        self,
        model_a: str,
        model_b: str,
        messages: List[Dict],
    ) -> Dict:
        """
        A/B测试两个模型

        Returns:
            {
                "model_a": {...},
                "model_b": {...},
                "comparison": {...}
            }
        """
        import time

        # 调用模型A
        start_a = time.time()
        response_a = await self.call_model(model_a, messages)
        time_a = time.time() - start_a

        # 调用模型B
        start_b = time.time()
        response_b = await self.call_model(model_b, messages)
        time_b = time.time() - start_b

        return {
            "model_a": {
                "name": model_a,
                "response": response_a,
                "latency": time_a,
            },
            "model_b": {
                "name": model_b,
                "response": response_b,
                "latency": time_b,
            },
            "comparison": {
                "faster": model_a if time_a < time_b else model_b,
                "latency_diff": abs(time_a - time_b),
            }
        }


# 使用示例
if __name__ == "__main__":
    import asyncio

    async def demo():
        # 创建管理器
        manager = MultiModelManager()

        # 注册模型
        manager.register_model(
            "gpt4",
            OpenAIAdapter(api_key="your-key", model="gpt-4-turbo-preview")
        )
        manager.register_model(
            "claude",
            AnthropicAdapter(api_key="your-key")
        )

        # 调用模型
        messages = [{"role": "user", "content": "分析螺纹钢走势"}]

        response = await manager.call_model("gpt4", messages)
        print(response)

        # 查看统计
        stats = manager.get_stats_summary()
        print(stats)

    asyncio.run(demo())
