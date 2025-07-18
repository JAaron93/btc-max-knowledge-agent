#!/usr/bin/env python3
"""
Test script for Bitcoin Knowledge Assistant (Pinecone Assistant version)
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agents.pinecone_assistant_agent import PineconeAssistantAgent

def load_assistant_info():
    """Load assistant info from setup"""
    try:
        with open('data/assistant_info.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Assistant info not found. Run setup_bitcoin_assistant.py first!")
        return None

def main():
    print("🤖 Bitcoin Knowledge Assistant Test")
    print("=" * 40)
    
    try:
        # Load assistant info
        assistant_info = load_assistant_info()
        if not assistant_info:
            return
        
        assistant_id = assistant_info['assistant_id']
        print(f"🤖 Using assistant: {assistant_info['assistant_name']}")
        print(f"📚 Documents in knowledge base: {assistant_info['documents_uploaded']}")
        
        # Initialize agent
        agent = PineconeAssistantAgent()
        
        # Test questions
        test_questions = [
            "What is Bitcoin and how does it work?",
            "Explain the Lightning Network and its benefits",
            "What are decentralized applications (dApps)?",
            "Tell me about the GENIUS Act and its impact on blockchain",
            "What are the key differences between Bitcoin and traditional currency?"
        ]
        
        print("\n🧪 Testing with sample questions...\n")
        
        for i, question in enumerate(test_questions, 1):
            print(f"Q{i}: {question}")
            print("-" * 50)
            
            try:
                result = agent.query_assistant(assistant_id, question)
                answer = result.get('answer', 'No answer received')
                sources = result.get('sources', [])
                
                print(f"🤖 A{i}: {answer}")
                
                if sources:
                    print(f"\n📚 Sources ({len(sources)} citations):")
                    for j, source in enumerate(sources[:3], 1):  # Show first 3 sources
                        title = source.get('title', 'Unknown')
                        print(f"   {j}. {title}")
                
                print("\n" + "="*60 + "\n")
                
            except Exception as e:
                print(f"❌ Error answering question: {e}\n")
        
        # Show assistant info
        print("📊 Assistant Information:")
        assistant_details = agent.get_assistant_info(assistant_id)
        if assistant_details:
            print(f"   Name: {assistant_details.get('name', 'Unknown')}")
            print(f"   Model: {assistant_details.get('model', 'Unknown')}")
            print(f"   Created: {assistant_details.get('created_at', 'Unknown')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you've run setup_bitcoin_assistant.py first")
        print("2. Check your PINECONE_ASSISTANT_HOST in .env")
        print("3. Verify your Pinecone API key is correct")

if __name__ == "__main__":
    main()