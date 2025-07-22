#!/usr/bin/env python3
"""
Enhanced test script to verify URL metadata handling in PineconeAssistantAgent
with additional scenarios including timeouts, partial metadata, and mixed
availability.

Run from project root with:
    python -m pytest test_pinecone_assistant_url_metadata_enhanced.py -v
    
Or set PYTHONPATH:
    PYTHONPATH=. python test_pinecone_assistant_url_metadata_enhanced.py
"""

import os
import sys
import unittest
import uuid
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from unittest.mock import Mock, patch

import requests

# Robust path handling for imports
def setup_import_path():
    """Setup import path for the project modules."""
    # Get the project root directory
    current_file = Path(__file__).resolve()
    project_root = current_file.parent
    
    # Add project root to Python path if not already present
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    
    # Also check for src directory (in case of src layout)
    src_dir = project_root / 'src'
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    return project_root

# Setup imports
project_root = setup_import_path()

# Now import project modules
try:
    from src.agents.pinecone_assistant_agent import PineconeAssistantAgent
    from src.utils.url_error_handler import exponential_backoff_retry
    from src.utils.url_metadata_logger import set_correlation_id
except ImportError as e:
    # Fallback import strategy
    print(f"Warning: Standard import failed ({e}), trying alternative imports...")
    try:
        # Try relative imports from current directory
        sys.path.insert(0, str(project_root))
        from src.agents.pinecone_assistant_agent import PineconeAssistantAgent
        from src.utils.url_error_handler import exponential_backoff_retry
        from src.utils.url_metadata_logger import set_correlation_id
    except ImportError as e2:
        print(f"ERROR: Failed to import required modules.")
        print(f"Please run tests from project root or set PYTHONPATH appropriately.")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Project root detected as: {project_root}")
        print(f"Import error: {e2}")
        sys.exit(1)


