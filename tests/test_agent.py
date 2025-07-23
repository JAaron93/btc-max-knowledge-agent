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
    print("🤖 Bitcoin Knowledge Assistant Test")
    print("=" * 40)

    try:
        # Load assistant info
        assistant_info = load_assistant_info()
        assistant_id = assistant_info.get("assistant_id")
        if not assistant_id:
            print("❌ Invalid assistant info: missing assistant_id")
            return

        print(f"🤖 Using assistant: {assistant_info.get('assistant_name', 'Unknown')}")
        documents_count = assistant_info.get('documents_uploaded', 'Unknown')
        print(f"📚 Documents in knowledge base: {documents_count}")

        # Initialize agent with error handling
        try:
            agent = PineconeAssistantAgent()
            print("✅ Agent initialized successfully")
        except ImportError as e:
            print(f"❌ Import error: {e}")
            print("Make sure PineconeAssistantAgent is properly installed")
            return
        except Exception as e:
            print(f"❌ Failed to initialize agent: {e}")
            print("Check your environment configuration and API keys")
            return

        # Load test questions dynamically
        test_questions = load_test_questions()
        print(f"📝 Loaded {len(test_questions)} test questions")

        print("\n🧪 Testing with sample questions...\n")

        for i, question in enumerate(test_questions, 1):
            print(f"Q{i}: {question}")
            print("-" * 50)

            try:
                result = agent.query_assistant(assistant_id, question)
                answer = result.get("answer", "No answer received")
                sources = result.get("sources", [])

                print(f"🤖 A{i}: {answer}")

                if sources:
                    print(f"\n📚 Sources ({len(sources)} citations):")
                    for j, source in enumerate(sources[:3], 1):  # Show first 3 sources
                        title = source.get("title", "Unknown")
                        print(f"   {j}. {title}")

                print("\n" + "=" * 60 + "\n")

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
