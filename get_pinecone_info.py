#!/usr/bin/env python3
"""
Script to help you find your Pinecone Assistant information
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

def check_pinecone_connection():
    """Check basic Pinecone API connection"""
    api_key = os.getenv('PINECONE_API_KEY')
    
    if not api_key:
        print("❌ PINECONE_API_KEY not found in .env file")
        return False
    
    print(f"✅ Found Pinecone API Key: {api_key[:10]}...")
    
    # Try to get Pinecone indexes to verify connection
    try:
        headers = {
            'Api-Key': api_key,
            'Content-Type': 'application/json'
        }
        
        # This is the standard Pinecone API endpoint
        response = requests.get(
            'https://api.pinecone.io/indexes',
            headers=headers
        )
        
        if response.status_code == 200:
            indexes = response.json()
            print(f"✅ Successfully connected to Pinecone API")
            print(f"📊 Found {len(indexes.get('indexes', []))} indexes")
            
            for index in indexes.get('indexes', []):
                print(f"   - {index.get('name', 'Unknown')}")
            
            return True
        else:
            print(f"❌ Failed to connect to Pinecone API: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error connecting to Pinecone: {e}")
        return False

def find_assistant_endpoints():
    """Help user find their Pinecone Assistant endpoints"""
    print("\n🔍 Finding Your Pinecone Assistant Information:")
    print("=" * 50)
    
    print("1. Go to https://app.pinecone.io")
    print("2. Look for 'Assistants' in the left sidebar")
    print("3. If you don't see 'Assistants', you may need to:")
    print("   - Upgrade your Pinecone plan")
    print("   - Enable the Assistant feature")
    print("   - Check if it's available in your region")
    
    print("\n4. Once in Assistants:")
    print("   - Create a new Assistant or select existing one")
    print("   - Look for API endpoint or host URL")
    print("   - It typically looks like: https://assistant-<id>.pinecone.io")
    print("   - Or: https://<region>-assistant.pinecone.io")
    
    print("\n5. Alternative approach:")
    print("   - Check Pinecone documentation for Assistant API")
    print("   - Look in your Pinecone console settings")
    print("   - Contact Pinecone support if Assistant feature isn't visible")

def test_assistant_host():
    """Test if user has a working assistant host"""
    host = input("\nEnter your Pinecone Assistant Host URL (or press Enter to skip): ").strip()
    
    if not host:
        return None
    
    if not host.startswith('https://'):
        host = 'https://' + host
    
    api_key = os.getenv('PINECONE_API_KEY')
    
    try:
        headers = {
            'Api-Key': api_key,
            'Content-Type': 'application/json'
        }
        
        # Test basic connection to assistant endpoint
        response = requests.get(
            f"{host}/assistants",
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 401, 403]:  # 401/403 means endpoint exists but auth issue
            print(f"✅ Assistant endpoint is reachable: {host}")
            return host
        else:
            print(f"❌ Assistant endpoint test failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error testing assistant host: {e}")
        return None

def main():
    print("🔍 Pinecone Assistant Information Finder")
    print("=" * 50)
    
    # Check basic Pinecone connection
    if not check_pinecone_connection():
        print("\n❌ Cannot proceed without valid Pinecone API connection")
        return
    
    # Help find assistant endpoints
    find_assistant_endpoints()
    
    # Test assistant host if provided
    host = test_assistant_host()
    
    if host:
        # Update .env file
        try:
            with open('.env', 'r') as f:
                content = f.read()
            
            updated_content = content.replace(
                'PINECONE_ASSISTANT_HOST="YOUR_PINECONE_ASSISTANT_HOST_HERE"',
                f'PINECONE_ASSISTANT_HOST="{host}"'
            )
            
            with open('.env', 'w') as f:
                f.write(updated_content)
            
            print(f"✅ Updated .env file with host: {host}")
            
        except Exception as e:
            print(f"❌ Error updating .env file: {e}")
    
    print("\n📋 Next Steps:")
    print("1. If you found your Assistant host, the .env file has been updated")
    print("2. If Assistants aren't available, consider using regular Pinecone indexes")
    print("3. You can also proceed with the standard RAG approach using our existing code")

if __name__ == "__main__":
    main()