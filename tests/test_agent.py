#!/usr/bin/env python3
"""
Test script for Bitcoin Knowledge Assistant (Pinecone Assistant version)
"""

import json

try:
    from src.agents.pinecone_assistant_agent import PineconeAssistantAgent
except ImportError:
    pass


def load_test_questions(questions_path="tests/test_questions.json"):
    """Load test questions from external JSON file"""
    try:
        from pathlib import Path
        
        questions_file = Path(questions_path)
        if not questions_file.is_absolute():
            questions_file = Path(__file__).parent / "test_questions.json"
        
        with open(questions_file, "r") as f:
            data = json.load(f)
        
        questions = [item["question"] for item in data.get("test_questions", [])]
        if not questions:
            print("⚠️ No test questions found, using fallback questions")
            return [
                "What is Bitcoin and how does it work?",
                "Explain the Lightning Network and its benefits"
            ]
        
        return questions
    except FileNotFoundError:
        print("⚠️ Test questions file not found, using fallback questions")
        return [
            "What is Bitcoin and how does it work?",
            "Explain the Lightning Network and its benefits"
        ]
    except json.JSONDecodeError:
        print("⚠️ Invalid JSON in test questions file, using fallback")
        return [
            "What is Bitcoin and how does it work?",
            "Explain the Lightning Network and its benefits"
        ]
    except Exception as e:
        print(f"⚠️ Error loading test questions: {e}")
        return [
            "What is Bitcoin and how does it work?",
            "Explain the Lightning Network and its benefits"
        ]


def load_assistant_info(config_path="data/assistant_info.json"):
    """Load assistant info from setup"""
    try:
        from pathlib import Path

        config_file = Path(config_path)
        if not config_file.is_absolute():
            config_file = Path(__file__).parent.parent / config_path

        with open(config_file, "r") as f:
            data = json.load(f)

        # Validate required fields
        required_fields = ["assistant_id", "assistant_name", "documents_uploaded"]
        if not all(field in data for field in required_fields):
            print("❌ Invalid assistant info format. Missing required fields.")
            return None

        return data
    except FileNotFoundError:
        print("❌ Assistant info not found. Run setup_bitcoin_assistant.py first!")
        return None
    except json.JSONDecodeError:
        print("❌ Invalid JSON format in assistant info file.")
        return None


def main():
    # Load assistant info
    assistant_info = load_assistant_info()
    if not assistant_info:
        return
    
    assistant_id = assistant_info.get("assistant_id")
    if not assistant_id:
        print("❌ Invalid assistant info: missing assistant_id")
        return

    print(f"🤖 Using assistant: {assistant_info.get('assistant_name', 'Unknown')}")
    documents_count = assistant_info.get('documents_uploaded', 'Unknown')
    print(f"📚 Documents in knowledge base: {documents_count}")
    
    # Load test questions
    test_questions = load_test_questions()
    print(f"\n📝 Testing with {len(test_questions)} questions...\n")
    
    # Initialize agent
    try:
        agent = PineconeAssistantAgent(assistant_id=assistant_id)
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        return
    
    # Test each question
    for i, question in enumerate(test_questions, 1):
        print(f"Question {i}: {question}")
        try:
            response = agent.process_query(question)
            print(f"✅ Response: {response[:200]}..." if len(response) > 200 else f"✅ Response: {response}")
        except Exception as e:
            print(f"❌ Error: {e}")
        print("-" * 80)

if __name__ == "__main__":
    main()
