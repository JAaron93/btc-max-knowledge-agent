#!/usr/bin/env python3
"""
Complete demonstration of URL metadata system end-to-end workflow.

Shows data collection, validation, error handling, logging, monitoring,
and retrieval with proper source attribution.
"""

import json
import os
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List

# Add src directory to path for btc_max_knowledge_agent imports
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, "src")
sys.path.insert(0, src_dir)

# noqa: E402 (module level import not at top of file)
from btc_max_knowledge_agent.monitoring.url_metadata_monitor import (
    URLMetadataMonitor,
)  # noqa: E402
from btc_max_knowledge_agent.utils.result_formatter import (
    QueryResultFormatter,
)  # noqa: E402
from btc_max_knowledge_agent.utils.url_error_handler import (  # noqa: E402
    FallbackURLStrategy,
    GracefulDegradation,
)
from btc_max_knowledge_agent.utils.url_metadata_logger import (
    URLMetadataLogger,
)  # noqa: E402
from btc_max_knowledge_agent.utils.url_utils import URLValidator  # noqa: E402


class URLMetadataDemo:
    """Demonstrates complete URL metadata workflow."""

    def __init__(self):
        """Initialize demo components."""
        # Initialize monitoring
        self.monitor = URLMetadataMonitor()

        # Initialize logging with correlation ID
        self.correlation_id = str(uuid.uuid4())
        self.logger = URLMetadataLogger()

        # Initialize error handler with graceful degradation
        self.graceful_degradation = GracefulDegradation()
        self.fallback_strategy = FallbackURLStrategy()

        # Initialize URL validator
        self.url_validator = URLValidator()

        # Initialize result formatter
        self.result_formatter = QueryResultFormatter()

        # Track demo metrics
        self.demo_metrics = {
            "start_time": datetime.utcnow(),
            "operations": [],
            "errors": [],
            "successes": [],
        }

    def log_operation(self, operation: str, status: str, details: Dict[str, Any]):
        """Log operation for demo tracking."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "operation": operation,
            "status": status,
            "details": details,
            "correlation_id": self.correlation_id,
        }
        self.demo_metrics["operations"].append(entry)

        if status == "error":
            self.demo_metrics["errors"].append(entry)
        elif status == "success":
            self.demo_metrics["successes"].append(entry)

    def _get_sample_sources(self) -> List[Dict[str, str]]:
        """Generate sample data sources with various URL formats for testing.

        Returns:
            List of sample source dictionaries containing URL, title, and content.
        """
        return [
            {
                "url": "https://bitcoin.org/en/bitcoin-paper",
                "title": "Bitcoin: A Peer-to-Peer Electronic Cash System",
                "content": (
                    "A purely peer-to-peer version of electronic cash "
                    "would allow online payments..."
                ),
            },
            {
                "url": "https://lightning.network/lightning-network-paper.pdf",
                "title": "The Bitcoin Lightning Network",
                "content": (
                    "The Lightning Network is a decentralized system "
                    "for instant, high-volume micropayments..."
                ),
            },
            {
                "url": "https://example.com/../../../etc/passwd",  # Malicious
                "title": "Suspicious Content",
                "content": "This should be blocked by security validation",
            },
            {
                "url": "not-a-valid-url",  # Invalid URL
                "title": "Invalid URL Test",
                "content": "This content has an invalid URL",
            },
            {
                "url": "https://ethereum.org/en/whitepaper/",
                "title": "Ethereum Whitepaper",
                "content": (
                    "Ethereum is a decentralized platform that runs "
                    "smart contracts..."
                ),
            },
        ]

    def _generate_mock_embedding(self) -> List[float]:
        """Generate mock embedding vector using standard library random.

        Returns:
            List of 1536 random float values representing an embedding vector.
        """
        return [random.random() for _ in range(1536)]

    def _process_single_source(self, source: Dict[str, str]) -> Dict[str, Any]:
        """Process a single data source with URL validation and metadata extraction.

        Args:
            source: Dictionary containing url, title, and content

        Returns:
            Processed data entry with metadata or None if validation fails

        Raises:
            Exception: If processing fails completely
        """
        print(f"\nProcessing: {source['url']}")

        # Validate URL with security checks
        self.monitor.record_url_event("validation_attempt")
        is_valid, validation_result = self.url_validator.validate_url(source["url"])

        if not is_valid:
            error_msg = validation_result.get("error", "Unknown error")
            print(f"  ❌ URL validation failed: {error_msg}")
            self.monitor.record_validation_result(
                url=source["url"], is_valid=False, error=validation_result.get("error")
            )
            self.log_operation(
                "url_validation",
                "error",
                {
                    "url": source["url"],
                    "error": validation_result.get("error"),
                    "security_check": validation_result.get("security_check", {}),
                },
            )
            return None

        print("  ✓ URL validated successfully")
        self.monitor.record_validation_result(url=source["url"], is_valid=True)

        # Extract URL metadata with graceful error handling
        try:
            url_metadata = self.url_validator.extract_metadata(source["url"])
        except Exception as e:  # pylint: disable=broad-except
            # Log the error and continue processing
            print(f"  ⚠️  Failed to extract metadata: {e}")
            self.log_operation(
                "metadata_extraction",
                "error",
                {
                    "url": source["url"],
                    "error": str(e),
                },
            )
            # Provide safe defaults so downstream processing continues
            url_metadata = {
                "domain": "",
                "path": "",
                "protocol": "",
            }

        # Create data entry with URL metadata
        data_entry = {
            "id": str(uuid.uuid4()),
            "text": source["content"],
            "metadata": {
                "title": source["title"],
                "source_url": source["url"],
                "url_title": source["title"],
                "url_domain": url_metadata["domain"],
                "url_path": url_metadata["path"],
                "url_protocol": url_metadata["protocol"],
                "url_validated": True,
                "url_validation_timestamp": (datetime.utcnow().isoformat() + "Z"),
                "url_security_score": validation_result.get("security_score", 1.0),
                "metadata_version": "2.0",
                "collection_timestamp": (datetime.utcnow().isoformat() + "Z"),
                "correlation_id": self.correlation_id,
            },
            "embedding": self._generate_mock_embedding(),  # Using random module
        }

        # Log successful collection
        self.logger.log_metadata_creation(
            metadata=data_entry["metadata"], correlation_id=self.correlation_id
        )

        self.log_operation(
            "data_collection",
            "success",
            {
                "url": source["url"],
                "title": source["title"],
                "metadata_fields": list(data_entry["metadata"].keys()),
            },
        )

        num_fields = len(data_entry["metadata"])
        print(f"  ✓ Data collected with {num_fields} metadata fields")

        return data_entry

    def demonstrate_data_collection(self) -> List[Dict[str, Any]]:
        """Demonstrate data collection with URL metadata."""
        print("\n=== Data Collection Phase ===")

        sample_sources = self._get_sample_sources()
        collected_data = []

        for source in sample_sources:
            try:
                # Process individual source
                data_entry = self._process_single_source(source)

                if data_entry:
                    collected_data.append(data_entry)

            except Exception as e:
                print(f"  ❌ Error processing source: {str(e)}")
                self.monitor.record_error(
                    error_type="data_collection_error",
                    error_message=str(e),
                    context={"url": source["url"]},
                )

                # Handle with graceful degradation
                fallback_result = self.graceful_degradation.degrade_safely(
                    lambda: self._process_source_with_fallback(source),
                    fallback_value=None,
                    operation_name="data_collection",
                )

                if fallback_result:
                    collected_data.append(fallback_result)

        print(f"\n✓ Collected {len(collected_data)} valid data entries")
        return collected_data

    def _process_source_with_fallback(self, source: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback processing for failed sources."""
        # Create minimal entry without URL validation
        return {
            "id": str(uuid.uuid4()),
            "text": source["content"],
            "metadata": {
                "title": source["title"],
                "source_url": source.get("url", "unknown"),
                "url_validated": False,
                "fallback_processing": True,
                "metadata_version": "2.0",
                "collection_timestamp": datetime.utcnow().isoformat() + "Z",
            },
            "embedding": self._generate_mock_embedding(),
        }

    def demonstrate_concurrent_operations(
        self, data: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Demonstrate concurrent operations with URL metadata."""
        print("\n=== Concurrent Operations Phase ===")

        def process_data_item(item: Dict[str, Any]) -> Dict[str, str]:
            """Process individual data item."""
            try:
                # Simulate processing with URL metadata
                time.sleep(0.1)  # Simulate work

                # Log concurrent operation
                self.logger.log_url_operation(
                    operation="concurrent_processing",
                    url=item["metadata"].get("source_url", "unknown"),
                    success=True,
                    correlation_id=self.correlation_id,
                )

                return {
                    "id": item["id"],
                    "status": "processed",
                    "url": item["metadata"].get("source_url", "unknown"),
                }

            except Exception as e:
                return {"id": item["id"], "status": "failed", "error": str(e)}

        # Process items concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(process_data_item, item): item for item in data}

            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                status_icon = "✓" if result["status"] == "processed" else "❌"
                print(f"  {status_icon} Processed item {result['id'][:8]}...")

        print(f"\n✓ Processed {len(results)} items concurrently")
        return results

    def _create_mock_results(self) -> List[Dict[str, Any]]:
        """Create mock retrieval results for demonstration purposes.

        Returns:
            List of mock result dictionaries
        """
        return [
            {
                "id": "result_1",
                "score": 0.95,
                "metadata": {
                    "text": ("The Lightning Network is a second-layer " "solution..."),
                    "source_url": "https://lightning.network/docs",
                    "url_title": "Lightning Network Documentation",
                    "url_domain": "lightning.network",
                    "url_validated": True,
                    "metadata_version": "2.0",
                },
            },
            {
                "id": "result_2",
                "score": 0.89,
                "metadata": {
                    "text": ("Lightning enables instant Bitcoin " "transactions..."),
                    "source_url": "https://bitcoin.org/lightning",
                    "url_title": "Bitcoin Lightning Guide",
                    "url_domain": "bitcoin.org",
                    "url_validated": True,
                    "metadata_version": "2.0",
                },
            },
            {
                "id": "legacy_result",
                "score": 0.85,
                "metadata": {
                    "text": ("Payment channels allow off-chain " "transactions..."),
                    "timestamp": "2023-01-01T00:00:00Z",
                    # No URL metadata (legacy format)
                },
            },
        ]

    def _display_formatted_response(self, formatted_response: Dict[str, Any]) -> None:
        """Display the formatted response with sources.

        Args:
            formatted_response: The formatted response dictionary with answer and sources
        """
        print("\n--- Formatted Response ---")
        print(f"Answer: {formatted_response['answer'][:100]}...")
        print(f"\nSources ({len(formatted_response['sources'])}):")

        for i, source in enumerate(formatted_response["sources"], 1):
            print(f"\n  [{i}] {source.get('title', 'Unknown Source')}")
            if source.get("url"):
                print(f"      URL: {source['url']}")
                print(f"      Domain: {source.get('domain', 'N/A')}")
                validated = "✓" if source.get("validated") else "✗"
                print(f"      Validated: {validated}")
            else:
                print("      URL: No URL metadata (legacy content)")
            relevance = source.get("relevance_score", 0)
            print(f"      Relevance: {relevance:.0%}")

    def demonstrate_query_and_retrieval(self, mock_mode: bool = True) -> Dict[str, Any]:
        """Demonstrate query and retrieval with source attribution."""
        print("\n=== Query and Retrieval Phase ===")

        # Sample query
        query = "What is the Bitcoin Lightning Network?"
        print(f"\nQuery: {query}")

        if mock_mode:
            # Mock retrieval results
            mock_results = self._create_mock_results()

            # Format results with source attribution
            formatted_response = self.result_formatter.format_response(
                query=query,
                results=mock_results,
                model_answer=(
                    "The Lightning Network is a Layer 2 scaling "
                    "solution for Bitcoin..."
                ),
            )

            # Display formatted results
            self._display_formatted_response(formatted_response)

            # Log query operation
            self.logger.log_query_execution(
                query=query,
                result_count=len(mock_results),
                has_url_metadata=sum(
                    1 for r in mock_results if "source_url" in r.get("metadata", {})
                ),
                correlation_id=self.correlation_id,
            )

            return formatted_response

        else:
            # Real Pinecone query (requires setup)
            print("  ℹ️  Real query mode requires Pinecone setup")
            return {
                "query": query,
                "answer": "Real query mode not implemented",
                "sources": [],
                "error": "Pinecone setup required",
            }

    def demonstrate_monitoring_and_metrics(self):
        """Demonstrate monitoring and metrics collection."""
        print("\n=== Monitoring and Metrics Phase ===")

        # Get current metrics
        metrics = self.monitor.get_metrics_summary()

        print("\nURL Metadata System Metrics:")
        print(f"  • Total URL Events: {metrics['total_events']}")
        print(f"  • Validation Attempts: {metrics['validation_attempts']}")
        success_count = metrics["successful_validations"]
        print(f"  • Successful Validations: {success_count}")
        success_rate = metrics["validation_success_rate"]
        print(f"  • Validation Success Rate: {success_rate:.1%}")
        print(f"  • Total Errors: {metrics['total_errors']}")

        if metrics["error_breakdown"]:
            print("\n  Error Breakdown:")
            for error_type, count in metrics["error_breakdown"].items():
                print(f"    - {error_type}: {count}")

        # Demo-specific metrics
        duration = (datetime.utcnow() - self.demo_metrics["start_time"]).total_seconds()
        print("\nDemo Execution Metrics:")
        print(f"  • Duration: {duration:.2f} seconds")
        print(f"  • Total Operations: {len(self.demo_metrics['operations'])}")
        success_ops = len(self.demo_metrics["successes"])
        print(f"  • Successful Operations: {success_ops}")
        print(f"  • Failed Operations: {len(self.demo_metrics['errors'])}")

        # Generate detailed report
        report = self.monitor.generate_detailed_report()

        # Save metrics to file
        metrics_file = f"demo_metrics_{self.correlation_id[:8]}.json"
        try:
            with open(metrics_file, "w") as f:
                json.dump(
                    {
                        "correlation_id": self.correlation_id,
                        "system_metrics": metrics,
                        "demo_metrics": self.demo_metrics,
                        "detailed_report": report,
                    },
                    f,
                    indent=2,
                    default=str,
                )
            print(f"\n✓ Metrics saved to {metrics_file}")
        except IOError as e:
            print(f"\n⚠️  Failed to save metrics: {str(e)}")

    def run_complete_demo(self):
        """Run the complete URL metadata demonstration."""
        print("=" * 60)
        print("URL Metadata System - Complete Demonstration")
        print(f"Correlation ID: {self.correlation_id}")
        print("=" * 60)

        try:
            # Phase 1: Data Collection
            collected_data = self.demonstrate_data_collection()

            # Phase 2: Concurrent Operations
            if collected_data:
                self.demonstrate_concurrent_operations(collected_data)

            # Phase 3: Query and Retrieval
            self.demonstrate_query_and_retrieval(mock_mode=True)

            # Phase 4: Monitoring and Metrics
            self.demonstrate_monitoring_and_metrics()

            print("\n" + "=" * 60)
            print("✓ Demo completed successfully!")
            print("=" * 60)

            # Return summary
            return {
                "success": True,
                "correlation_id": self.correlation_id,
                "data_collected": len(collected_data),
                "errors_encountered": len(self.demo_metrics["errors"]),
                "metrics_file": f"demo_metrics_{self.correlation_id[:8]}.json",
            }

        except Exception as e:
            print(f"\n❌ Demo failed: {str(e)}")
            self.logger.log_critical_error(
                error=e,
                context={"phase": "demo_execution"},
                correlation_id=self.correlation_id,
            )
            return {
                "success": False,
                "error": str(e),
                "correlation_id": self.correlation_id,
            }


def main():
    """Run the URL metadata demonstration."""
    demo = URLMetadataDemo()
    result = demo.run_complete_demo()

    # Print final summary
    print("\n" + "=" * 60)
    print("Demo Summary:")
    print(f"  • Status: {'✓ Success' if result['success'] else '❌ Failed'}")
    print(f"  • Correlation ID: {result['correlation_id']}")

    if result["success"]:
        print(f"  • Data Collected: {result['data_collected']}")
        print(f"  • Errors Encountered: {result['errors_encountered']}")
        print(f"  • Metrics File: {result['metrics_file']}")
    else:
        print(f"  • Error: {result.get('error', 'Unknown error')}")

    print("=" * 60)


if __name__ == "__main__":
    main()
