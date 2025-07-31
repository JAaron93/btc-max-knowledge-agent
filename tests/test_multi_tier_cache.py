"""
Unit tests for multi-tier audio cache system.

Tests all cache backends, coordination logic, and integration scenarios.

RECOMMENDED SETUP:
    To avoid path manipulation, install the project in development mode:
    $ pip install -e .
    
    Then use standard absolute imports:
    from btc_max_knowledge_agent.utils.multi_tier_audio_cache import MultiTierAudioCache
"""

import os
import sys
import unittest
import tempfile
import shutil
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# NOTE: setup_src_path() is now called once in conftest.py to avoid redundant sys.path modifications
# TODO: Replace this path hack by making the project installable with: pip install -e .
# This would allow using standard absolute imports without sys.path manipulation

from utils.multi_tier_audio_cache import (
    MultiTierAudioCache,
    CacheConfig,
    MemoryCacheBackend,
    SQLiteCacheBackend,
    BaseCacheBackend
)


class TestCacheConfig(unittest.TestCase):
    """Test cache configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CacheConfig()
        
        self.assertEqual(config.backend, "memory")
        self.assertEqual(config.memory_max_size, 100)
        self.assertEqual(config.memory_max_mb, 50)
        self.assertEqual(config.ttl_hours, 24)
        self.assertTrue(config.enable_cache_warming)
        self.assertTrue(config.enable_statistics)
    
    def test_config_from_env(self):
        """Test configuration from environment variables."""
        env_vars = {
            'CACHE_BACKEND': 'sqlite',
            'CACHE_MEMORY_MAX_SIZE': '200',
            'CACHE_MEMORY_MAX_MB': '100',
            'CACHE_TTL_HOURS': '48',
            'CACHE_ENABLE_WARMING': 'false'
        }
        
        with patch.dict(os.environ, env_vars):
            config = CacheConfig.from_env()
            
            self.assertEqual(config.backend, 'sqlite')
            self.assertEqual(config.memory_max_size, 200)
            self.assertEqual(config.memory_max_mb, 100)
            self.assertEqual(config.ttl_hours, 48)
            self.assertFalse(config.enable_cache_warming)


class TestMemoryCacheBackend(unittest.TestCase):
    """Test memory cache backend."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = CacheConfig(memory_max_size=5, memory_max_mb=1)
        self.cache = MemoryCacheBackend(self.config)
        self.test_key = "test_key_123"
        self.test_data = b"test audio data"
    
    def test_put_and_get(self):
        """Test basic put and get operations."""
        # Test put
        success = self.cache.put(self.test_key, self.test_data)
        self.assertTrue(success)
        
        # Test get
        retrieved = self.cache.get(self.test_key)
        self.assertEqual(retrieved, self.test_data)
    
    def test_has(self):
        """Test has operation."""
        # Initially should not exist
        self.assertFalse(self.cache.has(self.test_key))
        
        # After putting, should exist
        self.cache.put(self.test_key, self.test_data)
        self.assertTrue(self.cache.has(self.test_key))
    
    def test_remove(self):
        """Test remove operation."""
        # Put data
        self.cache.put(self.test_key, self.test_data)
        self.assertTrue(self.cache.has(self.test_key))
        
        # Remove data
        removed = self.cache.remove(self.test_key)
        self.assertTrue(removed)
        self.assertFalse(self.cache.has(self.test_key))
        
        # Try to remove non-existent key
        removed = self.cache.remove("non_existent")
        self.assertFalse(removed)
    
    def test_clear(self):
        """Test clear operation."""
        # Put multiple entries
        for i in range(3):
            self.cache.put(f"key_{i}", f"data_{i}".encode())
        
        # Verify entries exist
        stats = self.cache.get_stats()
        self.assertEqual(stats['entry_count'], 3)
        
        # Clear cache
        self.cache.clear()
        
        # Verify cache is empty
        stats = self.cache.get_stats()
        self.assertEqual(stats['entry_count'], 0)
    
    def test_ttl_expiration(self):
        """Test TTL expiration."""
        # Put with short TTL
        self.cache.put(self.test_key, self.test_data, ttl_seconds=1)
        
        # Should exist immediately
        self.assertTrue(self.cache.has(self.test_key))
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired
        self.assertFalse(self.cache.has(self.test_key))
        self.assertIsNone(self.cache.get(self.test_key))
    
    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        # Put entries with different TTLs
        self.cache.put("key1", b"data1", ttl_seconds=1)
        self.cache.put("key2", b"data2", ttl_seconds=10)
        
        # Wait for first to expire
        time.sleep(1.1)
        
        # Cleanup expired
        removed_count = self.cache.cleanup_expired()
        self.assertEqual(removed_count, 1)
        
        # Verify only non-expired entry remains
        self.assertFalse(self.cache.has("key1"))
        self.assertTrue(self.cache.has("key2"))
    
    def test_stats(self):
        """Test statistics reporting."""
        # Put test data
        self.cache.put(self.test_key, self.test_data)
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats['backend_type'], 'memory')
        self.assertEqual(stats['entry_count'], 1)
        self.assertEqual(stats['total_size_bytes'], len(self.test_data))
        self.assertIn('ttl_entries', stats)


