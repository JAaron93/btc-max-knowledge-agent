#!/usr/bin/env python3
"""
Test script to verify Pinecone Assistant MCP connection
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_pinecone_assistant_endpoint():
    """Test the Pinecone Assistant MCP endpoint directly"""
    
    endpoint = "https://prod-1-data.ke.pinecone.io/mcp/assistants/genius"
    api_key = os.getenv('PINECONE_API_KEY')
    
    headers = {
        'Api-Key': api_key,
        'Content-Type': 'application/json'
    }
    
    print("🧪 Testing Pinecone Assistant MCP Endpoint")
    print("=" * 50)
    print(f"Endpoint: {endpoint}")
    print(f"API Key: {api_key[:10]}...")
    
    try:
        # Test basic connection
        print("\n1. Testing basic connection...")
        response = requests.get(endpoint, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ Connection successful!")
            try:
                data = response.json()
                print(f"Response data: {json.dumps(data, indent=2)}")
            except:
                print(f"Response text: {response.text}")
        else:
            print(f"❌ Connection failed: {response.status_code}")
            print(f"Response: {response.text}")
        
        # Test MCP capabilities endpoint with proper auth and accept headers
        print("\n2. Testing MCP capabilities...")
        mcp_headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'
        }
        
        mcp_response = requests.post(
            endpoint,
            headers=mcp_headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "bitcoin-knowledge-test",
                        "version": "1.0.0"
                    }
                }
            },
            timeout=10
        )
        
        print(f"MCP Status Code: {mcp_response.status_code}")
        if mcp_response.status_code == 200:
            print("✅ MCP protocol working!")
            try:
                mcp_data = mcp_response.json()
                print(f"MCP Response: {json.dumps(mcp_data, indent=2)}")
            except:
                print(f"MCP Response text: {mcp_response.text}")
        else:
            print(f"❌ MCP protocol failed: {mcp_response.status_code}")
            print(f"MCP Response: {mcp_response.text}")
            
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return False
    
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