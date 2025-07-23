#!/usr/bin/env python3
"""
Test script to verify Pinecone Assistant MCP connection
"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()


def send_jsonrpc_request(endpoint, api_key, method, params=None, request_id=1):
    """Helper function to send JSON-RPC requests"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
    }

    if params is not None:
        payload["params"] = params

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return None


def test_missing_api_key():
    """Test that the endpoint fails when API key is missing"""
    from unittest.mock import patch

    import pytest

    with patch.dict("os.environ", {"PINECONE_API_KEY": ""}):
        # Import inside test to ensure environment is properly mocked
        from tests.test_mcp_connection import (
            test_pinecone_assistant_endpoint as real_test,
        )

        with pytest.raises(
            pytest.fail.Exception,
            match="PINECONE_API_KEY environment variable is not set",
        ):
            real_test()


def test_pinecone_assistant_endpoint():
    """Test the Pinecone Assistant MCP endpoint using JSON-RPC protocol"""
    import pytest

    endpoint = os.getenv(
        "PINECONE_MCP_ENDPOINT",
        "https://prod-1-data.ke.pinecone.io/mcp/assistants/genius",
    )

    # Get and validate API key
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key or not api_key.strip():
        pytest.fail(
            "PINECONE_API_KEY environment variable is not set or is empty. "
            "Please set it before running this test.\n"
            "Example:\n"
            "  export PINECONE_API_KEY='your-api-key-here'\n"
            "Or when running tests:\n"
            "  PINECONE_API_KEY='your-api-key-here' python -m pytest tests/test_mcp_connection.py"
        )

    print("🧪 Testing Pinecone Assistant MCP Endpoint")
    print("=" * 50)
    print(f"Endpoint: {endpoint}")
    print(f"API Key: {api_key[:10]}...")

    # Test 1: Initialize connection
    print("\n1. Testing MCP initialization...")
    init_params = {
        "protocolVersion": "2024-11-05",
        "capabilities": {"textDocument": {"completion": {"dynamicRegistration": True}}},
        "clientInfo": {"name": "bitcoin-knowledge-test", "version": "1.0.0"},
    }

    init_response = send_jsonrpc_request(endpoint, api_key, "initialize", init_params)
    if not init_response:
        print("❌ Failed to initialize MCP connection")
        return False

    if "error" in init_response:
        print(f"❌ MCP initialization failed: {init_response['error']}")
        return False

    print("✅ MCP initialization successful")

    # Extract server capabilities for further testing
    server_capabilities = init_response.get("result", {}).get("capabilities", {})
    print(f"Server capabilities: {json.dumps(server_capabilities, indent=2)}")

    # Test 2: Test basic completion
    print("\n2. Testing basic completion...")
    completion_params = {
        "textDocument": {
            "uri": "test.py",
            "languageId": "python",
            "text": "def test_function():",
        },
        "position": {"line": 0, "character": 18},
    }

    completion_response = send_jsonrpc_request(
        endpoint, api_key, "textDocument/completion", completion_params, 2
    )

    if not completion_response:
        print("❌ Completion request failed")
    elif "error" in completion_response:
        print(f"❌ Completion error: {completion_response['error']}")
    else:
        print("✅ Completion request successful")

    # Test 3: Test shutdown
    print("\n3. Testing graceful shutdown...")
    shutdown_response = send_jsonrpc_request(endpoint, api_key, "shutdown", None, 3)

    if not shutdown_response:
        print("❌ Shutdown request failed")
    elif "error" in shutdown_response:
        print(f"❌ Shutdown error: {shutdown_response['error']}")
    else:
        print("✅ Shutdown request successful")

    # Always try to exit cleanly
    _ = send_jsonrpc_request(endpoint, api_key, "exit", None, 4)

    return True


def main():
    print("🔍 Pinecone Assistant MCP Connection Test")
    print("=" * 50)

    # Test the endpoint
    success = test_pinecone_assistant_endpoint()

    if success:
        print("\n✅ MCP endpoint is accessible!")
        print("\n📋 Next steps:")
        print("1. The MCP server should now work in Kiro IDE")
        print("2. You can proceed with setting up your Bitcoin knowledge base")
        print("3. Use the MCP tools to interact with your assistant")
    else:
        print("\n❌ MCP endpoint test failed")
        print("\n🔧 Troubleshooting:")
        print("1. Verify your API key is correct")
        print("2. Check if the endpoint URL is accessible")
        print("3. Ensure you have proper permissions for the assistant")


if __name__ == "__main__":
    main()
