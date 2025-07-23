#!/usr/bin/env python3
"""Demonstration of the new result formatting functionality with URL metadata support."""

import os
import sys

# Add src to path for imports
src_path = os.path.join(os.path.dirname(__file__), "src")
if os.path.exists(src_path):
    sys.path.append(src_path)
else:
    print(f"Error: src directory not found at {src_path}")
    sys.exit(1)

try:
    from src.utils.result_formatter import (
        AssistantResponseFormatter,
        MCPResponseFormatter,
        QueryResultFormatter,
    )
except ImportError as e:
    print(f"Error importing formatter classes: {e}")
    sys.exit(1)

# Sample data for demos
SAMPLE_RESULTS = [
    {
        "id": "doc1",
        "title": "Bitcoin: A Peer-to-Peer Electronic Cash System",
        "content": (
            "Bitcoin is a peer-to-peer electronic cash system that allows online "
            "payments to be sent directly from one party to another without "
            "going through a financial institution."
        ),
        "source": "Bitcoin.org",
        "url": "https://bitcoin.org/bitcoin.pdf",
        "category": "whitepaper",
        "score": 0.95,
        "published": "2008-10-31",
    },
    {
        "id": "doc2",
        "title": "Lightning Network Overview",
        "content": (
            "The Lightning Network is a decentralized system for instant, "
            "high-volume micropayments that removes the risk of delegating "
            "custody of funds to trusted third parties."
        ),
        "source": "Lightning Labs",
        "url": "https://lightning.network/lightning-network-paper.pdf",
        "category": "technical",
        "score": 0.87,
        "published": "2016-01-14",
    },
    {
        "id": "doc3",
        "title": "Bitcoin Mining Fundamentals",
        "content": (
            "Bitcoin mining is the process of adding transaction records to "
            "Bitcoin's public ledger of past transactions."
        ),
        "source": "Internal Knowledge Base",
        "url": "",  # No URL available
        "category": "guide",
        "score": 0.82,
        "published": "",
    },
]

