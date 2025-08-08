#!/usr/bin/env python3
"""
Unit test: minimal Hyperbolic integration contract.
"""

import os
import pytest

from src.agents.hyperbolic_agent import HyperbolicKnowledgeAgent

@pytest.mark.asyncio
async def test_hyperbolic_minimal_generation_contract():
    # Skip if no API key is present
    if not os.getenv("HYPERBOLIC_API_KEY"):
        pytest.skip("HYPERBOLIC_API_KEY not set; skipping live test")
    agent = HyperbolicKnowledgeAgent()
    # Simple query to validate call/response structure
    result = await agent.answer_question([], query_text="Say 'hello'.")
    assert isinstance(result, dict)
    assert "formatted_response" in result
    fr = result["formatted_response"]
    assert isinstance(fr, dict)
    assert "response" in fr
    assert isinstance(fr["response"], str)


