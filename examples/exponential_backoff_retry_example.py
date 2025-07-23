#!/usr/bin/env python3
"""
Exponential Backoff Retry Example

This example demonstrates how to use the enhanced exponential backoff retry
functionality that maintains consistency with MAX_QUERY_RETRIES.
"""

import logging
import time
from typing import Any, Dict

import requests

# Import the enhanced retry functionality
from btc_max_knowledge_agent.utils.url_error_handler import (
    MAX_QUERY_RETRIES,
    RetryExhaustedError,
    URLMetadataUploadError,
    exponential_backoff_retry,
    query_retry_with_backoff,
)

# Set up logging to see retry attempts
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Example 1: Using query_retry_with_backoff with default MAX_QUERY_RETRIES
@query_retry_with_backoff(
    exceptions=(requests.RequestException, ConnectionError),
    raise_on_exhaust=False,
    fallback_result=lambda: {"error": "Service unavailable after retries"},
)
def query_external_api(url: str) -> Dict[str, Any]:
    """
    Query an external API with automatic retry using MAX_QUERY_RETRIES.
    This function will retry up to MAX_QUERY_RETRIES times (10 by default).
    """
    logger.info(f"Attempting to query {url}")
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()


# Example 2: Using query_retry_with_backoff with custom parameters
@query_retry_with_backoff(
    max_retries=3,  # Override MAX_QUERY_RETRIES for this specific function
    initial_delay=0.5,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
    exceptions=(requests.RequestException,),
    raise_on_exhaust=True,
)
def query_bitcoin_price_api() -> Dict[str, Any]:
    """
    Query Bitcoin price API with custom retry parameters.
    This function will retry up to 3 times with exponential backoff and jitter.
    """
    logger.info("Querying Bitcoin price API")
    response = requests.get(
        "https://api.coindesk.com/v1/bpi/currentprice.json", timeout=5
    )
    response.raise_for_status()
    return response.json()


# Example 3: Using the original exponential_backoff_retry decorator directly
@exponential_backoff_retry(
    max_retries=5,
    initial_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    exceptions=(URLMetadataUploadError, ConnectionError, TimeoutError),
    raise_on_exhaust=True,
)
def upload_metadata_to_service(metadata: Dict[str, Any]) -> bool:
    """
    Upload metadata with custom exponential backoff configuration.
    This demonstrates direct use of the exponential_backoff_retry decorator.
    """
    logger.info(f"Uploading metadata: {metadata}")

    # Simulate intermittent failures
    import random

    if random.random() < 0.7:  # 70% chance of failure
        raise ConnectionError("Simulated connection failure")

    logger.info("Metadata uploaded successfully")
    return True


# Example 4: Simple retry loop without decorator (for comparison)
def simple_retry_query(url: str, max_attempts: int = None) -> Dict[str, Any]:
    """
    Simple retry loop using MAX_QUERY_RETRIES for comparison.
    This shows how you might implement retry logic without the decorator.
    """
    if max_attempts is None:
        max_attempts = MAX_QUERY_RETRIES

    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Attempt {attempt}/{max_attempts}: Querying {url}")
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            last_error = e
            if attempt < max_attempts:
                # Simple linear backoff (not exponential)
                delay = attempt * 1.0
                logger.warning(
                    f"Attempt {attempt} failed: {e}. Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(f"All {max_attempts} attempts failed")

    # Return error information after all attempts fail
    return {
        "error": f"Failed after {max_attempts} attempts",
        "last_error": str(last_error),
    }


def demonstrate_retry_functionality():
    """Demonstrate various retry patterns."""
    print("🔄 Exponential Backoff Retry Examples")
    print("=" * 50)

    # Example 1: Successful API call with retry wrapper
    print("\n1. Query CoinDesk API (should succeed):")
    try:
        result = query_bitcoin_price_api()
        print("✅ Success: Current Bitcoin price data retrieved")
        print(f"   USD Rate: {result['bpi']['USD']['rate']}")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # Example 2: Query with fallback (will likely fail for demo URL)
    print("\n2. Query with fallback (using MAX_QUERY_RETRIES):")
    result = query_external_api(
        "https://httpstat.us/500"
    )  # This will return 500 errors
    print(f"Result: {result}")

    # Example 3: Upload with simulated failures
    print("\n3. Upload with simulated failures:")
    try:
        success = upload_metadata_to_service(
            {
                "title": "Bitcoin Whitepaper",
                "url": "https://bitcoin.org/bitcoin.pdf",
                "category": "research",
            }
        )
        print(f"✅ Upload succeeded: {success}")
    except RetryExhaustedError as e:
        print(f"❌ Upload failed after all retries: {e}")

    # Example 4: Compare with simple retry loop
    print("\n4. Simple retry loop (for comparison):")
    result = simple_retry_query("https://httpstat.us/503", max_attempts=3)
    print(f"Result: {result}")

    print("\n📊 Configuration Summary:")
    print(f"   MAX_QUERY_RETRIES: {MAX_QUERY_RETRIES}")
    print("   Default initial delay: 1.0s")
    print("   Default max delay: 60.0s")
    print("   Default exponential base: 2.0")
    print("   Jitter enabled by default: Yes")


if __name__ == "__main__":
    demonstrate_retry_functionality()