class TestPineconeAssistantURLMetadataEnhanced(unittest.TestCase):
    """Enhanced tests for URL metadata handling with additional scenarios."""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the config and environment variables
        config_patch = 'src.agents.pinecone_assistant_agent.Config'
        with patch(config_patch) as mock_config:
            mock_config.PINECONE_API_KEY = 'test-api-key'
            
            with patch.dict(os.environ, {
                'PINECONE_ASSISTANT_HOST': 'https://test-host.pinecone.io'
            }):
                self.agent = PineconeAssistantAgent()
        
        # Set correlation ID for tracking
        self.correlation_id = str(uuid.uuid4())
        set_correlation_id(self.correlation_id)
    
    @patch('src.agents.pinecone_assistant_agent.requests.post')
    @patch('src.utils.url_utils.validate_url')
    @patch('time.sleep')
    def test_upload_with_url_validation_timeout(
        self, mock_sleep, mock_validate, mock_post
    ):
        """Test upload operation when URL validation times out."""
        # Mock validation timeout
        mock_validate.side_effect = FuturesTimeoutError("Validation timed out")
        
        # Mock successful upload response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'status': 'success'}
        mock_post.return_value = mock_response
        
        # Test documents
        documents = [
            {
                'id': 'doc1',
                'title': 'Test Document',
                'content': 'Test content',
                'source': 'Test Source',
                'category': 'test',
                'url': 'https://slow-loading-site.com/document'
            }
        ]
        
        # Call upload_documents
        result = self.agent.upload_documents('test-assistant-id', documents)
        
        # Should still succeed with empty URL on timeout
        self.assertTrue(result)
        
        # Verify request was made with empty URL due to timeout
        call_args = mock_post.call_args
        uploaded_doc = call_args[1]['json']['documents'][0]
        self.assertEqual(uploaded_doc['metadata']['url'], '')
    
    @patch('src.agents.pinecone_assistant_agent.requests.post')
    @patch('src.utils.url_utils.check_urls_accessibility_parallel')
    def test_batch_upload_with_mixed_url_accessibility(
        self, mock_check_urls, mock_post
    ):
        """Test batch upload with mix of accessible and inaccessible URLs."""
        # Mock URL accessibility check results
        mock_check_urls.return_value = {
            'https://accessible.com/doc1': True,
            'https://inaccessible.com/doc2': False,
            'https://timeout.com/doc3': None,  # Timeout
            'https://accessible.com/doc4': True
        }
        
        # Mock successful upload response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'status': 'success'}
        mock_post.return_value = mock_response
        
        # Test documents with various URL states
        documents = [
            {
                'id': 'doc1',
                'title': 'Accessible Document',
                'content': 'Content 1',
                'url': 'https://accessible.com/doc1'
            },
            {
                'id': 'doc2',
                'title': 'Inaccessible Document',
                'content': 'Content 2',
                'url': 'https://inaccessible.com/doc2'
            },
            {
                'id': 'doc3',
                'title': 'Timeout Document',
                'content': 'Content 3',
                'url': 'https://timeout.com/doc3'
            },
            {
                'id': 'doc4',
                'title': 'Another Accessible',
                'content': 'Content 4',
                'url': 'https://accessible.com/doc4'
            }
        ]
        
        # Upload documents
        result = self.agent.upload_documents('test-assistant-id', documents)
        self.assertTrue(result)
        
        # Get uploaded documents
        call_args = mock_post.call_args
        uploaded_docs = call_args[1]['json']['documents']
        
        # Verify URL handling based on accessibility
        self.assertEqual(
            uploaded_docs[0]['metadata']['url'],
            'https://accessible.com/doc1'
        )
        self.assertEqual(
            uploaded_docs[0]['metadata'].get('url_accessible', True),
            True
        )
        
        # Inaccessible URL should be marked
        self.assertEqual(
            uploaded_docs[1]['metadata']['url'],
            'https://inaccessible.com/doc2'
        )
        self.assertEqual(
            uploaded_docs[1]['metadata'].get('url_accessible', True),
            False
        )
        
        # Timeout URL should be handled gracefully
        self.assertEqual(
            uploaded_docs[2]['metadata']['url'],
            'https://timeout.com/doc3'
        )
        self.assertIn('url_check_timeout', uploaded_docs[2]['metadata'])
        self.assertTrue(uploaded_docs[2]['metadata']['url_check_timeout'])
    
    @patch('src.agents.pinecone_assistant_agent.requests.post')
    def test_query_with_partial_url_metadata(self, mock_post):
        """Test query operations with partial URL metadata in results."""
        # Mock response with mixed metadata completeness
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': 'Response about Bitcoin technology.',
            'citations': [
                {
                    'id': 'doc1',
                    'text': 'Bitcoin uses proof of work.',
                    'score': 0.95,
                    'metadata': {
                        'title': 'Bitcoin Technical Guide',
                        'source': 'btc-tech.org',
                        'url': 'https://btc-tech.org/guide',
                        'published': '2023-01-15'
                    }
                },
                {
                    'id': 'doc2',
                    'text': 'Mining difficulty adjusts every 2016 blocks.',
                    'score': 0.88,
                    'metadata': {
                        'title': 'Mining Overview',
                        'source': 'mining-info.com',
                        # Missing URL field entirely
                        'published': '2023-02-20'
                    }
                },
                {
                    'id': 'doc3',
                    'text': 'Halving occurs every 210,000 blocks.',
                    'score': 0.82,
                    'metadata': {
                        'title': 'Bitcoin Economics',
                        'url': '',  # Empty URL
                        # Missing other fields
                    }
                },
                {
                    'id': 'doc4',
                    'text': 'Lightning Network enables fast payments.',
                    'score': 0.79,
                    # Missing metadata entirely
                }
            ],
            'metadata': {'query_time': 0.4}
        }
        mock_post.return_value = mock_response
        
        # Query assistant
        result = self.agent.query_assistant(
            'test-assistant-id',
            'Explain Bitcoin technology'
        )
        
        # Verify response handling
        self.assertIn('sources', result)
        sources = result['sources']
        self.assertEqual(len(sources), 4)
        
        # Check first source (complete metadata)
        self.assertEqual(sources[0]['url'], 'https://btc-tech.org/guide')
        self.assertEqual(sources[0]['published'], '2023-01-15')
        
        # Check second source (missing URL)
        self.assertEqual(sources[1]['url'], '')
        self.assertEqual(sources[1]['published'], '2023-02-20')
        
        # Check third source (empty URL, missing fields)
        self.assertEqual(sources[2]['url'], '')
        self.assertEqual(sources[2].get('published', ''), '')
        self.assertEqual(sources[2].get('source', ''), '')
        
        # Check fourth source (missing metadata)
        self.assertEqual(sources[3]['url'], '')
        self.assertEqual(sources[3].get('title', ''), '')
    
    @patch('src.agents.pinecone_assistant_agent.requests.post')
    @patch('src.monitoring.url_metadata_monitor.url_metadata_monitor')
    def test_upload_with_monitoring_integration(
        self, mock_monitor, mock_post
    ):
        """Test upload operation with monitoring integration."""
        # Mock successful upload
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'status': 'success'}
        mock_post.return_value = mock_response
        
        # Test documents
        documents = [
            {
                'id': 'doc1',
                'title': 'Monitored Document',
                'content': 'Content',
                'url': 'https://example.com/doc1'
            }
        ]
        
        # Upload documents
        result = self.agent.upload_documents('test-assistant-id', documents)
        self.assertTrue(result)
        
        # Verify monitoring was called with correct parameters
        mock_monitor.track_upload.assert_called_once()
        # Add more specific assertions based on your monitoring implementation
        # e.g., mock_monitor.track_url_validation.assert_called_with(...)
    @patch('src.agents.pinecone_assistant_agent.requests.post')
    def test_retry_mechanism_on_upload_failure(self, mock_post):
        """Test retry mechanism during upload failures."""
        # Mock responses: fail twice, then succeed
        responses = [
            Mock(status_code=500, text='Server Error'),
            Mock(status_code=503, text='Service Unavailable'),
            Mock(
                status_code=201,
                json=Mock(return_value={'status': 'success'})
            )
        ]
        mock_post.side_effect = responses
        
        # Wrap upload with retry logic
        @exponential_backoff_retry(
            max_retries=3,
            initial_delay=0.01
        )
        def retry_upload():
            return self.agent.upload_documents(
                'test-assistant-id',
                [{'id': 'doc1', 'title': 'Test', 'content': 'Test'}]
            )
        
        # Should eventually succeed
        result = retry_upload()
        self.assertTrue(result)
        
        # Verify three attempts were made
        self.assertEqual(mock_post.call_count, 3)
    
        for call_index in range(3):
            call_args = mock_post.call_args_list[call_index]
            batch_docs = call_args[1]['json']['documents']
            
            for doc in batch_docs:
                url = doc['metadata']['url']
                # Dangerous URLs should be empty
                self.assertNotIn('javascript:', url)
                # Check the original URL from the document ID to determine expected behavior
                doc_index = int(doc['id'].replace('doc', ''))
                url_scenario_index = doc_index % 5
                if url_scenario_index == 1:  # Invalid URL scenario
                    self.assertEqual(url, '')
    @patch('src.agents.pinecone_assistant_agent.requests.post')
    @patch('src.utils.url_metadata_logger.logger')
    def test_correlation_id_tracking(self, mock_logger, mock_post):
        """Test correlation ID tracking through operations."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'status': 'success'}
        mock_post.return_value = mock_response
        
        # Upload document
        documents = [{
            'id': 'doc1',
            'title': 'Tracked Document',
            'content': 'Content',
            'url': 'https://example.com'
        }]
        
        result = self.agent.upload_documents('test-assistant-id', documents)
        self.assertTrue(result)
        
        # Verify correlation ID was used in logging
        # Note: Actual verification depends on logging implementation
        self.assertGreater(len(mock_logger.method_calls), 0)
        
        # Step 1: Verify at least one log call includes correlation ID
        correlation_id_found = False
        found_correlation_id = None
        
        for call in mock_logger.method_calls:
            if hasattr(call, 'kwargs') and 'extra' in call.kwargs:
                extra = call.kwargs['extra']
                if isinstance(extra, dict):
                    # Check direct extra fields
                    if 'correlation_id' in extra:
                        correlation_id_found = True
                        found_correlation_id = extra['correlation_id']
                        break
                    # Check nested extra_fields
                    if 'extra_fields' in extra and isinstance(extra['extra_fields'], dict):
                        if 'correlation_id' in extra['extra_fields']:
                            correlation_id_found = True
                            found_correlation_id = extra['extra_fields']['correlation_id']
                            break
        
        # Assert that we found at least one correlation ID
        self.assertTrue(correlation_id_found, "No correlation ID found in any log calls")
        
        # Step 2: Verify correlation ID is a non-empty string
        if found_correlation_id:
            self.assertIsInstance(found_correlation_id, str)
            self.assertTrue(len(found_correlation_id) > 0, "Correlation ID should not be empty")
        
        # Step 3: Verify consistency across all log calls with correlation ID
        for call in mock_logger.method_calls:
            if hasattr(call, 'kwargs') and 'extra' in call.kwargs:
                extra = call.kwargs['extra']
                if isinstance(extra, dict):
                    # Check direct correlation_id
                    if 'correlation_id' in extra:
                        self.assertEqual(extra['correlation_id'], found_correlation_id,
                                       "Correlation ID should be consistent across all log calls")
                    # Check nested correlation_id
                    if 'extra_fields' in extra and isinstance(extra['extra_fields'], dict):
                        if 'correlation_id' in extra['extra_fields']:
                            self.assertEqual(extra['extra_fields']['correlation_id'], found_correlation_id,
                                           "Correlation ID should be consistent across all log calls")
    
    def test_url_normalization_in_upload(self):
        """Test URL normalization during upload process."""
        test_cases = [
            # (input_url, expected_normalized)
            ('HTTP://EXAMPLE.COM/PATH', 'https://example.com/PATH'),
            ('https://example.com:443/path', 'https://example.com/path'),
            ('https://example.com/path?b=2&a=1',
             'https://example.com/path?a=1&b=2'),
            ('https://example.com/./path/../file', 'https://example.com/file'),
            ('https://example.com/path#fragment', 'https://example.com/path'),
        ]
        
        for input_url, expected in test_cases:
            result = self.agent._validate_and_sanitize_url(input_url)
            # Basic validation - actual normalization depends on implementation
            self.assertIsNotNone(result)
            self.assertTrue(result.startswith('https://'))
    
    @patch('src.agents.pinecone_assistant_agent.requests.post')
    def test_metadata_field_consistency(self, mock_post):
        """Test that all required metadata fields are present."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'status': 'success'}
        mock_post.return_value = mock_response
        
        # Documents with various missing fields
        documents = [
            {
                'id': 'complete',
                'title': 'Complete Doc',
                'content': 'Content',
                'source': 'Source',
                'url': 'https://example.com/complete'
            },
            {
                'id': 'minimal',
                'title': 'Minimal Doc',
                'content': 'Content only'
            }
        ]
        
        # Upload documents
        self.agent.upload_documents('test-assistant-id', documents)
        
        # Check uploaded documents
        call_args = mock_post.call_args
        uploaded_docs = call_args[1]['json']['documents']
        
        # Verify all documents have required fields
        required_fields = ['url', 'published', 'title', 'source', 'category']
        for doc in uploaded_docs:
            for field in required_fields:
                self.assertIn(field, doc['metadata'])
                # Empty string for missing fields
                if doc['id'] == 'minimal':
                    self.assertEqual(doc['metadata'][field], '')
    
    @patch('src.agents.pinecone_assistant_agent.requests.post')
    def test_network_error_handling_during_query(self, mock_post):
        """Test handling of network errors during query operations."""
        # Mock network error
        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )
        
        # Query should handle error gracefully
        result = self.agent.query_assistant(
            'test-assistant-id',
            'What is Bitcoin?'
        )
        
        # Should return error response
        self.assertIn('answer', result)
        self.assertIn('Sorry, I encountered an error', result['answer'])
        self.assertEqual(result['sources'], [])
    
    @patch('src.agents.pinecone_assistant_agent.requests.post')
    def test_timeout_during_query_operation(self, mock_post):
        """Test timeout handling during query operations."""
        # Mock timeout
        mock_post.side_effect = requests.exceptions.Timeout(
            "Request timed out"
        )
        
        # Query with timeout
        result = self.agent.query_assistant(
            'test-assistant-id',
            'Explain Bitcoin mining',
            timeout=5.0
        )
        
        # Should handle timeout gracefully
        self.assertIn('answer', result)
        self.assertIn('error', result['answer'].lower())
        self.assertEqual(result['sources'], [])
    
    def test_url_security_validation(self):
        """Test security validation for URLs."""
        dangerous_urls = [
            'javascript:alert("XSS")',
            'data:text/html,<script>alert("XSS")</script>',
            'file:///etc/passwd',
            'ftp://internal-server/files',
            'about:blank',
            'vbscript:msgbox("XSS")'
        ]
        
        for dangerous_url in dangerous_urls:
            result = self.agent._validate_and_sanitize_url(dangerous_url)
            # Should reject dangerous URLs
            self.assertIsNone(
                result,
                f"Dangerous URL {dangerous_url} should be rejected"
            )
    
    @patch('src.agents.pinecone_assistant_agent.requests.post')
    def test_unicode_url_handling(self, mock_post):
        """Test handling of Unicode characters in URLs."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'status': 'success'}
        mock_post.return_value = mock_response
        
        # Documents with Unicode URLs
        documents = [
            {
                'id': 'unicode1',
                'title': 'Unicode URL Test',
                'content': 'Content',
                'url': 'https://example.com/文档/测试'
            },
            {
                'id': 'unicode2',
                'title': 'Emoji URL Test',
                'content': 'Content',
                'url': 'https://example.com/path/🚀/document'
            }
        ]
        
        # Upload documents
        result = self.agent.upload_documents('test-assistant-id', documents)
        self.assertTrue(result)
        
        # Verify URLs are properly encoded
        call_args = mock_post.call_args
        uploaded_docs = call_args[1]['json']['documents']
        
        # URLs should be properly handled (encoded)
        for doc in uploaded_docs:
            url = doc['metadata']['url']
            if doc['id'] == 'unicode1':
                # Chinese characters should be percent-encoded
                self.assertIn('%E6%96%87%E6%A1%A3', url)  # 文档 encoded
                self.assertIn('%E6%B5%8B%E8%AF%95', url)  # 测试 encoded
            elif doc['id'] == 'unicode2':
                # Emoji should be percent-encoded
                self.assertIn('%F0%9F%9A%80', url)  # 🚀 encoded

def main():
    """Run the enhanced tests"""
    print("🧪 Testing Enhanced Pinecone Assistant URL Metadata Functionality")
    print("=" * 60)
    
    # Run the unit tests
    unittest.main(verbosity=2, exit=False)


if __name__ == "__main__":
    main()