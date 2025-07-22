#!/usr/bin/env python3
"""
Demonstration of the new result formatting functionality with URL metadata support
"""

import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.result_formatter import (
    QueryResultFormatter, 
    MCPResponseFormatter, 
    AssistantResponseFormatter
)

def demo_query_result_formatting():
    """Demonstrate query result formatting with URL metadata"""
    
    print("🔍 Query Result Formatting Demo")
    print("=" * 60)
    
    # Sample results with mixed URL availability
    sample_results = [
        {
            'id': 'doc1',
            'title': 'Bitcoin: A Peer-to-Peer Electronic Cash System',
            'content': 'Bitcoin is a peer-to-peer electronic cash system that allows online payments to be sent directly from one party to another without going through a financial institution. Digital signatures provide part of the solution, but the main benefits are lost if a trusted third party is still required to prevent double-spending.',
            'source': 'Bitcoin.org',
            'url': 'https://bitcoin.org/bitcoin.pdf',
            'category': 'whitepaper',
            'score': 0.95,
            'published': '2008-10-31'
        },
        {
            'id': 'doc2',
            'title': 'Lightning Network Overview',
            'content': 'The Lightning Network is a decentralized system for instant, high-volume micropayments that removes the risk of delegating custody of funds to trusted third parties. It enables scalable micropayments through a network of bidirectional payment channels.',
            'source': 'Lightning Labs',
            'url': 'https://lightning.network/lightning-network-paper.pdf',
            'category': 'technical',
            'score': 0.87,
            'published': '2016-01-14'
        },
        {
            'id': 'doc3',
            'title': 'Bitcoin Mining Fundamentals',
            'content': 'Bitcoin mining is the process of adding transaction records to Bitcoin\'s public ledger of past transactions. This ledger of past transactions is called the blockchain as it is a chain of blocks.',
            'source': 'Internal Knowledge Base',
            'url': '',  # No URL available
            'category': 'guide',
            'score': 0.82,
            'published': ''
        }
    ]
    
    print("\n1. Single Result Formatting (with URL):")
    print("-" * 40)
    single_formatted = QueryResultFormatter.format_single_result(sample_results[0], include_score=True)
    print(single_formatted)
    
    print("\n2. Single Result Formatting (without URL):")
    print("-" * 40)
    single_no_url = QueryResultFormatter.format_single_result(sample_results[2])
    print(single_no_url)
    
    print("\n3. Multiple Results Formatting:")
    print("-" * 40)
    multiple_formatted = QueryResultFormatter.format_multiple_results(sample_results, include_scores=True)
    print(multiple_formatted)
    
    print("\n4. Structured Response Format:")
    print("-" * 40)
    structured = QueryResultFormatter.format_structured_response(
        sample_results, 
        query="What is Bitcoin and how does it work?",
        include_summary=True
    )
    print(f"Query: {structured['query']}")
    print(f"Total Results: {structured['total_results']}")
    print(f"Results with Sources: {structured['results_with_sources']}")
    print(f"Results without Sources: {structured['results_without_sources']}")
    print(f"Summary: {structured['summary']}")
    print("\nUnique Sources:")
    for source in structured['sources']:
        if source['url']:
            print(f"  - {source['name']}: {source['url']} ({source['count']} results)")
        else:
            print(f"  - {source['name']}: No URL ({source['count']} results)")

def demo_mcp_formatting():
    """Demonstrate MCP response formatting"""
    
    print("\n\n📡 MCP Response Formatting Demo")
    print("=" * 60)
    
    sample_results = [
        {
            'id': 'doc1',
            'title': 'Bitcoin Whitepaper',
            'content': 'Bitcoin is a peer-to-peer electronic cash system that allows online payments to be sent directly from one party to another without going through a financial institution.',
            'source': 'Bitcoin.org',
            'url': 'https://bitcoin.org/bitcoin.pdf',
            'score': 0.95
        },
        {
            'id': 'doc2',
            'title': 'Bitcoin Mining Guide',
            'content': 'Bitcoin mining is the process by which new bitcoins are entered into circulation and is also a critical component of the maintenance and development of the blockchain ledger.',
            'source': 'Internal Guide',
            'url': '',
            'score': 0.78
        }
    ]
    
    mcp_response = MCPResponseFormatter.format_for_mcp(sample_results, "What is Bitcoin?")
    
    print("MCP Response Structure:")
    print(f"Content Type: {mcp_response['content'][0]['type']}")
    print(f"Metadata: {mcp_response.get('metadata', {})}")
    print("\nFormatted Text:")
    print(mcp_response['content'][0]['text'])

