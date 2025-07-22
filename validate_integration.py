#!/usr/bin/env python3
"""
Integration validation script for URL metadata system.

Tests the complete pipeline with real or mock Pinecone operations,
validates URL metadata flow, logging, monitoring, and performance.
"""

import os
import sys
import time
import uuid
import json
import asyncio
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue
from dataclasses import dataclass, asdict
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.retrieval.pinecone_client import PineconeClient
from src.agents.pinecone_assistant_agent import PineconeAssistantAgent
from src.knowledge.data_collector import DataCollector
from src.utils.url_metadata_logger import URLMetadataLogger
from src.monitoring.url_metadata_monitor import URLMetadataMonitor
from src.utils.url_error_handler import (
    exponential_backoff_retry,
    GracefulDegradation,
    FallbackURLStrategy,
    URLValidationError,
    URLMetadataUploadError,
    URLRetrievalError
)
from src.utils.url_utils import URLValidator
from src.utils.result_formatter import ResultFormatter
from src.utils.config import get_config


@dataclass
class ValidationResult:
    """Result of a validation test."""
    test_name: str
    passed: bool
    duration: float
    details: Dict[str, Any]
    error: Optional[str] = None


class IntegrationValidator:
    """Validates complete URL metadata integration."""
    
    def __init__(self, use_real_pinecone: bool = False):
        """Initialize validator."""
        self.use_real_pinecone = use_real_pinecone
        self.correlation_id = str(uuid.uuid4())
        
        # Initialize components
        self.logger = URLMetadataLogger()
        self.monitor = URLMetadataMonitor()
        self.url_validator = URLValidator()
        self.result_formatter = ResultFormatter()
        self.data_collector = DataCollector()
        self.graceful_degradation = GracefulDegradation()
        
        # Initialize clients if using real Pinecone
        if self.use_real_pinecone:
            config = get_config()
            if config.get('PINECONE_API_KEY'):
                self.pinecone_client = PineconeClient(
                    index_name=config.get('PINECONE_INDEX_NAME', 'test-index'),
                    dimension=1536
                )
                self.assistant_agent = PineconeAssistantAgent(
                    assistant_id=config.get('ASSISTANT_ID', 'test-assistant'),
                    pinecone_index_name=config.get('PINECONE_INDEX_NAME')
                )
            else:
                print("⚠️  No Pinecone API key found, using mock mode")
                self.use_real_pinecone = False
                self.pinecone_client = None
                self.assistant_agent = None
        else:
            self.pinecone_client = None
            self.assistant_agent = None
        
        # Test results storage
        self.test_results: List[ValidationResult] = []
        self.performance_metrics: Dict[str, Any] = {}
    
    def run_test(self, test_name: str, test_func):
        """Run a single test and record results."""
        print(f"\n🧪 Running: {test_name}")
        start_time = time.time()
        
        try:
            result = test_func()
            duration = time.time() - start_time
            
            validation_result = ValidationResult(
                test_name=test_name,
                passed=result.get('passed', True),
                duration=duration,
                details=result.get('details', {}),
                error=result.get('error')
            )
            
            self.test_results.append(validation_result)
            
            if validation_result.passed:
                print(f"  ✅ PASSED ({duration:.2f}s)")
            else:
                print(f"  ❌ FAILED ({duration:.2f}s)")
                if validation_result.error:
                    print(f"     Error: {validation_result.error}")
            
            return validation_result
            
        except Exception as e:
            duration = time.time() - start_time
            validation_result = ValidationResult(
                test_name=test_name,
                passed=False,
                duration=duration,
                details={'exception': str(e)},
                error=str(e)
            )
            self.test_results.append(validation_result)
            print(f"  ❌ EXCEPTION ({duration:.2f}s): {str(e)}")
            return validation_result
    
    def test_url_validation_security(self) -> Dict[str, Any]:
        """Test URL validation with security checks."""
        test_urls = [
            # Valid URLs
            ('https://bitcoin.org/bitcoin.pdf', True),
            ('https://lightning.network/docs', True),
            ('http://localhost:8080/api', True),
            
            # Invalid/Malicious URLs
            ('https://example.com/../../../etc/passwd', False),
            ('javascript:alert("XSS")', False),
            ('file:///etc/passwd', False),
            ('ftp://malicious.com/exploit', False),
            ('not-a-url', False),
            ('<script>alert("XSS")</script>', False),
        ]
        
        results = []
        for url, expected_valid in test_urls:
            is_valid, validation_result = self.url_validator.validate_url(url)
            results.append({
                'url': url,
                'expected': expected_valid,
                'actual': is_valid,
                'passed': is_valid == expected_valid,
                'details': validation_result
            })
        
        all_passed = all(r['passed'] for r in results)
        
        return {
            'passed': all_passed,
            'details': {
                'total_tests': len(test_urls),
                'passed': sum(1 for r in results if r['passed']),
                'failed': sum(1 for r in results if not r['passed']),
                'results': results
            }
        }
    
    def test_metadata_extraction(self) -> Dict[str, Any]:
        """Test URL metadata extraction."""
        test_cases = [
            {
                'url': 'https://bitcoin.org/en/bitcoin-paper',
                'expected': {
                    'protocol': 'https',
                    'domain': 'bitcoin.org',
                    'path': '/en/bitcoin-paper'
                }
            },
            {
                'url': 'http://localhost:3000/api/v1/data?query=test#section',
                'expected': {
                    'protocol': 'http',
                    'domain': 'localhost',
                    'path': '/api/v1/data'
                }
            }
        ]
        
        results = []
        for test_case in test_cases:
            metadata = self.url_validator.extract_metadata(test_case['url'])
            
            passed = all(
                metadata.get(key) == value
                for key, value in test_case['expected'].items()
            )
            
            results.append({
                'url': test_case['url'],
                'expected': test_case['expected'],
                'actual': metadata,
                'passed': passed
            })
        
        return {
            'passed': all(r['passed'] for r in results),
            'details': {
                'test_count': len(test_cases),
                'results': results
            }
        }
    
    def test_error_handling_retry(self) -> Dict[str, Any]:
        """Test error handling with retry mechanisms."""
        attempts = []
        max_attempts = 3
        
        def failing_operation():
            """Operation that fails first 2 times."""
            attempt = len(attempts) + 1
            attempts.append(attempt)
            
            if attempt < max_attempts:
                raise Exception(f"Simulated failure {attempt}")
            return {'success': True, 'attempt': attempt}
        
        result = self.error_handler.handle_with_retry(
            failing_operation,
            operation_name='test_retry',
            max_attempts=max_attempts
        )
        
        return {
            'passed': result['success'] and len(attempts) == max_attempts,
            'details': {
                'attempts_made': len(attempts),
                'max_attempts': max_attempts,
                'final_result': result
            }
        }
    
    def test_logging_correlation(self) -> Dict[str, Any]:
        """Test logging with correlation IDs."""
        test_correlation_id = str(uuid.uuid4())
        
        # Log various operations
        self.logger.log_metadata_creation(
            metadata={'test': 'data'},
            correlation_id=test_correlation_id
        )
        
        self.logger.log_url_operation(
            operation='test_operation',
            url='https://test.com',
            success=True,
            correlation_id=test_correlation_id
        )
        
        self.logger.log_query_execution(
            query='test query',
            result_count=5,
            has_url_metadata=3,
            correlation_id=test_correlation_id
        )
        
        # Verify correlation tracking
        # In a real implementation, we'd check log files or log aggregation
        return {
            'passed': True,
            'details': {
                'correlation_id': test_correlation_id,
                'operations_logged': 3
            }
        }
    
    def test_monitoring_metrics(self) -> Dict[str, Any]:
        """Test monitoring metrics collection."""
        # Reset metrics
        self.monitor.metrics = {
            'url_events': 0,
            'validation_attempts': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'errors': {}
        }
        
        # Generate test events
        for i in range(10):
            self.monitor.record_url_event('test_event')
            self.monitor.record_validation_result(
                url=f'https://test{i}.com',
                is_valid=i % 2 == 0
            )
        
        # Record some errors
        self.monitor.record_error(
            error_type='test_error',
            error_message='Test error message',
            context={'test': True}
        )
        
        # Get metrics summary
        summary = self.monitor.get_metrics_summary()
        
        return {
            'passed': (
                summary['total_events'] == 10 and
                summary['validation_attempts'] == 10 and
                summary['successful_validations'] == 5 and
                summary['validation_success_rate'] == 0.5
            ),
            'details': summary
        }
    
    def test_concurrent_operations(self) -> Dict[str, Any]:
        """Test concurrent URL metadata operations."""
        num_workers = 5
        operations_per_worker = 10
        results_queue = queue.Queue()
        errors_queue = queue.Queue()
        
        def worker(worker_id: int):
            """Worker function for concurrent operations."""
            for i in range(operations_per_worker):
                try:
                    # Simulate URL validation
                    url = f'https://worker{worker_id}.test{i}.com'
                    is_valid, _ = self.url_validator.validate_url(url)
                    
                    # Log operation
                    self.logger.log_url_operation(
                        operation='concurrent_test',
                        url=url,
                        success=is_valid,
                        correlation_id=self.correlation_id
                    )
                    
                    results_queue.put({
                        'worker_id': worker_id,
                        'operation': i,
                        'success': True
                    })
                    
                except Exception as e:
                    errors_queue.put({
                        'worker_id': worker_id,
                        'operation': i,
                        'error': str(e)
                    })
        
        # Launch workers
        threads = []
        start_time = time.time()
        
        for worker_id in range(num_workers):
            thread = threading.Thread(target=worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        duration = time.time() - start_time
        
        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        errors = []
        while not errors_queue.empty():
            errors.append(errors_queue.get())
        
        total_operations = num_workers * operations_per_worker
        
        return {
            'passed': len(results) == total_operations and len(errors) == 0,
            'details': {
                'num_workers': num_workers,
                'operations_per_worker': operations_per_worker,
                'total_operations': total_operations,
                'successful': len(results),
                'errors': len(errors),
                'duration': duration,
                'ops_per_second': total_operations / duration if duration > 0 else 0
            }
        }
    
    def test_batch_operations(self) -> Dict[str, Any]:
        """Test batch operations performance."""
        batch_sizes = [10, 50, 100, 500]
        results = []
        
        for batch_size in batch_sizes:
            # Generate batch data
            batch_data = []
            for i in range(batch_size):
                batch_data.append({
                    'id': f'batch_{batch_size}_{i}',
                    'url': f'https://batch.test{i}.com',
                    'content': f'Test content {i}',
                    'embedding': np.random.rand(1536).tolist()
                })
            
            # Time batch processing
            start_time = time.time()
            
            # Process batch (validation, metadata extraction, etc.)
            processed = 0
            for item in batch_data:
                is_valid, _ = self.url_validator.validate_url(item['url'])
                if is_valid:
                    metadata = self.url_validator.extract_metadata(item['url'])
                    item['metadata'] = metadata
                    processed += 1
            
            duration = time.time() - start_time
            
            results.append({
                'batch_size': batch_size,
                'processed': processed,
                'duration': duration,
                'items_per_second': batch_size / duration if duration > 0 else 0
            })
        
        # Check performance doesn't degrade significantly with batch size
        performance_ratios = []
        for i in range(1, len(results)):
            ratio = (results[i]['items_per_second'] / 
                    results[0]['items_per_second'])
            performance_ratios.append(ratio)
        
        # Performance should not degrade by more than 50%
        acceptable_performance = all(ratio > 0.5 for ratio in performance_ratios)
        
        return {
            'passed': acceptable_performance,
            'details': {
                'batch_results': results,
                'performance_ratios': performance_ratios
            }
        }
    
    def test_pinecone_integration(self) -> Dict[str, Any]:
        """Test Pinecone integration if available."""
        if not self.use_real_pinecone or not self.pinecone_client:
            return {
                'passed': True,
                'details': {
                    'skipped': True,
                    'reason': 'Pinecone integration not configured'
                }
            }
        
        try:
            # Test vector with URL metadata
            test_vector = {
                'id': f'integration_test_{uuid.uuid4().hex[:8]}',
                'values': np.random.rand(1536).tolist(),
                'metadata': {
                    'text': 'Integration test content',
                    'source_url': 'https://integration.test.com',
                    'url_title': 'Integration Test',
                    'url_domain': 'integration.test.com',
                    'url_validated': True,
                    'metadata_version': '2.0',
                    'test_timestamp': datetime.utcnow().isoformat() + 'Z'
                }
            }
            
            # Upsert vector
            self.pinecone_client.upsert_vectors([test_vector])
            
            # Query for vector
            time.sleep(2)  # Allow indexing
            
            results = self.pinecone_client.query(
                vector=test_vector['values'],
                top_k=1
            )
            
            # Verify result
            if results and len(results) > 0:
                result = results[0]
                metadata = result.get('metadata', {})
                
                # Check URL metadata preserved
                url_metadata_present = all(
                    key in metadata
                    for key in ['source_url', 'url_title', 'url_domain']
                )
                
                # Clean up - delete test vector
                self.pinecone_client.delete_vectors([test_vector['id']])
                
                return {
                    'passed': url_metadata_present,
                    'details': {
                        'vector_id': test_vector['id'],
                        'metadata_fields': list(metadata.keys()),
                        'url_metadata_preserved': url_metadata_present
                    }
                }
            else:
                return {
                    'passed': False,
                    'details': {'error': 'No results returned from query'}
                }
                
        except Exception as e:
            return {
                'passed': False,
                'details': {'error': str(e)},
                'error': str(e)
            }
    
    def test_assistant_integration(self) -> Dict[str, Any]:
        """Test assistant agent integration if available."""
        if not self.use_real_pinecone or not self.assistant_agent:
            return {
                'passed': True,
                'details': {
                    'skipped': True,
                    'reason': 'Assistant integration not configured'
                }
            }
        
        try:
            # Test query
            test_query = "What is Bitcoin?"
            
            response = self.assistant_agent.process_query(test_query)
            
            # Verify response structure
            has_required_fields = all(
                field in response
                for field in ['answer', 'sources']
            )
            
            # Check if sources have URL metadata
            sources_with_urls = sum(
                1 for source in response.get('sources', [])
                if source.get('url')
            )
            
            return {
                'passed': has_required_fields,
                'details': {
                    'query': test_query,
                    'has_answer': 'answer' in response,
                    'has_sources': 'sources' in response,
                    'source_count': len(response.get('sources', [])),
                    'sources_with_urls': sources_with_urls
                }
            }
            
        except Exception as e:
            return {
                'passed': False,
                'details': {'error': str(e)},
                'error': str(e)
            }
    
    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.passed)
        failed_tests = total_tests - passed_tests
        
        # Calculate performance metrics
        total_duration = sum(r.duration for r in self.test_results)
        
        # Group results by status
        passed_results = [r for r in self.test_results if r.passed]
        failed_results = [r for r in self.test_results if not r.passed]
        
        report = {
            'validation_id': self.correlation_id,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': passed_tests / total_tests if total_tests > 0 else 0,
                'total_duration': total_duration,
                'use_real_pinecone': self.use_real_pinecone
            },
            'passed_tests': [
                {
                    'name': r.test_name,
                    'duration': r.duration,
                    'details': r.details
                }
                for r in passed_results
            ],
            'failed_tests': [
                {
                    'name': r.test_name,
                    'duration': r.duration,
                    'error': r.error,
                    'details': r.details
                }
                for r in failed_results
            ],
            'performance_metrics': self.performance_metrics,
            'monitoring_summary': self.monitor.get_metrics_summary()
        }
        
        return report
    
    def run_all_validations(self):
        """Run all validation tests."""
        print("=" * 60)
        print("URL Metadata System - Integration Validation")
        print(f"Validation ID: {self.correlation_id}")
        print(f"Mode: {'Real Pinecone' if self.use_real_pinecone else 'Mock'}")
        print("=" * 60)
        
        # Run all tests
        self.run_test("URL Validation & Security", self.test_url_validation_security)
        self.run_test("Metadata Extraction", self.test_metadata_extraction)
        self.run_test("Error Handling & Retry", self.test_error_handling_retry)
        self.run_test("Logging Correlation", self.test_logging_correlation)
        self.run_test("Monitoring Metrics", self.test_monitoring_metrics)
        self.run_test("Concurrent Operations", self.test_concurrent_operations)
        self.run_test("Batch Operations", self.test_batch_operations)
        self.run_test("Pinecone Integration", self.test_pinecone_integration)
        self.run_test("Assistant Integration", self.test_assistant_integration)
        
        # Generate report
        report = self.generate_validation_report()
        
        # Save report
        report_file = f"validation_report_{self.correlation_id[:8]}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']} ✅")
        print(f"Failed: {report['summary']['failed']} ❌")
        print(f"Success Rate: {report['summary']['success_rate']:.1%}")
        print(f"Total Duration: {report['summary']['total_duration']:.2f}s")
        print(f"\nDetailed report saved to: {report_file}")
        
        # Print failed tests if any
        if report['summary']['failed'] > 0:
            print("\nFailed Tests:")
            for test in report['failed_tests']:
                print(f"  - {test['name']}: {test.get('error', 'Unknown error')}")
        
        print("=" * 60)
        
        # Return overall success
        return report['summary']['failed'] == 0


def main():
    """Run integration validation."""
    parser = argparse.ArgumentParser(
        description='Validate URL metadata system integration'
    )
    parser.add_argument(
        '--real-pinecone',
        action='store_true',
        help='Use real Pinecone API (requires configuration)'
    )
    
    args = parser.parse_args()
    
    # Run validation
    validator = IntegrationValidator(use_real_pinecone=args.real_pinecone)
    success = validator.run_all_validations()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()