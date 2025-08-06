#!/usr/bin/env python3
"""
Test the result formatting functionality with URL metadata support
"""

import pytest

from btc_max_knowledge_agent.utils.result_formatter import (
    AssistantResponseFormatter,
    MCPResponseFormatter,
    QueryResultFormatter,
)


@pytest.fixture
def sample_results_with_urls():
    """Sample test data with URLs"""
    return [
        {
            "id": "doc1",
            "title": "Bitcoin Whitepaper",
            "content": "Bitcoin is a peer-to-peer electronic cash system...",
            "source": "Bitcoin.org",
            "url": "https://bitcoin.org/bitcoin.pdf",
            "category": "whitepaper",
            "score": 0.95,
            "published": "2008-10-31",
        },
        {
            "id": "doc2",
            "title": "Lightning Network Paper",
            "content": "The Lightning Network is a decentralized system...",
            "source": "Lightning Labs",
            "url": "https://lightning.network/lightning-network-paper.pdf",
            "category": "technical",
            "score": 0.87,
            "published": "2016-01-14",
        },
    ]


@pytest.fixture
def sample_results_mixed():
    """Sample test data with mixed URL availability"""
    return [
        {
            "id": "doc1",
            "title": "Bitcoin Whitepaper",
            "content": "Bitcoin is a peer-to-peer electronic cash system...",
            "source": "Bitcoin.org",
            "url": "https://bitcoin.org/bitcoin.pdf",
            "category": "whitepaper",
            "score": 0.95,
        },
        {
            "id": "doc2",
            "title": "Internal Bitcoin Guide",
            "content": "This is an internal guide about Bitcoin basics...",
            "source": "Internal Knowledge Base",
            "url": "",  # No URL
            "category": "guide",
            "score": 0.82,
        },
    ]


def test_format_single_result_with_url(sample_results_with_urls):
    """Test formatting a single result with URL"""
    result = sample_results_with_urls[0]
    formatted = QueryResultFormatter.format_single_result(result)

    assert "**Bitcoin Whitepaper**" in formatted
    assert "Bitcoin is a peer-to-peer electronic cash system" in formatted
    assert "[Bitcoin.org](https://bitcoin.org/bitcoin.pdf)" in formatted
    assert "Published: 2008-10-31" in formatted


def test_format_single_result_without_url(sample_results_mixed):
    """Test formatting a single result without URL"""
    result = sample_results_mixed[1]
    formatted = QueryResultFormatter.format_single_result(result)

    assert "**Internal Bitcoin Guide**" in formatted
    assert "This is an internal guide about Bitcoin basics" in formatted
    assert "*Source: Internal Knowledge Base*" in formatted
    assert "](" not in formatted  # No markdown links


def test_format_single_result_with_score(sample_results_with_urls):
    """Test formatting a single result with relevance score"""
    result = sample_results_with_urls[0]
    formatted = QueryResultFormatter.format_single_result(result, include_score=True)

    assert "*Relevance: 0.950*" in formatted


def test_format_multiple_results(sample_results_with_urls):
    """Test formatting multiple results"""
    formatted = QueryResultFormatter.format_multiple_results(sample_results_with_urls)

    assert "## Result 1" in formatted
    assert "## Result 2" in formatted
    assert "---" in formatted  # Separator between results
    assert "[Bitcoin.org](https://bitcoin.org/bitcoin.pdf)" in formatted
    assert (
        "[Lightning Labs](https://lightning.network/lightning-network-paper.pdf)"
        in formatted
    )


def test_format_multiple_results_with_limit(sample_results_with_urls):
    """Test formatting multiple results with limit"""
    formatted = QueryResultFormatter.format_multiple_results(
        sample_results_with_urls, max_results=1
    )

    assert "## Result 1" in formatted
    assert "## Result 2" not in formatted


def test_format_structured_response(sample_results_mixed):
    """Test creating structured response format"""
    response = QueryResultFormatter.format_structured_response(
        sample_results_mixed, query="What is Bitcoin?", include_summary=True
    )

    assert response["query"] == "What is Bitcoin?"
    assert response["total_results"] == 2
    assert response["results_with_sources"] == 1
    assert response["results_without_sources"] == 1
    assert "formatted_response" in response
    assert "sources" in response
    assert "summary" in response


def test_extract_unique_sources(sample_results_mixed):
    """Test extracting unique sources"""
    sources = QueryResultFormatter._extract_unique_sources(sample_results_mixed)

    assert len(sources) == 2

    # Check Bitcoin.org source
    bitcoin_source = next(s for s in sources if s["name"] == "Bitcoin.org")
    assert bitcoin_source["url"] == "https://bitcoin.org/bitcoin.pdf"
    assert bitcoin_source["count"] == 1

    # Check Internal source
    internal_source = next(s for s in sources if s["name"] == "Internal Knowledge Base")
    assert internal_source["url"] == ""
    assert internal_source["count"] == 1


