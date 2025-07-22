#!/usr/bin/env python3
"""
Test script to verify URL metadata handling in PineconeClient
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.retrieval.pinecone_client import PineconeClient

class TestPineconeURLMetadata(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the config and external dependencies
        with patch('src.retrieval.pinecone_client.Config') as mock_config:
            mock_config.validate.return_value = None
            mock_config.PINECONE_API_KEY = 'test-key'
            mock_config.PINECONE_INDEX_NAME = 'test-index'
            mock_config.EMBEDDING_DIMENSION = 768
            
            with patch('src.retrieval.pinecone_client.Pinecone'):
                self.client = PineconeClient()
    
    def test_validate_and_sanitize_url_valid_urls(self):
        """Test URL validation with valid URLs"""
        # Test valid URLs
        valid_urls = [
            'https://example.com',
            'http://example.com',
            'https://subdomain.example.com',
            'https://example.com/path',
            'https://example.com/path?query=value'
        ]
        
        for url in valid_urls:
            result = self.client.validate_and_sanitize_url(url)
            self.assertEqual(result, url, f"Valid URL {url} should be returned as-is")
    
    def test_validate_and_sanitize_url_missing_protocol(self):
        """Test URL validation with missing protocol"""
        # Test URLs without protocol
        test_cases = [
            ('example.com', 'https://example.com'),
            ('subdomain.example.com', 'https://subdomain.example.com'),
            ('example.com/path', 'https://example.com/path')
        ]
        
        for input_url, expected in test_cases:
            result = self.client.validate_and_sanitize_url(input_url)
            self.assertEqual(result, expected, f"URL {input_url} should be sanitized to {expected}")
    
    def test_validate_and_sanitize_url_invalid_urls(self):
        """Test URL validation with invalid URLs"""
        invalid_urls = [
            None,
            '',
            '   ',
            'not-a-url',
            'http://',
            'https://',
            'ftp://example.com',  # Wrong protocol
            'invalid-domain',
            'http://localhost',  # No TLD
            123,  # Not a string
            []   # Not a string
        ]
        
        for url in invalid_urls:
            result = self.client.validate_and_sanitize_url(url)
            self.assertIsNone(result, f"Invalid URL {url} should return None")
    
    def test_upsert_documents_with_url_metadata(self):
        """Test document upsert with URL metadata"""
        # Mock the index
        mock_index = Mock()
        self.client.get_index = Mock(return_value=mock_index)
        
        # Test documents with URLs and embeddings
        documents = [
            {
                'id': 'doc1',
                'title': 'Test Document 1',
                'content': 'This is test content 1',
                'source': 'Test Source 1',
                'category': 'test',
                'url': 'https://example.com/doc1',
                'embedding': [0.1] * 768
            },
            {
                'id': 'doc2',
                'title': 'Test Document 2',
                'content': 'This is test content 2',
                'source': 'Test Source 2',
                'category': 'test',
                'url': 'example.com/doc2',  # Missing protocol
                'embedding': [0.2] * 768
            },
            {
                'id': 'doc3',
                'title': 'Test Document 3',
                'content': 'This is test content 3',
                'source': 'Test Source 3',
                'category': 'test',
                'embedding': [0.3] * 768
                # No URL field
            }
        ]
        
        # Call upsert_documents
        self.client.upsert_documents(documents)
        
        # Verify upsert was called
        mock_index.upsert.assert_called_once()
        
        # Get the vectors that were upserted
        call_args = mock_index.upsert.call_args[1]['vectors']
        
        # Verify first document has correct URL
        self.assertEqual(call_args[0]['metadata']['url'], 'https://example.com/doc1')
        
        # Verify second document has sanitized URL
        self.assertEqual(call_args[1]['metadata']['url'], 'https://example.com/doc2')
        
        # Verify third document has empty URL
        self.assertEqual(call_args[2]['metadata']['url'], '')
        
        # Verify all documents have the URL field in metadata
        for vector in call_args:
            self.assertIn('url', vector['metadata'])
    
    def test_upsert_documents_with_published_date(self):
        """Test document upsert with published date metadata"""
        # Mock the index
        mock_index = Mock()
        self.client.get_index = Mock(return_value=mock_index)
        
        # Test document with published date
        documents = [
            {
                'id': 'doc1',
                'title': 'Test Document',
                'content': 'This is test content',
                'source': 'Test Source',
                'category': 'test',
                'url': 'https://example.com',
                'published': '2024-01-01',
                'embedding': [0.1] * 768
            }
        ]
        
        # Call upsert_documents
        self.client.upsert_documents(documents)
        
        # Get the vectors that were upserted
        call_args = mock_index.upsert.call_args[1]['vectors']
        
        # Verify published date is included
        self.assertEqual(call_args[0]['metadata']['published'], '2024-01-01')
    
    def test_query_similar_returns_url_metadata(self):
        """Test that query_similar returns URL metadata in results"""
        # Mock the index and query results
        mock_index = Mock()
        mock_query_results = {
            'matches': [
                {
                    'id': 'doc1',
                    'score': 0.95,
                    'metadata': {
                        'title': 'Test Document 1',
                        'source': 'Test Source 1',
                        'category': 'test',
                        'content': 'Test content 1',
                        'url': 'https://example.com/doc1',
                        'published': '2024-01-01'
                    }
                },
                {
                    'id': 'doc2',
                    'score': 0.85,
                    'metadata': {
                        'title': 'Test Document 2',
                        'source': 'Test Source 2',
                        'category': 'test',
                        'content': 'Test content 2',
                        'url': '',  # Empty URL
                        'published': ''
                    }
                }
            ]
        }
        
        mock_index.query.return_value = mock_query_results
        self.client.get_index = Mock(return_value=mock_index)
        
        # Call query_similar with embedding vector
        test_embedding = [0.1] * 768
        results = self.client.query_similar(test_embedding)
        
        # Verify results include URL metadata
        self.assertEqual(len(results), 2)
        
        # Check first result
        self.assertEqual(results[0]['url'], 'https://example.com/doc1')
        self.assertEqual(results[0]['published'], '2024-01-01')
        
        # Check second result (empty URL)
        self.assertEqual(results[1]['url'], '')
        self.assertEqual(results[1]['published'], '')
        
        # Verify all results have URL and published fields
        for result in results:
            self.assertIn('url', result)
            self.assertIn('published', result)
    
    def test_upsert_documents_handles_invalid_urls_gracefully(self):
        """Test that invalid URLs are handled gracefully during upsert"""
        # Mock the index
        mock_index = Mock()
        self.client.get_index = Mock(return_value=mock_index)
        
        # Test documents with invalid URLs
        documents = [
            {
                'id': 'doc1',
                'title': 'Test Document 1',
                'content': 'This is test content 1',
                'source': 'Test Source 1',
                'category': 'test',
                'url': 'invalid-url',
                'embedding': [0.1] * 768
            },
            {
                'id': 'doc2',
                'title': 'Test Document 2',
                'content': 'This is test content 2',
                'source': 'Test Source 2',
                'category': 'test',
                'url': None,
                'embedding': [0.2] * 768
            }
        ]
        
        # This should not raise an exception
        try:
            self.client.upsert_documents(documents)
        except Exception as e:
            self.fail(f"upsert_documents raised an exception with invalid URLs: {e}")
        
        # Verify upsert was called
        mock_index.upsert.assert_called_once()
        
        # Get the vectors that were upserted
        call_args = mock_index.upsert.call_args[1]['vectors']
        
        # Verify both documents have empty URL (invalid URLs become empty strings)
        self.assertEqual(call_args[0]['metadata']['url'], '')
        self.assertEqual(call_args[1]['metadata']['url'], '')

def main():
    """Run the tests"""
    print("🧪 Testing Pinecone URL Metadata Functionality")
    print("=" * 50)
    
    # Run the unit tests
    unittest.main(verbosity=2, exit=False)

if __name__ == "__main__":
    main()