def demo_assistant_formatting():
    """Demonstrate Pinecone Assistant response formatting"""
    
    print("\n\n🤖 Assistant Response Formatting Demo")
    print("=" * 60)
    
    answer = "Bitcoin is a decentralized digital currency that operates without a central bank or single administrator. It uses blockchain technology to maintain a public ledger of all transactions."
    
    sources = [
        {
            'id': 'doc1',
            'title': 'Bitcoin: A Peer-to-Peer Electronic Cash System',
            'content': 'Bitcoin is a peer-to-peer electronic cash system that allows online payments to be sent directly from one party to another without going through a financial institution. Digital signatures provide part of the solution, but the main benefits are lost if a trusted third party is still required to prevent double-spending.',
            'source': 'Bitcoin.org',
            'url': 'https://bitcoin.org/bitcoin.pdf'
        },
        {
            'id': 'doc2',
            'title': 'Blockchain Technology Explained',
            'content': 'A blockchain is a distributed ledger that maintains a continuously growing list of records, called blocks, which are linked and secured using cryptography. Each block contains a cryptographic hash of the previous block, a timestamp, and transaction data.',
            'source': 'Internal Knowledge Base',
            'url': ''
        }
    ]
    
    formatted_response = AssistantResponseFormatter.format_assistant_response(answer, sources)
    
    print("Assistant Answer:")
    print(formatted_response['answer'])
    print(f"\nSource Summary: {formatted_response['source_summary']}")
    print("\nFormatted Sources:")
    print(formatted_response['formatted_sources'])
    
    print("\nStructured Sources:")
    for source in formatted_response['structured_sources']:
        print(f"  {source['index']}. {source['title']}")
        if source['url']:
            print(f"     URL: {source['url']}")
        print(f"     Preview: {source['content_preview'][:100]}...")

def demo_mixed_results_handling():
    """Demonstrate handling of mixed results (with and without URLs)"""
    
    print("\n\n🔀 Mixed Results Handling Demo")
    print("=" * 60)
    
    mixed_results = [
        {
            'id': 'doc1',
            'title': 'Bitcoin Whitepaper',
            'content': 'The original Bitcoin whitepaper by Satoshi Nakamoto.',
            'source': 'Bitcoin.org',
            'url': 'https://bitcoin.org/bitcoin.pdf',
            'score': 0.95
        },
        {
            'id': 'doc2',
            'title': 'Internal Bitcoin Guide',
            'content': 'Our internal guide covering Bitcoin basics and fundamentals.',
            'source': 'Internal Knowledge Base',
            'url': '',  # No URL
            'score': 0.82
        },
        {
            'id': 'doc3',
            'title': 'Lightning Network Paper',
            'content': 'Technical specification for the Lightning Network.',
            'source': 'Lightning Labs',
            'url': 'https://lightning.network/lightning-network-paper.pdf',
            'score': 0.88
        }
    ]
    
    print("Handling Mixed Results (some with URLs, some without):")
    print("-" * 50)
    
    structured = QueryResultFormatter.format_structured_response(mixed_results)
    print(f"Summary: {structured['summary']}")
    
    print("\nSource Breakdown:")
    for source in structured['sources']:
        status = "✅ Has URL" if source['url'] else "❌ No URL"
        print(f"  - {source['name']}: {status} ({source['count']} results)")
    
    print("\nFormatted Response:")
    print(structured['formatted_response'][:500] + "..." if len(structured['formatted_response']) > 500 else structured['formatted_response'])

def main():
    """Run all formatting demos"""
    
    print("🎯 Result Formatting with URL Metadata - Complete Demo")
    print("=" * 80)
    
    demo_query_result_formatting()
    demo_mcp_formatting()
    demo_assistant_formatting()
    demo_mixed_results_handling()
    
    print("\n\n✅ Demo Complete!")
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