def test_validate_url():
    """Test URL validation"""
    # Valid URLs
    assert (
        QueryResultFormatter._validate_url("https://bitcoin.org/bitcoin.pdf")
        == "https://bitcoin.org/bitcoin.pdf"
    )
    assert (
        QueryResultFormatter._validate_url("bitcoin.org/bitcoin.pdf")
        == "https://bitcoin.org/bitcoin.pdf"
    )

    # Invalid URLs
    assert QueryResultFormatter._validate_url("") is None
    assert QueryResultFormatter._validate_url("not-a-url") is None
    assert QueryResultFormatter._validate_url(None) is None


def test_generate_result_summary(sample_results_mixed):
    """Test result summary generation"""
    summary = QueryResultFormatter._generate_result_summary(sample_results_mixed)

    assert "Found 2 relevant results" in summary
    assert "1 result includes source links" in summary
    assert "1 result from internal sources" in summary


@pytest.fixture
def sample_mcp_results():
    """Sample test data for MCP response formatter"""
    return [
        {
            "id": "doc1",
            "title": "Bitcoin Whitepaper",
            "content": "Bitcoin is a peer-to-peer electronic cash system...",
            "source": "Bitcoin.org",
            "url": "https://bitcoin.org/bitcoin.pdf",
            "score": 0.95,
        }
    ]


@pytest.fixture
def sample_assistant_sources():
    """Sample test data for assistant response formatter"""
    return [
        {
            "id": "doc1",
            "title": "Bitcoin Whitepaper",
            "content": (
                "Bitcoin is a peer-to-peer electronic cash system that allows online payments..."
            ),
            "source": "Bitcoin.org",
            "url": "https://bitcoin.org/bitcoin.pdf",
        },
        {
            "id": "doc2",
            "title": "Internal Guide",
            "content": (
                "This is an internal guide about Bitcoin basics and fundamentals..."
            ),
            "source": "Internal KB",
            "url": "",  # No URL
        },
    ]


def test_format_for_mcp_with_results(sample_mcp_results):
    """Test formatting results for MCP response"""
    response = MCPResponseFormatter.format_for_mcp(
        sample_mcp_results, "What is Bitcoin?"
    )

    assert "content" in response
    assert len(response["content"]) == 1
    assert response["content"][0]["type"] == "text"

    text = response["content"][0]["text"]
    assert "**Query:** What is Bitcoin?" in text
    assert "**Bitcoin Whitepaper**" in text
    assert "[Bitcoin.org](https://bitcoin.org/bitcoin.pdf)" in text
    assert "## Sources Referenced" in text


def test_format_for_mcp_empty_results():
    """Test formatting empty results for MCP response"""
    response = MCPResponseFormatter.format_for_mcp([], "What is Bitcoin?")

    assert "content" in response
    assert len(response["content"]) == 1
    assert "No relevant information found" in response["content"][0]["text"]


def test_format_assistant_response_with_sources(sample_assistant_sources):
    """Test formatting assistant response with sources"""
    answer = "Bitcoin is a decentralized digital currency..."
    response = AssistantResponseFormatter.format_assistant_response(
        answer, sample_assistant_sources
    )

    assert response["answer"] == answer
    assert len(response["sources"]) == 2
    assert "formatted_sources" in response
    assert "source_summary" in response
    assert "structured_sources" in response

    # Check formatted sources
    formatted = response["formatted_sources"]
    assert "## Sources" in formatted
    assert "1. **Bitcoin Whitepaper**" in formatted
    assert "[Bitcoin.org](https://bitcoin.org/bitcoin.pdf)" in formatted
    assert "2. **Internal Guide**" in formatted
    assert "*Source: Internal KB*" in formatted


def test_format_assistant_response_no_sources():
    """Test formatting assistant response without sources"""
    answer = "I don't have information about that topic."
    response = AssistantResponseFormatter.format_assistant_response(answer, [])

    assert response["answer"] == answer
    assert len(response["sources"]) == 0
    assert response["formatted_sources"] == "No sources available."


def test_format_query_results_for_mcp_fallback():
    """Test the fallback MCP formatting function"""
    try:
        from clean_mcp_response import format_query_results_for_mcp

        results = [
            {
                "title": "Bitcoin Whitepaper",
                "content": "Bitcoin is a peer-to-peer electronic cash system...",
                "source": "Bitcoin.org",
                "url": "https://bitcoin.org/bitcoin.pdf",
            }
        ]

        response = format_query_results_for_mcp(results, "What is Bitcoin?")

        assert "content" in response
        text = response["content"][0]["text"]
        assert "**Query:** What is Bitcoin?" in text
        assert "[Bitcoin.org](https://bitcoin.org/bitcoin.pdf)" in text
    except ImportError:
        pytest.skip("clean_mcp_response module not available")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
