"""
Example integration of optimized logging in the PineconeClient.

This example demonstrates how to integrate the optimized logging system
into existing code to achieve performance improvements.
"""

import os
import sys
import time
from typing import List, Dict, Any

# Add src to path for imports
from pathlib import Path
src_dir = Path(__file__).resolve().parent.parent / "src"
# Check if directory exists before adding to sys.path
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from utils.optimized_logging import (
    PerformanceOptimizedLogger,
    timed_operation,
    configure_optimized_logging
)


class OptimizedPineconeClient:
    """Example of PineconeClient with optimized logging integration."""
    
    def __init__(self):
        # Use optimized logger instead of standard logging
        self.logger = PerformanceOptimizedLogger(__name__)
        
        # Configure optimized logging for the application
        configure_optimized_logging()
        
        print("✅ OptimizedPineconeClient initialized with performance logging")
    
    def validate_and_sanitize_url(self, url: str) -> str:
        """Example URL validation with optimized logging."""
        
        # Only perform expensive validation logging if debug is enabled
        if self.logger.is_debug_enabled():
            # This expensive operation only runs when debug logging is on
            detailed_validation = self._perform_detailed_url_analysis(url)
            self.logger.debug(f"Detailed URL analysis: {detailed_validation}")
        
        # Use lazy logging for potentially expensive operations
        self.logger.info_lazy(
            lambda: f"Validating URL: {self._format_url_for_logging(url)}"
        )
        
        # Simulate validation logic
        if url and url.startswith(('http://', 'https://')):
            self.logger.debug("URL validation passed")
            return url
        else:
-def validate_and_sanitize_url(self, url: str) -> str:
+def validate_and_sanitize_url(self, url: str | None) -> str | None:
            return None
    
    @timed_operation(PerformanceOptimizedLogger("timing"), "upsert_documents")
    def upsert_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Example document upsert with performance timing."""
        
        self.logger.info(f"Starting upsert of {len(documents)} documents")
        
        successful_count = 0
        failed_count = 0
        
        for i, doc in enumerate(documents):
            try:
                # Simulate document processing
                time.sleep(0.001)  # Simulate work
                
                # Only log detailed info for failures or when debug is enabled
                if self.logger.is_debug_enabled():
                    self.logger.debug(f"Processing document {i}: {doc.get('id', 'unknown')}")
                
                successful_count += 1
                
            except Exception as e:
                failed_count += 1
                # Always log errors
                self.logger.error(f"Failed to process document {i}: {e}")
        
        # Use lazy logging for success summary to avoid string formatting overhead
        self.logger.info_lazy(
            lambda: f"Upsert completed: {successful_count} successful, {failed_count} failed"
        )
        
        return failed_count == 0
    
    def query_similar(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """Example query with optimized logging."""
        
        # Avoid expensive logging operations in production
        if not self.logger.is_info_enabled():
            # Skip all info-level logging overhead in production
            return self._perform_query_internal(query_embedding, top_k)
        
        # Only format expensive log messages when needed
        self.logger.info_lazy(
            lambda: f"Querying for similar documents (top_k={top_k}, embedding_dim={len(query_embedding)})"
        )
        
        results = self._perform_query_internal(query_embedding, top_k)
        
        # Conditional detailed logging
        if self.logger.is_debug_enabled():
            for i, result in enumerate(results[:3]):  # Only log first 3 for debugging
                self.logger.debug(f"Result {i}: {result.get('id')} (score: {result.get('score', 0):.3f})")
        
        self.logger.info(f"Query returned {len(results)} results")
        return results
    
    def _perform_detailed_url_analysis(self, url: str) -> Dict[str, Any]:
        """Expensive URL analysis that should only run when debug logging is enabled."""
        # Simulate expensive analysis
        time.sleep(0.01)
        
        return {
            "length": len(url),
            "scheme": url.split("://")[0] if "://" in url else None,
            "has_params": "?" in url,
            "analysis_time": time.time()
        }
    
    def _format_url_for_logging(self, url: str) -> str:
        """Format URL for logging (potentially expensive)."""
        if len(url) > 100:
            return url[:97] + "..."
        return url
    
    def _perform_query_internal(self, query_embedding: List[float], top_k: int) -> List[Dict]:
        """Internal query implementation."""
        # Simulate query processing
        time.sleep(0.005)
        
        # Return mock results
        return [
            {"id": f"doc_{i}", "score": 0.9 - i * 0.1, "metadata": {"title": f"Document {i}"}}
            for i in range(min(top_k, 3))
        ]


def demonstrate_performance_improvement():
    """Demonstrate the performance improvements of optimized logging."""
    
    print("=== Optimized Logging Performance Demonstration ===\n")
    
    # Test with production settings (minimal logging)
    print("1. Testing with PRODUCTION settings (LOG_LEVEL=WARNING)...")
    os.environ["LOG_LEVEL"] = "WARNING"
    os.environ["ENVIRONMENT"] = "production"
    
    client = OptimizedPineconeClient()
    
    # Performance test with disabled debug logging
    start_time = time.time()
    for i in range(100):
        url = f"https://example{i}.com/path/to/resource"
        client.validate_and_sanitize_url(url)
    
    production_time = time.time() - start_time
    print(f"Production logging time (100 operations): {production_time:.3f}s")
    print(f"Average per operation: {(production_time / 100 * 1000):.2f}ms\n")
    
    # Test with development settings (verbose logging)
    print("2. Testing with DEVELOPMENT settings (LOG_LEVEL=DEBUG)...")
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["ENVIRONMENT"] = "development"
    
    # Reconfigure logging
    configure_optimized_logging()
    client = OptimizedPineconeClient()
    
    start_time = time.time()
    for i in range(10):  # Fewer iterations since debug logging is expensive
        url = f"https://example{i}.com/path/to/resource"
        client.validate_and_sanitize_url(url)
    
    debug_time = time.time() - start_time
    print(f"Debug logging time (10 operations): {debug_time:.3f}s")
    print(f"Average per operation: {(debug_time / 10 * 1000):.2f}ms\n")
    
    # Demonstrate document upsert with timing
    print("3. Testing document upsert with performance timing...")
    documents = [
        {"id": f"doc_{i}", "content": f"Content for document {i}", "url": f"https://example{i}.com"}
        for i in range(5)
    ]
    
    result = client.upsert_documents(documents)
    print(f"Upsert result: {'Success' if result else 'Failed'}\n")
    
    # Demonstrate query operations
    print("4. Testing query operations...")
    query_embedding = [0.1] * 1536  # Mock embedding
    results = client.query_similar(query_embedding, top_k=3)
    print(f"Query returned {len(results)} results\n")
    
    print("=== Key Performance Benefits ===")
    print("✅ Conditional logging prevents expensive operations when logging is disabled")
    print("✅ Lazy evaluation avoids string formatting overhead")
    print("✅ Environment-based configuration optimizes for production vs development")
    print("✅ Timed operations provide performance insights when needed")
    print("✅ Reduced third-party library logging noise")


def show_migration_example():
    """Show how to migrate existing code to use optimized logging."""
    
    print("\n=== Migration Example ===\n")
    
    print("BEFORE (Standard Logging):")
    print("""
import logging

logger = logging.getLogger(__name__)

def process_documents(documents):
    logger.debug(f"Processing {len(documents)} documents: {[d['id'] for d in documents]}")
    for doc in documents:
        expensive_analysis = analyze_document(doc)  # Always runs!
        logger.debug(f"Analysis result: {expensive_analysis}")
    """)
    
    print("\nAFTER (Optimized Logging):")
    print("""
from utils.optimized_logging import PerformanceOptimizedLogger

logger = PerformanceOptimizedLogger(__name__)

def process_documents(documents):
    # Lazy evaluation - only formats if debug is enabled
    logger.debug_lazy(lambda: f"Processing {len(documents)} documents: {[d['id'] for d in documents]}")
    
    for doc in documents:
        # Conditional execution - only runs if debug logging is enabled
        if logger.is_debug_enabled():
            expensive_analysis = analyze_document(doc)
            logger.debug(f"Analysis result: {expensive_analysis}")
    """)
    
    print("\n🚀 Key Changes:")
    print("1. Replace logging.getLogger() with PerformanceOptimizedLogger()")
    print("2. Use debug_lazy() for expensive string formatting")
    print("3. Use is_debug_enabled() to guard expensive operations")
    print("4. Configure environment variables for production optimization")


if __name__ == "__main__":
    demonstrate_performance_improvement()
    show_migration_example()
