#!/usr/bin/env python3
"""
Minimal demo to validate Hyperbolic GPT-OSS 120B integration.

This demo showcases the Bitcoin Knowledge Agent using the Hyperbolic API
for answering Bitcoin and blockchain-related questions.
"""

import argparse
import asyncio

from btc_max_knowledge_agent.agents.hyperbolic_knowledge_agent import (
    HyperbolicKnowledgeAgent,
)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Bitcoin Knowledge Agent - Hyperbolic GPT-OSS 120B Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo_hyperbolic_minimal.py "What is Bitcoin halving?"
  python demo_hyperbolic_minimal.py "Explain blockchain consensus mechanisms"
  python demo_hyperbolic_minimal.py --query "How does Bitcoin mining work?"
        """,
    )

    parser.add_argument(
        "query",
        nargs="?",
        default="What is Bitcoin and how does it work?",
        help="The Bitcoin/blockchain question to ask the knowledge agent (default: %(default)s)",
    )

    parser.add_argument(
        "--query",
        "-q",
        dest="query_flag",
        help="Alternative way to specify the query using a flag",
    )

    return parser.parse_args()


async def main():
    """Main function to run the Bitcoin knowledge agent demo."""
    args = parse_arguments()

    # Use flag query if provided, otherwise use positional argument
    query = args.query_flag if args.query_flag else args.query

    print(f"Query: {query}")
    print("-" * 50)

    try:
        agent = HyperbolicKnowledgeAgent()
        result = await agent.answer_question([], query_text=query)

        print("Model:", result.get("model", "Unknown"))
        print("Response:")
        print(
            result.get("formatted_response", {}).get(
                "response", "No response available"
            )
        )

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