class TestSQLiteCacheBackend(unittest.TestCase):
    """Test SQLite cache backend."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CacheConfig(
            persistent_path=self.temp_dir,
            persistent_max_size=10,
            persistent_max_mb=1
        )
        self.cache = SQLiteCacheBackend(self.config)
        self.test_key = "test_key_123"
        self.test_data = b"test audio data"
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_put_and_get(self):
        """Test basic put and get operations."""
        # Test put
        success = self.cache.put(self.test_key, self.test_data)
        self.assertTrue(success)
        
        # Test get
        retrieved = self.cache.get(self.test_key)
        self.assertEqual(retrieved, self.test_data)
    
    def test_persistence(self):
        """Test data persistence across instances."""
        # Put data in first instance
        self.cache.put(self.test_key, self.test_data)
        
        # Create new instance with same config
        new_cache = SQLiteCacheBackend(self.config)
        
        # Should retrieve data from persistent storage
        retrieved = new_cache.get(self.test_key)
        self.assertEqual(retrieved, self.test_data)
    
    def test_has(self):
        """Test has operation."""
        self.assertFalse(self.cache.has(self.test_key))
        
        self.cache.put(self.test_key, self.test_data)
        self.assertTrue(self.cache.has(self.test_key))
    
    def test_remove(self):
        """Test remove operation."""
        self.cache.put(self.test_key, self.test_data)
        self.assertTrue(self.cache.has(self.test_key))
        
        removed = self.cache.remove(self.test_key)
        self.assertTrue(removed)
        self.assertFalse(self.cache.has(self.test_key))
    
    def test_clear(self):
        """Test clear operation."""
        # Put multiple entries
        for i in range(3):
            self.cache.put(f"key_{i}", f"data_{i}".encode())
        
        stats = self.cache.get_stats()
        self.assertEqual(stats['entry_count'], 3)
        
        self.cache.clear()
        
        stats = self.cache.get_stats()
        self.assertEqual(stats['entry_count'], 0)
    
    def test_ttl_expiration(self):
        """Test TTL expiration in SQLite."""
        # Put with short TTL
        self.cache.put(self.test_key, self.test_data, ttl_seconds=1)
        self.assertTrue(self.cache.has(self.test_key))
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired
        self.assertFalse(self.cache.has(self.test_key))
        self.assertIsNone(self.cache.get(self.test_key))
    
    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        self.cache.put("key1", b"data1", ttl_seconds=1)
        self.cache.put("key2", b"data2", ttl_seconds=10)
        
        time.sleep(1.1)
        
        removed_count = self.cache.cleanup_expired()
        self.assertEqual(removed_count, 1)
        
        self.assertFalse(self.cache.has("key1"))
        self.assertTrue(self.cache.has("key2"))
    
    def test_stats(self):
        """Test statistics reporting."""
        self.cache.put(self.test_key, self.test_data)
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats['backend_type'], 'sqlite')
        self.assertEqual(stats['entry_count'], 1)
        self.assertEqual(stats['total_size_bytes'], len(self.test_data))
        self.assertIn('db_path', stats)


class TestMultiTierAudioCache(unittest.TestCase):
    """Test multi-tier cache coordination."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CacheConfig(
            backend="multi-tier",
            memory_max_size=5,
            memory_max_mb=1,
            persistent_path=self.temp_dir,
            persistent_max_size=10,
            ttl_hours=1
        )
        self.cache = MultiTierAudioCache(self.config)
        self.test_text = "This is a test message for caching"
        self.test_data = b"test audio data" * 10
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cache_hierarchy(self):
        """Test cache hierarchy: Memory → Persistent → Distributed."""
        # Put data (should go to all tiers)
        cache_key = self.cache.put(self.test_text, self.test_data)
        self.assertIsInstance(cache_key, str)
        
        # Get data (should hit memory first)
        retrieved = self.cache.get(self.test_text)
        self.assertEqual(retrieved, self.test_data)
        
        # Verify it's in memory cache
        self.assertTrue(self.cache.backends['memory'].has(cache_key))
        
        # Clear memory cache
        self.cache.backends['memory'].clear()
        
        # Get again (should hit persistent cache and warm memory)
        retrieved = self.cache.get(self.test_text)
        self.assertEqual(retrieved, self.test_data)
        
        # Verify memory was warmed
        self.assertTrue(self.cache.backends['memory'].has(cache_key))
    
    def test_has(self):
        """Test has operation across tiers."""
        self.assertFalse(self.cache.has(self.test_text))
        
        self.cache.put(self.test_text, self.test_data)
        self.assertTrue(self.cache.has(self.test_text))
    
    def test_remove(self):
        """Test remove operation across tiers."""
        self.cache.put(self.test_text, self.test_data)
        self.assertTrue(self.cache.has(self.test_text))
        
        removed = self.cache.remove(self.test_text)
        self.assertTrue(removed)
        self.assertFalse(self.cache.has(self.test_text))
    
    def test_clear(self):
        """Test clear operation across tiers."""
        # Put multiple entries
        for i in range(3):
            self.cache.put(f"text_{i}", f"data_{i}".encode())
        
        # Verify entries exist
        stats = self.cache.get_comprehensive_stats()
        self.assertGreater(stats['backends']['memory']['entry_count'], 0)
        
        # Clear all tiers
        self.cache.clear()
        
        # Verify all tiers are empty
        stats = self.cache.get_comprehensive_stats()
        self.assertEqual(stats['backends']['memory']['entry_count'], 0)
        self.assertEqual(stats['backends']['persistent']['entry_count'], 0)
    
    def test_cache_warming(self):
        """Test cache warming functionality."""
        warm_entries = [
            ("warm_text_1", b"warm_data_1"),
            ("warm_text_2", b"warm_data_2")
        ]
        
        warmed_count = self.cache.warm_cache(warm_entries)
        self.assertEqual(warmed_count, 2)
        
        # Verify entries are cached
        for text, data in warm_entries:
            retrieved = self.cache.get(text)
            self.assertEqual(retrieved, data)
    
    def test_comprehensive_stats(self):
        """Test comprehensive statistics reporting."""
        # Put some data
        self.cache.put(self.test_text, self.test_data)
        
        stats = self.cache.get_comprehensive_stats()
        
        # Check structure
        self.assertIn('config', stats)
        self.assertIn('performance', stats)
        self.assertIn('backends', stats)
        
        # Check performance stats
        self.assertIn('hits', stats['performance'])
        self.assertIn('misses', stats['performance'])
        self.assertIn('puts', stats['performance'])
        
        # Check backend stats
        self.assertIn('memory', stats['backends'])
        self.assertIn('persistent', stats['backends'])
        
        # Check hit rates
        for tier in ['memory', 'persistent', 'distributed']:
            self.assertIn(f'{tier}_hit_rate', stats['performance'])
    
    def test_cleanup_expired(self):
        """Test cleanup across all tiers."""
        # This is mainly testing the coordination
        results = self.cache.cleanup_expired()
        
        self.assertIsInstance(results, dict)
        self.assertIn('memory', results)
        self.assertIn('persistent', results)


