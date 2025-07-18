#!/usr/bin/env python3
"""
Test MCP tools directly using the JSON-RPC protocol
"""

import requests
import json
import os
from dotenv import load_dotenv
from clean_mcp_response import clean_mcp_response

load_dotenv()

def call_mcp_tool(method, params=None):
    """Call an MCP tool using JSON-RPC"""
    
    endpoint = "https://prod-1-data.ke.pinecone.io/mcp/assistants/genius"
    api_key = os.getenv('PINECONE_API_KEY')
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream'
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    }
    
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            # Handle streaming response
            if 'text/event-stream' in response.headers.get('content-type', ''):
                # Parse server-sent events
                lines = response.text.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])  # Remove 'data: ' prefix
                            return data
                        except json.JSONDecodeError:
                            continue
            else:
                return response.json()
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error calling MCP tool: {e}")
        return None

def test_mcp_tools():
    """Test available MCP tools"""
    
    print("🧪 Testing MCP Tools")
    print("=" * 40)
    
    # Test 1: List available tools
    print("1. Getting available tools...")
    tools_response = call_mcp_tool("tools/list")
    
    if tools_response:
        print("✅ Available tools:")
        tools = tools_response.get('result', {}).get('tools', [])
        for tool in tools:
            print(f"   - {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
    else:
        print("❌ Failed to get tools list")
        return
    
    # Test 2: Try to get context about Bitcoin
    print("\n2. Testing get_context tool...")
    query_response = call_mcp_tool("tools/call", {
        "name": "get_context",
        "arguments": {
            "query": "What is Bitcoin?",
            "top_k": 5
        }
    })
    
    if query_response:
        print("✅ Query successful!")
        result = query_response.get('result', {})
        
        # Clean the response for better readability
        cleaned_result = clean_mcp_response(result)
        
        print("\n📚 Bitcoin Knowledge Retrieved:")
        print("=" * 60)
        
        if 'content' in cleaned_result:
            for i, item in enumerate(cleaned_result['content'], 1):
                if item.get('type') == 'text':
                    print(f"\n{i}. {item.get('text', '')}")
                    print("-" * 60)
        else:
            print(f"Raw result: {cleaned_result}")
    else:
        print("❌ Query failed")
    
    # Test 3: Get assistant info
    print("\n3. Getting assistant information...")
    info_response = call_mcp_tool("tools/call", {
        "name": "get_assistant_info",
        "arguments": {}
    })
    
    if info_response:
        print("✅ Assistant info retrieved!")
        result = info_response.get('result', {})
        print(f"Info: {result}")
    else:
        print("❌ Failed to get assistant info")

def main():
    print("🔍 MCP Tools Test")
    print("=" * 30)
    
    # First, test basic connection
    print("Testing basic MCP connection...")
    init_response = call_mcp_tool("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "bitcoin-knowledge-test",
            "version": "1.0.0"
        }
    })
    
    if init_response:
        print("✅ MCP connection successful!")
        print(f"Server: {init_response.get('result', {}).get('serverInfo', {})}")
        
        # Test the tools
        test_mcp_tools()
    else:
        print("❌ MCP connection failed")

if __name__ == "__main__":
    main()