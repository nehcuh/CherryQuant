"""
RAG (Retrieval-Augmented Generation) 系统

功能：
1. 向量化市场文档和新闻
2. 语义检索相关信息
3. 增强AI决策上下文

教学要点：
1. Embedding和向量检索
2. RAG架构设计
3. 上下文增强策略
"""

from .embedder import TextEmbedder
from .vector_store import VectorStore
from .retriever import MarketContextRetriever
from .rag_engine import RAGEngine

__all__ = [
    "TextEmbedder",
    "VectorStore",
    "MarketContextRetriever",
    "RAGEngine",
]
