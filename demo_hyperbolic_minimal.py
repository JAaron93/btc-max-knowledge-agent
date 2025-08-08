#!/usr/bin/env python3
"""
Minimal demo to validate Hyperbolic GPT-OSS 120B integration.

Run:
  python demo_hyperbolic_minimal.py "What is Bitcoin halving?"
"""

import asyncio
import sys

from btc_max_knowledge_agent.agents.hyperbolic_agent import (
    HyperbolicKnowledgeAgent,
)


async def main():
    query = (
        " ".join(sys.argv[1:]).strip() or "Explain Bitcoin in one paragraph."
    )
    agent = HyperbolicKnowledgeAgent()
    result = await agent.answer_question([], query_text=query)
    print("Model:", result.get("model"))
    print(
        "Response:\n",
        result.get("formatted_response", {}).get("response", ""),
    )

if __name__ == "__main__":
    asyncio.run(main())