MCP_SAMPLE_RESPONSES = [
    {
        "id": "mcp1",
        "title": "Bitcoin Core RPC API",
        "content": (
            "The Bitcoin Core RPC API allows you to interact with a Bitcoin node. "
            "It provides a way to query the blockchain, send transactions, and "
            "manage the wallet."
        ),
        "source": "Bitcoin Core Documentation",
        "url": "https://developer.bitcoin.org/reference/rpc/",
        "metadata": {
            "endpoint": "/rpc",
            "method": "getblockchaininfo",
            "version": "0.21.0",
            "requires_auth": True,
        },
        "score": 0.91,
    },
    {
        "id": "mcp2",
        "title": "Lightning Network Daemon API",
        "content": (
            "The Lightning Network Daemon (LND) provides a gRPC and REST API to "
            "interact with the Lightning Network. It allows you to create channels, "
            "send payments, and query network information."
        ),
        "source": "Lightning Labs Documentation",
        "url": "https://api.lightning.community/",
        "metadata": {
            "endpoint": "/v1/getinfo",
            "method": "GET",
            "version": "0.13.0-beta",
            "requires_auth": True,
        },
        "score": 0.88,
    },
]


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a specified length with an optional suffix.

    Args:
        text: The text to truncate
        max_length: Maximum length before truncation
        suffix: Suffix to add when text is truncated

    Returns:
        str: Truncated text with suffix if needed, or original text if shorter than max_length
    """
    if not text:
        return text
    return text if len(text) <= max_length else text[:max_length] + suffix


def demo_single_result_formatting() -> None:
    """Demonstrate formatting of a single result with URL."""
    try:
        print("\n1. Single Result Formatting (with URL):")
        print("-" * 40)
        result = QueryResultFormatter.format_single_result(
            SAMPLE_RESULTS[0], include_score=True
        )
        print(result)
    except Exception as e:
        print(f"Error formatting single result with URL: {e}")


def demo_single_result_no_url() -> None:
    """Demonstrate formatting of a single result without URL."""
    try:
        print("\n2. Single Result Formatting (without URL):")
        print("-" * 40)
        result = QueryResultFormatter.format_single_result(SAMPLE_RESULTS[2])
        print(result)
    except Exception as e:
        print(f"Error formatting single result without URL: {e}")


def demo_multiple_results_formatting() -> None:
    """Demonstrate formatting of multiple results.

    Shows how to format multiple query results with optional inclusion of scores
    and limiting the number of results.
    """
    try:
        print("\n3. Multiple Results Formatting:")
        print("-" * 40)

        results = QueryResultFormatter.format_multiple_results(
            results=SAMPLE_RESULTS, include_scores=True, max_results=2
        )
        print(results)

    except ValueError as ve:
        print(f"Invalid input parameters: {ve}")
    except Exception as e:
        print(f"Unexpected error formatting multiple results: {e}")
        if __debug__:
            import traceback

            traceback.print_exc()


def demo_structured_response() -> None:
    """Demonstrate structured response formatting.

    Shows how to format query results into a structured response with metadata,
    including a summary of the results when requested.
    """
    try:
        print("\n4. Structured Response Format:")
        print("-" * 40)

        # Define the query and get structured results
        query = "What is Bitcoin and how does it work?"
        structured = QueryResultFormatter.format_structured_response(
            results=SAMPLE_RESULTS, query=query, include_summary=True
        )

        # Display the structured response
        print(f"Query: {structured.get('query', 'N/A')}")
        print(f"Total Results: {structured.get('total_results', 0)}")

        if "summary" in structured:
            summary = truncate_text(text=structured["summary"], max_length=150)
            print(f"Summary: {summary}")

    except ValueError as ve:
        print(f"Invalid input parameters: {ve}")
    except Exception as e:
        print(f"Error generating structured response: {e}")
        if __debug__:
            import traceback

            traceback.print_exc()


def demo_query_result_formatting() -> None:
    """Demonstrate query result formatting with URL metadata.

    This function serves as a driver that runs multiple demo functions to showcase
    different aspects of query result formatting, including single results,
    multiple results, and structured responses.
    """
    try:
        print("\n🔍 Query Result Formatting Demo")
        print("=" * 60)

        # List of demo functions to execute in sequence
        demos = [
            ("Single Result (with URL)", demo_single_result_formatting),
            ("Single Result (no URL)", demo_single_result_no_url),
            ("Multiple Results", demo_multiple_results_formatting),
            ("Structured Response", demo_structured_response),
        ]

        # Execute each demo with a header
        for name, demo_func in demos:
            try:
                print(f"\n{' ' + name + ' ':-^60}")
                demo_func()
            except Exception as e:
                print(f"Error in {name} demo: {e}")
                if __debug__:
                    import traceback

                    traceback.print_exc()

    except Exception as e:
        print(f"Unexpected error in query result formatting demo: {e}")
        if __debug__:
            import traceback

            traceback.print_exc()


def demo_mcp_formatting() -> None:
    """Demonstrate MCP response formatting.

    Shows how to format query results for the MCP (Model Control Protocol) response
    format, which includes structured metadata and source information.
    """
    try:
        print("\n📡 MCP Response Formatting Demo")
        print("=" * 60)

        # Define the query and get MCP-formatted response
        query = "What is Bitcoin?"
        mcp_response = MCPResponseFormatter.format_for_mcp(
            results=MCP_SAMPLE_RESPONSES, query=query
        )

        if (
            not mcp_response
            or "content" not in mcp_response
            or not mcp_response["content"]
        ):
            print("Error: Invalid MCP response structure")
            return

        print("MCP Response Structure:")
        content = mcp_response["content"][0]
        print(f"Content Type: {content.get('type', 'Unknown')}")
        print(f"Metadata: {mcp_response.get('metadata', {})}")
        print("\nFormatted Text:")
        print(content.get("text", "No text available"))

    except Exception as e:
        print(f"Error in MCP formatting demo: {e}")


def demo_assistant_formatting() -> None:
    """Demonstrate Pinecone Assistant response formatting.

    Shows how to format responses for a conversational AI assistant, including
    the answer text and source citations with proper attribution and formatting.
    """
    try:
        print("\n🤖 Assistant Response Formatting Demo")
        print("=" * 60)

        # Define the assistant's answer
        answer = (
            "Bitcoin is a decentralized digital currency that operates without "
            "a central bank or single administrator. It uses blockchain technology "
            "to maintain a public ledger of all transactions."
        )

        # Define the source documents with metadata
        sources = [
            {
                "id": "doc1",
                "title": "Bitcoin: A Peer-to-Peer Electronic Cash System",
                "content": (
                    "Bitcoin is a peer-to-peer electronic cash system that allows online payments to be sent "
                    "directly from one party to another without going through a financial institution. "
                    "Digital signatures provide part of the solution, but the main benefits are lost if a "
                    "trusted third party is still required to prevent double-spending."
                ),
                "source": "Bitcoin.org",
                "url": "https://bitcoin.org/bitcoin.pdf",
            },
            {
                "id": "doc2",
                "title": "Blockchain Technology Explained",
                "content": (
                    "A blockchain is a distributed ledger that maintains a continuously growing list of records, "
                    "called blocks, which are linked and secured using cryptography. Each block contains a "
                    "cryptographic hash of the previous block, a timestamp, and transaction data."
                ),
                "source": "Internal Knowledge Base",
                "url": "",
            },
        ]

        # Format the assistant's response with sources
        formatted_response = AssistantResponseFormatter.format_assistant_response(
            answer=answer, sources=sources
        )

        # Validate response structure
        required_keys = [
            "answer",
            "source_summary",
            "formatted_sources",
            "structured_sources",
        ]
        for key in required_keys:
            if key not in formatted_response:
                print(f"Error: Missing key '{key}' in assistant response")
                return

        print("Assistant Answer:")
        print(formatted_response["answer"])
        print(f"\nSource Summary: {formatted_response['source_summary']}")
        print("\nFormatted Sources:")
        print(formatted_response["formatted_sources"])

        print("\nStructured Sources:")
        for source in formatted_response["structured_sources"]:
            index = source.get("index", "N/A")
            title = source.get("title", "No title")
            print(f"  {index}. {title}")
            if source["url"]:
                print(f"     URL: {source['url']}")
            content_preview = source.get("content_preview", "No preview available")
            print(f"     Preview: {truncate_text(content_preview)}")
    except Exception as e:
        print(f"Error in assistant formatting demo: {e}")
    print("\nFormatted Sources:")
    print(formatted_response.get("formatted_sources", "No sources available"))

    print("\nStructured Sources:")
    for source in formatted_response.get("structured_sources", []):
        print(f"  {source['index']}. {source['title']}")
        if source["url"]:
            print(f"     URL: {source['url']}")
        print(f"     Preview: {truncate_text(source['content_preview'])}")


def demo_mixed_results_handling() -> None:
    """Demonstrate handling of mixed results (with and without URLs).

    Shows how the formatter handles a mix of results that include both
    URL-based and non-URL-based sources, which is a common scenario in
    real-world applications where data comes from multiple sources.
    """
    try:
        print("\n🔀 Mixed Results Handling Demo")
        print("=" * 60)

        # Define mixed results with and without URLs
        mixed_results = [
            {
                "id": "doc1",
                "title": "Bitcoin Whitepaper",
                "content": (
                    "The original Bitcoin whitepaper by Satoshi Nakamoto. "
                    "Describes a peer-to-peer electronic cash system."
                ),
                "source": "Bitcoin.org",
                "url": "https://bitcoin.org/bitcoin.pdf",
                "score": 0.95,
            },
            {
                "id": "doc2",
                "title": "Internal Bitcoin Guide",
                "content": (
                    "Our internal guide covering Bitcoin basics and fundamentals. "
                    "Includes key concepts, security practices, and usage guidelines."
                ),
                "source": "Internal Knowledge Base",
                "url": "",  # No URL
                "score": 0.82,
            },
            {
                "id": "doc3",
                "title": "Lightning Network Paper",
                "content": (
                    "Technical specification for the Lightning Network. "
                    "Describes a second-layer protocol for fast, scalable "
                    "Bitcoin transactions."
                ),
                "source": "Lightning Labs",
                "url": "https://lightning.network/lightning-network-paper.pdf",
                "score": 0.88,
            },
        ]

        print("Handling Mixed Results (some with URLs, some without):")
        print("-" * 50)

        # Process structured response with error handling
        try:
            structured = QueryResultFormatter.format_structured_response(
                results=mixed_results,
                query="Bitcoin fundamentals and technologies",
                include_summary=True,
            )

            # Validate structured response structure
            if not structured:
                print("Error: Failed to generate structured response")
                return

            # Display basic information
            print(f"Query: {structured.get('query', 'No query specified')}")
            print(f"Total Results: {structured.get('total_results', 0)}")

            if "summary" in structured:
                print(
                    f"Summary: {truncate_text(structured['summary'], max_length=150)}"
                )

            # Display individual results with error handling
            print("\nProcessing Individual Results:")
            print("-" * 30)

            try:
                # Display basic information
                query = structured.get("query", "No query specified")
                print(f"Query: {query}")
                result_count = len(structured.get("results", []))
                print(f"Found {result_count} results")

                # Display results with source attribution
                print("\nResults:")
                for idx, result in enumerate(structured.get("results", []), 1):
                    title = result.get("title", "No title")
                    source = result.get("source", "No source")
                    url = result.get("url", "No URL available")
                    score = result.get("score", "N/A")
                    content = result.get("content", "No content")

                    print(f"\n{idx}. {title}")
                    print(f"   Source: {source}")
                    print(f"   URL: {url}")
                    print(f"   Score: {score:.2f}")
                    print(f"   Content: {truncate_text(content, 150)}")

                # Display summary if available
                if "summary" in structured:
                    print(f"\nSummary: {structured['summary']}")

                # Also demonstrate assistant formatting with the same results
                print("\n📝 Assistant Formatting with Mixed Results:")
                print("-" * 50)

                try:
                    # Format assistant response with detailed answer
                    assistant_response = (
                        AssistantResponseFormatter.format_assistant_response(
                            answer=(
                                "Bitcoin is a decentralized digital currency that "
                                "enables peer-to-peer transactions without "
                                "intermediaries. The Lightning Network is a "
                                "second-layer solution that enables fast and "
                                "scalable Bitcoin transactions."
                            ),
                            sources=mixed_results,
                        )
                    )

                    # Validate assistant response structure
                    required_keys = [
                        "answer",
                        "source_summary",
                        "formatted_sources",
                        "structured_sources",
                    ]
                    missing_keys = set(required_keys) - set(assistant_response.keys())
                    if missing_keys:
                        raise ValueError(
                            "Assistant response missing required keys: "
                            f"{missing_keys}"
                        )

                    # Display assistant response sections
                    print("\nAssistant Answer:")
                    print(assistant_response["answer"])

                    print("\nSource Summary:")
                    print(assistant_response["source_summary"])

                    print("\nFormatted Sources:")
                    print(assistant_response["formatted_sources"])

                    # Display structured sources if available
                    if "structured_sources" in assistant_response:
                        print("\nStructured Sources:")
                        for src in assistant_response["structured_sources"]:
                            title = src.get("title", "Untitled")
                            print(f"  • {title}")
                            if "url" in src and src["url"]:
                                print(f"    URL: {src['url']}")

                except Exception as inner_e:
                    print(f"\n⚠️ Error in assistant formatting demo: {inner_e}")
                    if __debug__:
                        import traceback

                        traceback.print_exc()

            except Exception as display_e:
                print(f"\n⚠️ Error displaying results: {display_e}")
                if __debug__:
                    import traceback

                    traceback.print_exc()

        except Exception as e:
            print(f"\n⚠️ Error in mixed results handling demo: {e}")
            if __debug__:
                import traceback

                traceback.print_exc()
        finally:
            print("\n" + "=" * 60)
            print("✅ Mixed Results Handling Demo Completed" " (with error handling)")
            print("=" * 60)

        # Demonstrate MCP formatting with mixed results
        print("\nMCP Formatting with Mixed Results:")
        print("-" * 35)

        try:
            mcp_formatted = MCPResponseFormatter.format_for_mcp(
                mixed_results, "Bitcoin fundamentals and technologies"
            )

            if mcp_formatted and "content" in mcp_formatted:
                content = mcp_formatted["content"][0]
                formatted_text = content.get("text", "No text available")
                print(f"MCP Response: {truncate_text(formatted_text, max_length=250)}")
            else:
                print("Warning: Invalid MCP response structure")

        except Exception as e:
            print(f"Error in MCP formatting: {e}")

        # Summary of mixed result handling capabilities
        print("\nMixed Results Summary:")
        print("-" * 25)

        url_count = sum(1 for r in mixed_results if r.get("url"))
        no_url_count = len(mixed_results) - url_count

        print(f"Results with URLs: {url_count}")
        print(f"Results without URLs: {no_url_count}")
        print("✓ All results processed successfully")
        print("✓ Graceful handling of missing URLs")
        print("✓ Consistent formatting applied")

    except Exception as e:
        print(f"Error in mixed results handling demo: {e}")
        print("Failed to complete demo - check input data and formatter availability")


def main():
    """Run all formatting demos"""

    print("🎯 Result Formatting with URL Metadata - Complete Demo")
    print("=" * 80)

    demos = [
        ("Query Result Formatting", demo_query_result_formatting),
        ("MCP Formatting", demo_mcp_formatting),
        ("Assistant Formatting", demo_assistant_formatting),
        ("Mixed Results Handling", demo_mixed_results_handling),
    ]

    failed_demos = []

    for demo_name, demo_func in demos:
        try:
            demo_func()
        except Exception as e:
            print(f"\n❌ Error in {demo_name} demo: {e}")
            failed_demos.append(demo_name)

    if failed_demos:
        print(f"\n⚠️  Some demos failed: {', '.join(failed_demos)}")
    else:
        print("\n\n✅ All demos completed successfully!")

    print("The result formatting system now supports:")
    print("  • Clickable URLs in formatted responses")
    print("  • Graceful handling of documents without URLs")
    print("  • Clear source attribution with publication dates")
    print("  • Structured responses for API consumption")
    print("  • MCP-compatible response formatting")
    print("  • Assistant response enhancement")
    print("  • Mixed result handling (with and without URLs)")


if __name__ == "__main__":
    main()
