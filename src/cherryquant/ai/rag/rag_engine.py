"""
RAG引擎 - 简化实现

核心功能：
1. 文档向量化和检索
2. 上下文增强
3. 与决策引擎集成

教学要点：
1. RAG工作流程
2. 向量检索原理
3. 上下文构建策略
"""

from datetime import datetime
import hashlib


class SimpleVectorStore:
    """简化的向量存储（教学用）"""

    def __init__(self):
        self.documents: list[dict] = []
        # {id, text, embedding, metadata, timestamp}

    def add_document(
        self,
        text: str,
        embedding: list[float],
        metadata: dict = None
    ):
        """添加文档"""
        doc_id = hashlib.md5(text.encode()).hexdigest()[:16]

        self.documents.append({
            "id": doc_id,
            "text": text,
            "embedding": embedding,
            "metadata": metadata or {},
            "timestamp": datetime.now(),
        })

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 3
    ) -> list[dict]:
        """
        检索最相似的文档

        使用余弦相似度
        """
        if not self.documents:
            return []

        # 计算相似度
        scores = []
        for doc in self.documents:
            similarity = self._cosine_similarity(
                query_embedding,
                doc["embedding"]
            )
            scores.append((doc, similarity))

        # 排序并返回top_k
        scores.sort(key=lambda x: x[1], reverse=True)

        return [
            {
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": score,
            }
            for doc, score in scores[:top_k]
        ]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x ** 2 for x in a) ** 0.5
        norm_b = sum(x ** 2 for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


class RAGEngine:
    """
    RAG引擎

    教学要点：
    1. 如何构建RAG系统
    2. 检索增强生成流程
    3. 上下文构建
    """

    def __init__(self, vector_store: SimpleVectorStore = None):
        self.vector_store = vector_store or SimpleVectorStore()

        # 示例：预加载一些市场知识
        self._load_market_knowledge()

    def _load_market_knowledge(self):
        """加载市场知识库（示例）"""
        knowledge = [
            {
                "text": "螺纹钢价格受到铁矿石价格、钢铁产量、房地产需求等因素影响",
                "embedding": self._simple_hash_embedding("螺纹钢 铁矿石 房地产"),
                "metadata": {"category": "fundamental", "symbol": "rb"},
            },
            {
                "text": "RSI超过70通常被认为是超买信号，可能预示价格回调",
                "embedding": self._simple_hash_embedding("RSI 超买 回调"),
                "metadata": {"category": "technical", "indicator": "RSI"},
            },
            {
                "text": "MACD金叉（快线上穿慢线）是常见的做多信号",
                "embedding": self._simple_hash_embedding("MACD 金叉 做多"),
                "metadata": {"category": "technical", "indicator": "MACD"},
            },
            {
                "text": "布林带收窄通常预示波动率降低，可能即将突破",
                "embedding": self._simple_hash_embedding("布林带 波动率 突破"),
                "metadata": {"category": "technical", "indicator": "Bollinger"},
            },
        ]

        for item in knowledge:
            self.vector_store.add_document(
                text=item["text"],
                embedding=item["embedding"],
                metadata=item["metadata"],
            )

    def _simple_hash_embedding(self, text: str) -> list[float]:
        """
        简化的embedding（实际应该用OpenAI或本地模型）

        教学用：使用hash生成伪向量
        """
        import hashlib

        # 生成128维向量
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()

        # 转换为浮点向量
        embedding = []
        for i in range(0, len(hash_bytes), 2):
            val = (hash_bytes[i] * 256 + hash_bytes[i+1]) / 65535 - 0.5
            embedding.append(val)

        # 扩展到128维
        while len(embedding) < 128:
            embedding.extend(embedding[:128-len(embedding)])

        return embedding[:128]

    def retrieve_context(
        self,
        query: str,
        top_k: int = 3
    ) -> str:
        """
        检索相关上下文

        Args:
            query: 查询文本
            top_k: 返回top k个结果

        Returns:
            拼接的上下文文本
        """
        # 生成查询向量
        query_embedding = self._simple_hash_embedding(query)

        # 检索相关文档
        results = self.vector_store.search(query_embedding, top_k=top_k)

        if not results:
            return ""

        # 构建上下文
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"{i}. {result['text']} (相关度: {result['score']:.2f})"
            )

        return "\n".join(context_parts)

    def enhance_decision_context(
        self,
        symbol: str,
        market_context: dict
    ) -> dict:
        """
        增强决策上下文

        Args:
            symbol: 品种代码
            market_context: 市场上下文

        Returns:
            增强后的上下文
        """
        # 构建查询
        indicators = market_context.get("indicators", {})
        query_parts = [
            symbol,
            f"RSI {indicators.get('rsi_14', 50):.0f}",
            f"MACD {indicators.get('macd_hist', 0):.2f}",
        ]
        query = " ".join(query_parts)

        # 检索相关知识
        retrieved_context = self.retrieve_context(query, top_k=3)

        # 添加到市场上下文
        enhanced_context = market_context.copy()
        enhanced_context["rag_context"] = retrieved_context

        return enhanced_context


# 使用示例
if __name__ == "__main__":
    # 创建RAG引擎
    rag = RAGEngine()

    # 检索上下文
    context = rag.retrieve_context("螺纹钢 RSI 70 超买")
    print("检索到的上下文：")
    print(context)

    # 增强决策上下文
    market_ctx = {
        "symbol": "rb2501",
        "indicators": {
            "rsi_14": 72.0,
            "macd_hist": 3.5,
        }
    }

    enhanced = rag.enhance_decision_context("rb2501", market_ctx)
    print("\n增强后的上下文：")
    print(enhanced.get("rag_context"))
