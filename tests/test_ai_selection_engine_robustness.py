import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from cherryquant.ai.decision_engine.ai_selection_engine import AISelectionEngine
from cherryquant.ai.llm_client.openai_client import LLMClient

@pytest.fixture
def mock_ai_client():
    client = MagicMock(spec=LLMClient)
    client.get_trading_decision_async = AsyncMock()
    return client

@pytest.fixture
def ai_engine(mock_ai_client):
    return AISelectionEngine(ai_client=mock_ai_client)

@pytest.mark.asyncio
async def test_json_cleaning(ai_engine, mock_ai_client):
    """测试JSON清洗功能（去除Markdown代码块）"""
    # 模拟AI返回带Markdown的JSON
    mock_response = """
    ```json
    {
        "market_analysis": "Bullish",
        "top_opportunities": ["rb2501"],
        "selected_trade": {
            "action": "buy",
            "symbol": "rb2501",
            "exchange": "SHFE",
            "quantity": 1,
            "leverage": 1,
            "confidence": 0.9,
            "selection_rationale": "Strong trend"
        }
    }
    ```
    """
    mock_ai_client.get_trading_decision_async.return_value = mock_response
    
    # 模拟市场数据
    market_data = {
        "exchange_data": {
            "SHFE": {
                "rb2501": {"name": "螺纹钢", "current_price": 3600}
            }
        },
        "total_contracts": 1
    }
    
    # Mock _get_comprehensive_market_data
    ai_engine._get_comprehensive_market_data = AsyncMock(return_value=market_data)
    
    decision = await ai_engine.get_optimal_trade_decision(commodities=["rb"])
    
    assert decision is not None
    assert decision["selected_trade"]["symbol"] == "rb2501"
    assert decision["selected_trade"]["action"] == "buy"

@pytest.mark.asyncio
async def test_business_logic_validation_failure(ai_engine, mock_ai_client):
    """测试业务逻辑验证（拒绝不在市场数据中的合约）"""
    # 模拟AI返回不存在的合约
    mock_response = {
        "market_analysis": "Bullish",
        "top_opportunities": ["fake123"],
        "selected_trade": {
            "action": "buy",
            "symbol": "fake123",  # 不在市场数据中
            "exchange": "SHFE",
            "quantity": 1,
            "leverage": 1,
            "confidence": 0.9,
            "selection_rationale": "Hallucination"
        }
    }
    mock_ai_client.get_trading_decision_async.return_value = mock_response
    
    # 模拟市场数据（只有rb2501）
    market_data = {
        "exchange_data": {
            "SHFE": {
                "rb2501": {"name": "螺纹钢", "current_price": 3600}
            }
        },
        "total_contracts": 1
    }
    
    ai_engine._get_comprehensive_market_data = AsyncMock(return_value=market_data)
    
    # 应该返回None，因为验证失败
    decision = await ai_engine.get_optimal_trade_decision(commodities=["rb"])
    
    assert decision is None

@pytest.mark.asyncio
async def test_retry_mechanism(ai_engine, mock_ai_client):
    """测试重试机制"""
    # 第一次返回非法JSON，第二次返回正常JSON
    bad_response = "Not a JSON"
    good_response = {
        "market_analysis": "Bullish",
        "top_opportunities": ["rb2501"],
        "selected_trade": {
            "action": "buy",
            "symbol": "rb2501",
            "exchange": "SHFE",
            "quantity": 1,
            "leverage": 1,
            "confidence": 0.9,
            "selection_rationale": "Retry success"
        }
    }
    
    mock_ai_client.get_trading_decision_async.side_effect = [bad_response, good_response]
    
    market_data = {
        "exchange_data": {
            "SHFE": {
                "rb2501": {"name": "螺纹钢", "current_price": 3600}
            }
        },
        "total_contracts": 1
    }
    
    ai_engine._get_comprehensive_market_data = AsyncMock(return_value=market_data)
    
    decision = await ai_engine.get_optimal_trade_decision(commodities=["rb"], max_retries=2)
    
    assert decision is not None
    assert decision["selected_trade"]["symbol"] == "rb2501"
    # 验证调用了2次
    assert mock_ai_client.get_trading_decision_async.call_count == 2
