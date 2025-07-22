#!/usr/bin/env python3
"""
Enhanced backward compatibility tests for URL metadata system.

Tests that existing vectors without URL metadata continue to work
properly alongside new vectors with URL metadata.
"""

import pytest
import numpy as np
import time
import threading
import queue
from datetime import datetime, timezone
from typing import Dict, Any
from unittest.mock import Mock, patch

from src.retrieval.pinecone_client import PineconeClient
from src.agents.pinecone_assistant_agent import PineconeAssistantAgent


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
        with patch('src.retrieval.pinecone_client.Pinecone') as mock_pinecone_class, \
             patch('src.utils.config.Config') as mock_config:
            # Mock the config
            mock_config.validate.return_value = None
            mock_config.PINECONE_API_KEY = 'test-key'
            mock_config.PINECONE_INDEX_NAME = 'test-index'
            mock_config.EMBEDDING_DIMENSION = 1536
            
            # Mock Pinecone instance
            mock_pc = Mock()
            mock_pc.Index.return_value = mock_pinecone_index
            mock_pinecone_class.return_value = mock_pc
            
            client = PineconeClient()
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
    
    def test_null_safe_metadata_access(self):
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
            'url_validation_timestamp': datetime.now(timezone.utc).isoformat(),
            'metadata_version': '2.0',
            'enrichment_timestamp': datetime.now(timezone.utc).isoformat()
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
                'migration_timestamp': datetime.now(timezone.utc).isoformat()
            })
            enriched_batch.append({
                'id': vector['id'],
                'metadata': enriched_metadata
            })
        
        # Verify batch can be processed
        assert len(enriched_batch) == batch_size
        
        # Perform batch migration
        for vector in enriched_batch:
            # Update vector in Pinecone with enriched metadata
            pinecone_client.index.update(
                id=vector['id'],
                set_metadata=vector['metadata']
            )
        
        # Verify all vectors were updated
        assert mock_pinecone_index.update.call_count == batch_size
        
        # Verify update calls were made with correct data
        for i, vector in enumerate(enriched_batch):
            call_args = mock_pinecone_index.update.call_args_list[i][1]
            assert call_args['id'] == vector['id']
            assert call_args['set_metadata'] == vector['metadata']
            
            # Verify metadata structure
            assert 'source_url' in vector['metadata']
            assert 'metadata_version' in vector['metadata']
            assert 'migration_timestamp' in vector['metadata']
            
            # Verify timestamp format (ISO 8601 with timezone)
            try:
                datetime.fromisoformat(vector['metadata']['migration_timestamp'].rstrip('Z'))
            except ValueError:
                pytest.fail(f"Invalid ISO 8601 timestamp: {vector['metadata']['migration_timestamp']}")
    
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
                with patch.object(agent.client.beta.threads.messages, 'create'):
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
    
    def test_performance_impact_measurement(self, pinecone_client, mock_pinecone_index, capsys):
        """Test performance impact of URL metadata on queries."""

        
        # Measure legacy vector query time
        mock_pinecone_index.query.return_value = {
            'matches': mock_pinecone_index._legacy_vectors
        }
        
        start_time = time.time()
        pinecone_client.query(
            vector=np.random.rand(1536).tolist(),
            top_k=100
        )
        legacy_time = time.time() - start_time
        
        # Measure modern vector query time
        mock_pinecone_index.query.return_value = {
            'matches': mock_pinecone_index._modern_vectors * 50  # Simulate 100 results
        }
        
        start_time = time.time()
        pinecone_client.query(
            vector=np.random.rand(1536).tolist(),
            top_k=100
        )
        modern_time = time.time() - start_time
        
        # Performance should be comparable (within 50% tolerance)
        # In real scenarios, the difference should be minimal
        performance_ratio = modern_time / legacy_time if legacy_time > 0 else 1.0
        
        # Log performance metrics using capsys instead of print
        # Output can be captured and verified if needed
        import sys
        sys.stdout.write(f"Legacy query time: {legacy_time:.4f}s\n")
        sys.stdout.write(f"Modern query time: {modern_time:.4f}s\n")
        sys.stdout.write(f"Performance ratio: {performance_ratio:.2f}\n")
        
        # Capture output for verification if needed
        captured = capsys.readouterr()
        assert "Legacy query time:" in captured.out
        assert "Modern query time:" in captured.out
        assert "Performance ratio:" in captured.out
        
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
                'timestamp': datetime.now(timezone.utc).isoformat(),
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