#!/usr/bin/env python3
"""
Test the result formatting functionality with URL metadata support
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.result_formatter import (
    QueryResultFormatter, 
    MCPResponseFormatter, 
    AssistantResponseFormatter
)

class TestQueryResultFormatter(unittest.TestCase):
    """Test the QueryResultFormatter class"""
    
    def setUp(self):
        """Set up test data"""
        self.sample_results_with_urls = [
            {
                'id': 'doc1',
                'title': 'Bitcoin Whitepaper',
                'content': 'Bitcoin is a peer-to-peer electronic cash system...',
                'source': 'Bitcoin.org',
                'url': 'https://bitcoin.org/bitcoin.pdf',
                'category': 'whitepaper',
                'score': 0.95,
                'published': '2008-10-31'
            },
            {
                'id': 'doc2',
                'title': 'Lightning Network Paper',
                'content': 'The Lightning Network is a decentralized system...',
                'source': 'Lightning Labs',
                'url': 'https://lightning.network/lightning-network-paper.pdf',
                'category': 'technical',
                'score': 0.87,
                'published': '2016-01-14'
            }
        ]
        
        self.sample_results_mixed = [
            {
                'id': 'doc1',
                'title': 'Bitcoin Whitepaper',
                'content': 'Bitcoin is a peer-to-peer electronic cash system...',
                'source': 'Bitcoin.org',
                'url': 'https://bitcoin.org/bitcoin.pdf',
                'category': 'whitepaper',
                'score': 0.95
            },
            {
                'id': 'doc2',
                'title': 'Internal Bitcoin Guide',
                'content': 'This is an internal guide about Bitcoin basics...',
                'source': 'Internal Knowledge Base',
                'url': '',  # No URL
                'category': 'guide',
                'score': 0.82
            }
        ]
    
    def test_format_single_result_with_url(self):
        """Test formatting a single result with URL"""
        result = self.sample_results_with_urls[0]
        formatted = QueryResultFormatter.format_single_result(result)
        
        self.assertIn('**Bitcoin Whitepaper**', formatted)
        self.assertIn('Bitcoin is a peer-to-peer electronic cash system', formatted)
        self.assertIn('[Bitcoin.org](https://bitcoin.org/bitcoin.pdf)', formatted)
        self.assertIn('Published: 2008-10-31', formatted)
    
    def test_format_single_result_without_url(self):
        """Test formatting a single result without URL"""
        result = self.sample_results_mixed[1]
        formatted = QueryResultFormatter.format_single_result(result)
        
        self.assertIn('**Internal Bitcoin Guide**', formatted)
        self.assertIn('This is an internal guide about Bitcoin basics', formatted)
        self.assertIn('*Source: Internal Knowledge Base*', formatted)
        self.assertNotIn('](', formatted)  # No markdown links
    
    def test_format_single_result_with_score(self):
        """Test formatting a single result with relevance score"""
        result = self.sample_results_with_urls[0]
        formatted = QueryResultFormatter.format_single_result(result, include_score=True)
        
        self.assertIn('*Relevance: 0.950*', formatted)
    
    def test_format_multiple_results(self):
        """Test formatting multiple results"""
        formatted = QueryResultFormatter.format_multiple_results(self.sample_results_with_urls)
        
        self.assertIn('## Result 1', formatted)
        self.assertIn('## Result 2', formatted)
        self.assertIn('---', formatted)  # Separator between results
        self.assertIn('[Bitcoin.org](https://bitcoin.org/bitcoin.pdf)', formatted)
        self.assertIn('[Lightning Labs](https://lightning.network/lightning-network-paper.pdf)', formatted)
    
    def test_format_multiple_results_with_limit(self):
        """Test formatting multiple results with limit"""
        formatted = QueryResultFormatter.format_multiple_results(
            self.sample_results_with_urls, 
            max_results=1
        )
        
        self.assertIn('## Result 1', formatted)
        self.assertNotIn('## Result 2', formatted)
    
    def test_format_structured_response(self):
        """Test creating structured response format"""
        response = QueryResultFormatter.format_structured_response(
            self.sample_results_mixed,
            query="What is Bitcoin?",
            include_summary=True
        )
        
        self.assertEqual(response['query'], "What is Bitcoin?")
        self.assertEqual(response['total_results'], 2)
        self.assertEqual(response['results_with_sources'], 1)
        self.assertEqual(response['results_without_sources'], 1)
        self.assertIn('formatted_response', response)
        self.assertIn('sources', response)
        self.assertIn('summary', response)
    
    def test_extract_unique_sources(self):
        """Test extracting unique sources"""
        sources = QueryResultFormatter._extract_unique_sources(self.sample_results_mixed)
        
        self.assertEqual(len(sources), 2)
        
        # Check Bitcoin.org source
        bitcoin_source = next(s for s in sources if s['name'] == 'Bitcoin.org')
        self.assertEqual(bitcoin_source['url'], 'https://bitcoin.org/bitcoin.pdf')
        self.assertEqual(bitcoin_source['count'], 1)
        
        # Check Internal source
        internal_source = next(s for s in sources if s['name'] == 'Internal Knowledge Base')
        self.assertEqual(internal_source['url'], '')
        self.assertEqual(internal_source['count'], 1)
    
    def test_validate_url(self):
        """Test URL validation"""
        # Valid URLs
        self.assertEqual(
            QueryResultFormatter._validate_url('https://bitcoin.org/bitcoin.pdf'),
            'https://bitcoin.org/bitcoin.pdf'
        )
        self.assertEqual(
            QueryResultFormatter._validate_url('bitcoin.org/bitcoin.pdf'),
            'https://bitcoin.org/bitcoin.pdf'
        )
        
        # Invalid URLs
        self.assertIsNone(QueryResultFormatter._validate_url(''))
        self.assertIsNone(QueryResultFormatter._validate_url('not-a-url'))
        self.assertIsNone(QueryResultFormatter._validate_url(None))
    
    def test_generate_result_summary(self):
        """Test result summary generation"""
        summary = QueryResultFormatter._generate_result_summary(self.sample_results_mixed)
        
        self.assertIn('Found 2 relevant results', summary)
        self.assertIn('1 result includes source links', summary)
        self.assertIn('1 result from internal sources', summary)


class TestMCPResponseFormatter(unittest.TestCase):
    """Test the MCPResponseFormatter class"""
    
    def setUp(self):
        """Set up test data"""
        self.sample_results = [
            {
                'id': 'doc1',
                'title': 'Bitcoin Whitepaper',
                'content': 'Bitcoin is a peer-to-peer electronic cash system...',
                'source': 'Bitcoin.org',
                'url': 'https://bitcoin.org/bitcoin.pdf',
                'score': 0.95
            }
        ]
    
    def test_format_for_mcp_with_results(self):
        """Test formatting results for MCP response"""
        response = MCPResponseFormatter.format_for_mcp(self.sample_results, "What is Bitcoin?")
        
        self.assertIn('content', response)
        self.assertEqual(len(response['content']), 1)
        self.assertEqual(response['content'][0]['type'], 'text')
        
        text = response['content'][0]['text']
        self.assertIn('**Query:** What is Bitcoin?', text)
        self.assertIn('**Bitcoin Whitepaper**', text)
        self.assertIn('[Bitcoin.org](https://bitcoin.org/bitcoin.pdf)', text)
        self.assertIn('## Sources Referenced', text)
    
    def test_format_for_mcp_empty_results(self):
        """Test formatting empty results for MCP response"""
        response = MCPResponseFormatter.format_for_mcp([], "What is Bitcoin?")
        
        self.assertIn('content', response)
        self.assertEqual(len(response['content']), 1)
        self.assertIn('No relevant information found', response['content'][0]['text'])


class TestAssistantResponseFormatter(unittest.TestCase):
    """Test the AssistantResponseFormatter class"""
    
    def setUp(self):
        """Set up test data"""
        self.sample_sources = [
            {
                'id': 'doc1',
                'title': 'Bitcoin Whitepaper',
                'content': 'Bitcoin is a peer-to-peer electronic cash system that allows online payments...',
                'source': 'Bitcoin.org',
                'url': 'https://bitcoin.org/bitcoin.pdf'
            },
            {
                'id': 'doc2',
                'title': 'Internal Guide',
                'content': 'This is an internal guide about Bitcoin basics and fundamentals...',
                'source': 'Internal KB',
                'url': ''  # No URL
            }
        ]
    
    def test_format_assistant_response_with_sources(self):
        """Test formatting assistant response with sources"""
        answer = "Bitcoin is a decentralized digital currency..."
        response = AssistantResponseFormatter.format_assistant_response(answer, self.sample_sources)
        
        self.assertEqual(response['answer'], answer)
        self.assertEqual(len(response['sources']), 2)
        self.assertIn('formatted_sources', response)
        self.assertIn('source_summary', response)
        self.assertIn('structured_sources', response)
        
        # Check formatted sources
        formatted = response['formatted_sources']
        self.assertIn('## Sources', formatted)
        self.assertIn('1. **Bitcoin Whitepaper**', formatted)
        self.assertIn('[Bitcoin.org](https://bitcoin.org/bitcoin.pdf)', formatted)
        self.assertIn('2. **Internal Guide**', formatted)
        self.assertIn('*Source: Internal KB*', formatted)
    
    def test_format_assistant_response_no_sources(self):
        """Test formatting assistant response without sources"""
        answer = "I don't have information about that topic."
        response = AssistantResponseFormatter.format_assistant_response(answer, [])
        
        self.assertEqual(response['answer'], answer)
        self.assertEqual(len(response['sources']), 0)
        self.assertEqual(response['formatted_sources'], "No sources available.")


class TestResultFormattingIntegration(unittest.TestCase):
    """Integration tests for result formatting with actual components"""
    
    def test_format_query_results_for_mcp_fallback(self):
        """Test the fallback MCP formatting function"""
        from clean_mcp_response import format_query_results_for_mcp
        
        results = [
            {
                'title': 'Bitcoin Whitepaper',
                'content': 'Bitcoin is a peer-to-peer electronic cash system...',
                'source': 'Bitcoin.org',
                'url': 'https://bitcoin.org/bitcoin.pdf'
            }
        ]
        
        response = format_query_results_for_mcp(results, "What is Bitcoin?")
        
        self.assertIn('content', response)
        text = response['content'][0]['text']
        self.assertIn('**Query:** What is Bitcoin?', text)
        self.assertIn('[Bitcoin.org](https://bitcoin.org/bitcoin.pdf)', text)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)