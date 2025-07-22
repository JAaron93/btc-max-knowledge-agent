#!/usr/bin/env python3
"""
Complete setup script for Bitcoin Knowledge Assistant using Pinecone Assistant
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from btc_max_knowledge_agent.knowledge.data_collector import BitcoinDataCollector
from btc_max_knowledge_agent.agents.pinecone_assistant_agent import PineconeAssistantAgent

def main():
    print("🚀 Bitcoin Knowledge Assistant Setup")
    print("=" * 50)
    
    try:
        # Step 1: Collect Bitcoin documents
        print("1. Collecting Bitcoin and blockchain documents...")
        collector = BitcoinDataCollector()
        documents = collector.collect_all_documents(max_news_articles=50)
        
        if not documents:
            print("❌ No documents collected. Exiting.")
            return
        
        print(f"✅ Collected {len(documents)} documents")
        
        # Save documents locally for backup
        collector.save_documents(documents, "bitcoin_knowledge_base.json")
        
        # Step 2: Initialize Pinecone Assistant
        print("\n2. Initializing Pinecone Assistant...")
        assistant_agent = PineconeAssistantAgent()
        
        # Step 3: Check for existing assistants
        print("\n3. Checking for existing assistants...")
        assistants = assistant_agent.list_assistants()
        
        # Look for existing Bitcoin assistant
        bitcoin_assistant = None
        for assistant in assistants:
            if 'bitcoin' in assistant.get('name', '').lower():
                bitcoin_assistant = assistant
                print(f"✅ Found existing Bitcoin assistant: {assistant['name']}")
                break
        
        # Step 4: Create assistant if needed
        if not bitcoin_assistant:
            print("\n4. Creating new Bitcoin Knowledge Assistant...")
            bitcoin_assistant = assistant_agent.create_assistant("Bitcoin Knowledge Assistant")
            
            if not bitcoin_assistant:
                print("❌ Failed to create assistant. Exiting.")
                return
        else:
            print(f"\n4. Using existing assistant: {bitcoin_assistant['name']}")
        
        assistant_id = bitcoin_assistant['id']
        
        # Step 5: Upload documents
        print(f"\n5. Uploading {len(documents)} documents to assistant...")
        success = assistant_agent.upload_documents(assistant_id, documents)
        
        if not success:
            print("❌ Failed to upload documents. Exiting.")
            return
        
        # Step 6: Test the assistant
        print("\n6. Testing the assistant...")
        test_questions = [
            "What is Bitcoin?",
            "How does the Lightning Network work?",
            "What are dApps?",
            "Tell me about the GENIUS Act"
        ]
        
        for question in test_questions:
            print(f"\n🤔 Q: {question}")
            result = assistant_agent.query_assistant(assistant_id, question)
            answer = result.get('answer', 'No answer received')
            sources = result.get('sources', [])
            
            print(f"🤖 A: {answer[:200]}{'...' if len(answer) > 200 else ''}")
            if sources:
                print(f"📚 Sources: {len(sources)} citations")
        
        # Step 7: Save assistant info
        assistant_info = {
            'assistant_id': assistant_id,
            'assistant_name': bitcoin_assistant['name'],
            'documents_uploaded': len(documents),
            'setup_complete': True
        }
        
        with open('data/assistant_info.json', 'w') as f:
            json.dump(assistant_info, f, indent=2)
        
        print("\n✅ Setup Complete!")
        print("=" * 50)
        print(f"🤖 Assistant ID: {assistant_id}")
        print(f"📚 Documents uploaded: {len(documents)}")
        print("💾 Assistant info saved to: data/assistant_info.json")
        print("\n🔧 MCP Integration:")
        print("- Your Pinecone Assistant MCP is configured in .kiro/settings/mcp.json")
        print("- You can now use MCP tools to interact with your assistant")
        print("- The assistant is ready for Bitcoin and blockchain questions!")
        
        print("\n📋 Next Steps:")
        print("1. Test MCP integration in Kiro IDE")
        print("2. Ask Bitcoin questions using the assistant")
        print("3. Add more documents as needed")
        
    except Exception as e:
        print(f"❌ Error during setup: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PINECONE_ASSISTANT_HOST is set in .env")
        print("2. Run setup_pinecone_assistant.py first if needed")
        print("3. Check your Pinecone API key and permissions")
        sys.exit(1)

if __name__ == "__main__":
    main()