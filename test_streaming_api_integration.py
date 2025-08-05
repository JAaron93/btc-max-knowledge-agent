#!/usr/bin/env python3
"""
Integration test for streaming API endpoints.
"""

import json
import os
import sys
from pathlib import Path

import requests

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def test_api_connection():
    """Test basic API connection."""
    print("🧪 Testing API connection...")

    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API connected: {data.get('message')}")

            # Check for streaming endpoints
            endpoints = data.get("endpoints", [])
            streaming_endpoints = [ep for ep in endpoints if "streaming" in ep]
            print(f"📡 Streaming endpoints available: {streaming_endpoints}")

            return True
        else:
            print(f"❌ API connection failed: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print(
            "❌ Cannot connect to API. Make sure the FastAPI server is running on port 8000."
        )
        return False
    except Exception as e:
        print(f"❌ API connection test failed: {e}")
        return False


def test_streaming_status_endpoint():
    """Test streaming status endpoint."""
    print("\n🧪 Testing streaming status endpoint...")

    try:
        response = requests.get(f"{API_BASE_URL}/tts/streaming/status", timeout=10)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Streaming status retrieved:")
            print(f"   TTS enabled: {data.get('tts_enabled')}")

            streaming_info = data.get("streaming_manager", {})
            print(f"   Is streaming: {streaming_info.get('is_streaming')}")
            print(f"   Has current stream: {streaming_info.get('has_current_stream')}")

            return True
        else:
            print(
                f"❌ Streaming status failed: {response.status_code} - {response.text}"
            )
            return False

    except Exception as e:
        print(f"❌ Streaming status test failed: {e}")
        return False


def test_streaming_test_endpoint():
    """Test streaming test endpoint."""
    print("\n🧪 Testing streaming test endpoint...")

    try:
        payload = {
            "text": "This is a test of the streaming functionality.",
            "use_cache": True,
        }

        response = requests.post(
            f"{API_BASE_URL}/tts/streaming/test", json=payload, timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Streaming test successful:")
            print(f"   Message: {data.get('message')}")
            print(f"   Audio available: {data.get('audio_available')}")
            print(f"   Cached: {data.get('cached')}")

            streaming_data = data.get("streaming_data", {})
            streaming_data = data.get("streaming_data", {})
            if streaming_data:
                duration = streaming_data.get("duration")
                if duration is not None:
                    print(f"   Duration: {duration:.2f}s")
                size_bytes = streaming_data.get("size_bytes")
                if size_bytes is not None:
                    print(f"   Size: {size_bytes} bytes")
                print(f"   Instant replay: {streaming_data.get('instant_replay')}")
                synthesis_time = streaming_data.get("synthesis_time")
                if synthesis_time is not None:
                    print(f"   Synthesis time: {synthesis_time:.2f}s")

            return True
        elif response.status_code == 503:
            print(
                "⚠️  TTS service not enabled (likely missing API key), skipping streaming test"
            )
            return True
        else:
            print(f"❌ Streaming test failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"❌ Streaming test endpoint failed: {e}")
        return False


def test_query_with_streaming():
    """Test query endpoint with streaming TTS."""
    print("\n🧪 Testing query with streaming TTS...")

    try:
        payload = {"question": "What is Bitcoin?", "enable_tts": True}

        response = requests.post(f"{API_BASE_URL}/query", json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Query with streaming successful:")
            print(f"   Answer length: {len(data.get('answer', ''))}")
            print(f"   TTS enabled: {data.get('tts_enabled')}")
            print(f"   TTS cached: {data.get('tts_cached')}")
            print(f"   Synthesis time: {data.get('tts_synthesis_time')}")

            # Check for streaming data
            streaming_data = data.get("audio_streaming_data")
            if streaming_data:
                print(f"   Streaming data available: ✅")
                print(f"   Instant replay: {streaming_data.get('instant_replay')}")
                print(f"   Duration: {streaming_data.get('duration')}")
            else:
                print(f"   Streaming data available: ❌")

            # Check for audio data
            audio_data = data.get("audio_data")
            if audio_data:
                print(f"   Audio data available: ✅ ({len(audio_data)} chars)")
            else:
                print(f"   Audio data available: ❌")

            return True
        else:
            print(
                f"❌ Query with streaming failed: {response.status_code} - {response.text}"
            )
            return False

    except Exception as e:
        print(f"❌ Query with streaming test failed: {e}")
        return False


def main():
    """Run all integration tests."""
    print("🚀 Starting streaming API integration tests...\n")

    tests = [
        ("API Connection", test_api_connection),
        ("Streaming Status", test_streaming_status_endpoint),
        ("Streaming Test", test_streaming_test_endpoint),
        ("Query with Streaming", test_query_with_streaming),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print("=" * 60)

        result = test_func()
        results.append((test_name, result))

        if not result and test_name == "API Connection":
            print("\n⚠️  API not available, stopping tests.")
            break

    # Summary
    print(f"\n{'='*60}")
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)

    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("🎉 All streaming API integration tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. Make sure the FastAPI server is running.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