class TestConcurrency(unittest.TestCase):
    """Test cache behavior under concurrent access."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CacheConfig(
            backend="multi-tier",
            memory_max_size=100,
            persistent_path=self.temp_dir
        )
        self.cache = MultiTierAudioCache(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_concurrent_put_get(self):
        """Test concurrent put and get operations."""
        results = []
        errors = []
        
        def worker(thread_id):
            try:
                for i in range(10):
                    text = f"thread_{thread_id}_message_{i}"
                    data = f"audio_data_{thread_id}_{i}".encode()
                    
                    # Put data
                    self.cache.put(text, data)
                    
                    # Get data
                    retrieved = self.cache.get(text)
                    
                    if retrieved == data:
                        results.append(f"thread_{thread_id}_success_{i}")
                    else:
                        errors.append(f"thread_{thread_id}_mismatch_{i}")
            except Exception as e:
                errors.append(f"thread_{thread_id}_error: {e}")
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 50)  # 5 threads * 10 operations each
    
    def test_concurrent_cache_operations(self):
        """Test various concurrent cache operations."""
        def put_worker():
            for i in range(20):
                self.cache.put(f"put_text_{i}", f"put_data_{i}".encode())
        
        def get_worker():
            for i in range(20):
                self.cache.get(f"put_text_{i}")
        
        def stats_worker():
            for _ in range(10):
                self.cache.get_comprehensive_stats()
                time.sleep(0.01)
        
        # Start concurrent operations
        threads = [
            threading.Thread(target=put_worker),
            threading.Thread(target=get_worker),
            threading.Thread(target=stats_worker)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify cache is still functional
        test_text = "final_test"
        test_data = b"final_data"
        
        self.cache.put(test_text, test_data)
        retrieved = self.cache.get(test_text)
        self.assertEqual(retrieved, test_data)


if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestCacheConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryCacheBackend))
    suite.addTests(loader.loadTestsFromTestCase(TestSQLiteCacheBackend))
    suite.addTests(loader.loadTestsFromTestCase(TestMultiTierAudioCache))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrency))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)