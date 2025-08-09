#!/usr/bin/env python3
"""
Test script for the Bitcoin Assistant RAG system
"""

import argparse
import json
import os
import requests
import time
import random


def backoff_sleep(attempt: int, base: float = 0.5, cap: float = 10.0) -> None:
    """
    Exponential backoff with jitter. attempt starts at 1.
    """
    exp = min(cap, base * (2 ** (attempt - 1)))
    jitter = random.uniform(0, exp / 2.0)
    time.sleep(exp + jitter)


def test_rag_system(verbose=False, debug=False):
    """Test the RAG system with the GENIUS act question"""

    # API endpoint - configurable via environment variable
    url = os.getenv("RAG_API_URL", "http://localhost:8000/query")

    # Test question about GENIUS act
    payload = {
        "text": "What is the GENIUS act and why is it such a big deal?",
        "top_k": 5,
    }

    headers = {"Content-Type": "application/json"}

    print("🧪 Testing Bitcoin Assistant RAG System")
    print("=" * 50)
    print(f"🌐 API Endpoint: {url}")
    print(f"📤 Sending question: {payload['text']}")

    if debug:
        print(f"🔧 Debug mode enabled")
        print(f"🔧 Request payload: {json.dumps(payload, indent=2)}")
        print(f"🔧 Request headers: {json.dumps(headers, indent=2)}")

    print("⏳ Processing...")

    start_time = time.time()

    # Make the API request with retry logic
    for attempt in range(1, 5):  # 4 attempts total
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)

            end_time = time.time()
            response_time = end_time - start_time

            print(f"⏱️  Response time: {response_time:.2f} seconds")
            print(f"📊 HTTP Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print("\n✅ RAG System Response:")
                print("-" * 50)

                # Pretty print the full response
                print(json.dumps(result, indent=2))

                # Extract and highlight the main content
                if "result" in result and result["result"]:
                    print("\n📝 Main Answer:")
                    print("=" * 50)
                    for i, item in enumerate(result["result"], 1):
                        print(f"\n[Result {i}]")
                        if isinstance(item, dict):
                            if "text" in item:
                                print(f"Text: {item['text']}")
                            if "score" in item:
                                print(f"Relevance Score: {item['score']}")
                            if "id" in item:
                                print(f"Source ID: {item['id']}")
                        else:
                            print(f"Content: {item}")

                return True
            else:
                # Check if this is a recoverable error that should be retried
                if response.status_code in [429, 500, 502, 503, 504]:
                    # Transient errors - retry
                    if attempt < 4:
                        print(
                            f"⚠️  Transient error {response.status_code} (attempt {attempt}/4)"
                        )
                        print(f"Response: {response.text}")
                        print("🔄 Retrying with exponential backoff...")
                        backoff_sleep(attempt)
                        continue
                    else:
                        print(f"❌ API Error {response.status_code} after 4 attempts")
                        print(f"Response: {response.text}")
                        return False
                else:
                    # Non-recoverable client errors (4xx except 429) - don't retry
                    print(f"❌ Non-recoverable API Error: {response.status_code}")
                    print(f"Response: {response.text}")
                    return False

        except requests.exceptions.RequestException as e:
            if attempt < 4:
                print(f"⚠️  Request failed (attempt {attempt}/4): {e}")
                if verbose:
                    print(f"🔧 Full error details: {repr(e)}")
                print("🔄 Retrying with exponential backoff...")
                backoff_sleep(attempt)
            else:
                print(f"❌ Request failed after 4 attempts: {e}")
                if verbose:
                    print(f"🔧 Final error details: {repr(e)}")
                return False
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            if verbose:
                import traceback

                print(f"🔧 Full traceback:")
                traceback.print_exc()
            return False

    return False


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Test the Bitcoin Assistant RAG system",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output with detailed error information",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug mode to show request details and endpoint info",
    )
    parser.add_argument(
        "--endpoint",
        help="Override the API endpoint URL (can also use RAG_API_URL env var)",
    )

    args = parser.parse_args()

    # Override endpoint if provided via command line
    if args.endpoint:
        os.environ["RAG_API_URL"] = args.endpoint
        print(f"🔧 Using command-line endpoint: {args.endpoint}")

    success = test_rag_system(verbose=args.verbose, debug=args.debug)
    if success:
        print("\n🎉 RAG System test completed successfully!")
    else:
        print("\n💥 RAG System test failed!")


if __name__ == "__main__":
    main()
