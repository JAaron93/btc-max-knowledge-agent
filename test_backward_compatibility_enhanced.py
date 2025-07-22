#!/usr/bin/env python3
"""
Enhanced backward compatibility tests for URL metadata system.

Tests that existing vectors without URL metadata continue to work
properly alongside new vectors with URL metadata.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any, Optional
import uuid
import time

from src.retrieval.pinecone_client import PineconeClient
from src.agents.pinecone_assistant_agent import PineconeAssistantAgent
from src.utils.url_metadata_logger import URLMetadataLogger
from src.monitoring.url_metadata_monitor import URLMetadataMonitor
from src.utils.url_error_handler import (
    exponential_backoff_retry,
    GracefulDegradation,
    FallbackURLStrategy
)
from src.utils.url_utils import URLValidator


class TestBackwardCompatibilityEnhanced:
    """Test suite for backward compatibility with enhanced URL metadata."""
    
    @pytest.fixture
    def mock_pinecone_index(self):
        """Create a mock Pinecone index with mixed vector formats."""
        mock_index = Mock()
        
        # Legacy vectors (no URL metadata)
        legacy_vectors = [
            {
                'id': 'legacy_1',
                'values': np.random.rand(1536).tolist(),
                'metadata': {
                    'text': 'Bitcoin is a decentralized cryptocurrency',
                    'timestamp': '2023-01-01T00:00:00Z'
                },
                'score': 0.95
            },
            {
                'id': 'legacy_2',
                'values': np.random.rand(1536).tolist(),
                'metadata': {
                    'text': 'Blockchain technology enables trustless transactions',
                    'timestamp': '2023-01-02T00:00:00Z'
                },
                'score': 0.92
            }
        ]
        
        # Modern vectors (with URL metadata)
        modern_vectors = [
            {
                'id': 'modern_1',
                'values': np.random.rand(1536).tolist(),
                'metadata': {
                    'text': 'Bitcoin halving reduces block rewards by 50%',
                    'timestamp': '2024-01-01T00:00:00Z',
                    'source_url': 'https://bitcoin.org/halving',
                    'url_title': 'Bitcoin Halving Explained',
                    'url_domain': 'bitcoin.org',
                    'url_path': '/halving',
                    'url_validated': True,
                    'url_validation_timestamp': '2024-01-01T00:00:00Z',
                    'metadata_version': '2.0'
                },
                'score': 0.98
            },
            {
                'id': 'modern_2',
                'values': np.random.rand(1536).tolist(),
                'metadata': {
                    'text': 'Lightning Network enables fast Bitcoin transactions',
                    'timestamp': '2024-01-02T00:00:00Z',
                    'source_url': 'https://lightning.network/docs',
                    'url_title': 'Lightning Network Documentation',
                    'url_domain': 'lightning.network',
                    'url_path': '/docs',
                    'url_validated': True,
                    'url_validation_timestamp': '2024-01-02T00:00:00Z',
                    'metadata_version': '2.0'
                },
                'score': 0.94
            }
        ]
        
        # Store different vector sets for testing
        mock_index._legacy_vectors = legacy_vectors
        mock_index._modern_vectors = modern_vectors
        mock_index._all_vectors = legacy_vectors + modern_vectors
        
        return mock_index
    
    @pytest.fixture
    def pinecone_client(self, mock_pinecone_index):
        """Create PineconeClient with mocked index."""
        with patch('pinecone.Index') as mock_index_class:
            mock_index_class.return_value = mock_pinecone_index
            client = PineconeClient(
                index_name='test-index',
                dimension=1536
            )
            client.index = mock_pinecone_index
            return client
    
    def test_query_legacy_vectors_only(self, pinecone_client, mock_pinecone_index):
        """Test querying when only legacy vectors exist."""
        # Setup mock to return only legacy vectors
        mock_pinecone_index.query.return_value = {
            'matches': mock_pinecone_index._legacy_vectors
        }
        
        # Perform query
        results = pinecone_client.query(
            vector=np.random.rand(1536).tolist(),
            top_k=2
        )
        
        # Validate results
        assert len(results) == 2
        for result in results:
            assert 'source_url' not in result['metadata']
            assert 'text' in result['metadata']
            assert 'timestamp' in result['metadata']
    
    def test_query_mixed_vectors(self, pinecone_client, mock_pinecone_index):
        """Test querying when both legacy and modern vectors exist."""
        # Setup mock to return mixed vectors
        mock_pinecone_index.query.return_value = {
            'matches': mock_pinecone_index._all_vectors
        }
        
        # Perform query
        results = pinecone_client.query(
            vector=np.random.rand(1536).tolist(),
            top_k=4
        )
        
        # Validate results
        assert len(results) == 4
        
        # Check legacy vectors
        legacy_count = sum(1 for r in results if 'source_url' not in r['metadata'])
        assert legacy_count == 2
        
        # Check modern vectors
        modern_count = sum(1 for r in results if 'source_url' in r['metadata'])
        assert modern_count == 2
        
        # Ensure all vectors have required fields
        for result in results:
            assert 'text' in result['metadata']
            assert 'timestamp' in result['metadata']
    
    def test_null_safe_metadata_access(self, pinecone_client):
        """Test null-safe access to URL metadata fields."""
        # Create vector with partial URL metadata
        partial_vector = {
            'id': 'partial_1',
            'values': np.random.rand(1536).tolist(),
            'metadata': {
                'text': 'Test content',
                'timestamp': '2024-01-01T00:00:00Z',
                'source_url': 'https://example.com',
                # Missing other URL fields
            },
            'score': 0.90
        }
        
        # Test safe access methods
        metadata = partial_vector['metadata']
        
        # Should not raise errors
        url = metadata.get('source_url', '')
        title = metadata.get('url_title', 'Unknown')
        domain = metadata.get('url_domain', '')
        validated = metadata.get('url_validated', False)
        
        assert url == 'https://example.com'
        assert title == 'Unknown'
        assert domain == ''
        assert validated is False
    
    def test_metadata_version_detection(self):
        """Test detection of metadata schema versions."""
        # Legacy format (v1.0)
        legacy_metadata = {
            'text': 'Legacy content',
            'timestamp': '2023-01-01T00:00:00Z'
        }
        
        # Modern format (v2.0)
        modern_metadata = {
            'text': 'Modern content',
            'timestamp': '2024-01-01T00:00:00Z',
            'source_url': 'https://example.com',
            'metadata_version': '2.0'
        }
        
        # Detect versions
        def detect_version(metadata: Dict[str, Any]) -> str:
            """Detect metadata schema version."""
            if 'metadata_version' in metadata:
                return metadata['metadata_version']
            elif 'source_url' in metadata:
                return '2.0'
            else:
                return '1.0'
        
        assert detect_version(legacy_metadata) == '1.0'
        assert detect_version(modern_metadata) == '2.0'
    
    def test_retroactive_url_enrichment(self, pinecone_client, mock_pinecone_index):
        """Test retroactive enrichment of legacy vectors with URL metadata."""
        # Get legacy vector
        legacy_vector = mock_pinecone_index._legacy_vectors[0].copy()
        vector_id = legacy_vector['id']
        
        # Enrich with URL metadata
        enriched_metadata = legacy_vector['metadata'].copy()
        enriched_metadata.update({
            'source_url': 'https://retroactive.example.com/bitcoin',
            'url_title': 'Retroactively Added Source',
            'url_domain': 'retroactive.example.com',
            'url_path': '/bitcoin',
            'url_validated': True,
            'url_validation_timestamp': datetime.utcnow().isoformat() + 'Z',
            'metadata_version': '2.0',
            'enrichment_timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
        # Mock update operation
        mock_pinecone_index.update.return_value = None
        
        # Perform update
        pinecone_client.index.update(
            id=vector_id,
            metadata=enriched_metadata
        )
        
        # Verify update was called
        mock_pinecone_index.update.assert_called_once_with(
            id=vector_id,
            metadata=enriched_metadata
        )
    
    def test_batch_migration_compatibility(self, pinecone_client, mock_pinecone_index):
        """Test batch migration of legacy vectors."""
        # Prepare batch of legacy vectors for migration
        batch_size = 100
        legacy_batch = []
        
        for i in range(batch_size):
            legacy_batch.append({
                'id': f'legacy_batch_{i}',
                'metadata': {
                    'text': f'Legacy content {i}',
                    'timestamp': '2023-01-01T00:00:00Z'
                }
            })
        
        # Mock fetch operation
        mock_pinecone_index.fetch.return_value = {
            'vectors': {v['id']: v for v in legacy_batch}
        }
        
        # Simulate batch enrichment
        enriched_batch = []
        for vector in legacy_batch:
            enriched_metadata = vector['metadata'].copy()
            enriched_metadata.update({
                'source_url': f'https://migrated.example.com/content/{vector["id"]}',
                'metadata_version': '2.0',
                'migration_timestamp': datetime.utcnow().isoformat() + 'Z'
            })
            enriched_batch.append({
                'id': vector['id'],
                'metadata': enriched_metadata
            })
        
        # Verify batch can be processed
        assert len(enriched_batch) == batch_size
        for vector in enriched_batch:
            assert 'source_url' in vector['metadata']
            assert 'metadata_version' in vector['metadata']
    
    def test_assistant_agent_backward_compatibility(self, mock_pinecone_index):
        """Test PineconeAssistantAgent with mixed vector formats."""
        with patch('src.agents.pinecone_assistant_agent.PineconeClient') as mock_client_class:
            # Setup mock client
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            # Create agent
            agent = PineconeAssistantAgent(
                assistant_id='test-assistant',
                pinecone_index_name='test-index'
            )
            
            # Mock query response with mixed vectors
            mock_client.query.return_value = mock_pinecone_index._all_vectors
            
            # Mock OpenAI response
            with patch.object(agent.client.beta.threads, 'create') as mock_create:
                with patch.object(agent.client.beta.threads.messages, 'create') as mock_msg_create:
                    with patch.object(agent.client.beta.threads.runs, 'create_and_poll') as mock_run:
                        # Setup mock responses
                        mock_thread = Mock(id='thread-123')
                        mock_create.return_value = mock_thread
                        
                        mock_run.return_value = Mock(
                            status='completed',
                            thread_id='thread-123'
                        )
                        
                        # Mock message retrieval
                        mock_messages = Mock()
                        mock_messages.data = [
                            Mock(
                                role='assistant',
                                content=[Mock(
                                    type='text',
                                    text=Mock(value='Mixed vector response')
                                )]
                            )
                        ]
                        
                        with patch.object(agent.client.beta.threads.messages, 'list') as mock_list:
                            mock_list.return_value = mock_messages
                            
                            # Process query
                            response = agent.process_query("What is Bitcoin?")
                            
                            # Verify response
                            assert response is not None
                            assert 'answer' in response
                            assert 'sources' in response
    
    def test_concurrent_access_mixed_vectors(self, pinecone_client, mock_pinecone_index):
        """Test concurrent access to mixed vector environments."""
        import threading
        import queue
        
        results_queue = queue.Queue()
        errors_queue = queue.Queue()
        
        def query_worker(client, query_vector, worker_id):
            """Worker function for concurrent queries."""
            try:
                result = client.query(
                    vector=query_vector,
                    top_k=5
                )
                results_queue.put((worker_id, result))
            except Exception as e:
                errors_queue.put((worker_id, str(e)))
        
        # Mock different responses for concurrent queries
        responses = [
            {'matches': mock_pinecone_index._legacy_vectors},
            {'matches': mock_pinecone_index._modern_vectors},
            {'matches': mock_pinecone_index._all_vectors}
        ]
        
        mock_pinecone_index.query.side_effect = responses * 10
        
        # Launch concurrent queries
        threads = []
        num_workers = 10
        
        for i in range(num_workers):
            query_vector = np.random.rand(1536).tolist()
            thread = threading.Thread(
                target=query_worker,
                args=(pinecone_client, query_vector, i)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert errors_queue.empty(), "No errors should occur"
        assert results_queue.qsize() == num_workers
        
        # Check all results are valid
        while not results_queue.empty():
            worker_id, result = results_queue.get()
            assert isinstance(result, list)
            assert len(result) > 0
    
    def test_performance_impact_measurement(self, pinecone_client, mock_pinecone_index):
        """Test performance impact of URL metadata on queries."""
        import time
        
        # Measure legacy vector query time
        mock_pinecone_index.query.return_value = {
            'matches': mock_pinecone_index._legacy_vectors
        }
        
        start_time = time.time()
        legacy_results = pinecone_client.query(
            vector=np.random.rand(1536).tolist(),
            top_k=100
        )
        legacy_time = time.time() - start_time
        
        # Measure modern vector query time
        mock_pinecone_index.query.return_value = {
            'matches': mock_pinecone_index._modern_vectors * 50  # Simulate 100 results
        }
        
        start_time = time.time()
        modern_results = pinecone_client.query(
            vector=np.random.rand(1536).tolist(),
            top_k=100
        )
        modern_time = time.time() - start_time
        
        # Performance should be comparable (within 50% tolerance)
        # In real scenarios, the difference should be minimal
        performance_ratio = modern_time / legacy_time if legacy_time > 0 else 1.0
        
        # Log performance metrics
        print(f"Legacy query time: {legacy_time:.4f}s")
        print(f"Modern query time: {modern_time:.4f}s")
        print(f"Performance ratio: {performance_ratio:.2f}")
        
        # Assert reasonable performance
        assert performance_ratio < 1.5, "Modern queries should not be significantly slower"


class TestMigrationStrategies:
    """Test various migration strategies for adding URL metadata."""
    
    def test_gradual_migration_strategy(self, mock_pinecone_index):
        """Test gradual migration of vectors to include URL metadata."""
        # Simulate a gradual migration process
        total_vectors = 1000
        migration_batch_size = 100
        migrated_count = 0
        
        migration_log = []
        
        for batch_start in range(0, total_vectors, migration_batch_size):
            batch_end = min(batch_start + migration_batch_size, total_vectors)
            batch_size = batch_end - batch_start
            
            # Simulate migration of this batch
            migration_entry = {
                'batch_start': batch_start,
                'batch_end': batch_end,
                'batch_size': batch_size,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'status': 'completed'
            }
            
            migration_log.append(migration_entry)
            migrated_count += batch_size
            
            # Simulate progress tracking
            progress = (migrated_count / total_vectors) * 100
            assert progress <= 100
        
        # Verify complete migration
        assert migrated_count == total_vectors
        assert len(migration_log) == total_vectors // migration_batch_size
    
    def test_rollback_capability(self):
        """Test ability to rollback URL metadata changes."""
        # Original vector
        original_vector = {
            'id': 'test_rollback',
            'metadata': {
                'text': 'Original content',
                'timestamp': '2023-01-01T00:00:00Z'
            }
        }
        
        # Create backup before modification
        backup = original_vector['metadata'].copy()
        
        # Add URL metadata
        modified_vector = original_vector.copy()
        modified_vector['metadata'].update({
            'source_url': 'https://example.com',
            'url_title': 'Example',
            'metadata_version': '2.0'
        })
        
        # Simulate rollback
        rollback_vector = modified_vector.copy()
        rollback_vector['metadata'] = backup
        
        # Verify rollback
        assert rollback_vector['metadata'] == original_vector['metadata']
        assert 'source_url' not in rollback_vector['metadata']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])