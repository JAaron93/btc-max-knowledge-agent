#!/usr/bin/env python3
"""
Session Management Demo
Demonstrates how the session management system works
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path only when running this demo directly to avoid E402
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.web.session_manager import SessionManager


def demo_session_management():
    """Demonstrate session management features"""

    print("🔗 Bitcoin Knowledge Assistant - Session Management Demo")
    print("=" * 60)

    # Create session manager
    # Short timeout for demo
    manager = SessionManager(session_timeout_minutes=2)

    print("\n1. Creating multiple user sessions...")

    # Simulate multiple users
    users = ["Alice", "Bob", "Charlie"]
    user_sessions = {}

    for user in users:
        session_id = manager.create_session()
        user_sessions[user] = session_id
        print(f"   👤 {user}: Session {session_id[:8]}...")

    active_sessions = manager.get_session_stats()["active_sessions"]
    print(f"\n📊 Active sessions: {active_sessions}")

    print("\n2. Simulating conversations...")

    # Simulate conversations for each user
    conversations = {
        "Alice": [
            (
                "What is Bitcoin?",
                "Bitcoin is a decentralized digital currency...",
            ),
            (
                "How does mining work?",
                "Mining is the process of validating transactions...",
            ),
            (
                "What is the Lightning Network?",
                "The Lightning Network is a layer-2 scaling solution...",
            ),
        ],
        "Bob": [
            (
                "Tell me about blockchain",
                "Blockchain is a distributed ledger technology...",
            ),
            (
                "What are smart contracts?",
                "Smart contracts are self-executing contracts...",
            ),
        ],
        "Charlie": [
            (
                "What is DeFi?",
                "DeFi stands for Decentralized Finance...",
            )
        ],
    }

    for user, convos in conversations.items():
        session_id = user_sessions[user]
        session = manager.get_session(session_id)

        print(f"\n   👤 {user}'s conversation:")
        for i, (question, answer) in enumerate(convos, 1):
            session.add_conversation_turn(question, answer, [])
            print(f"      {i}. Q: {question[:30]}...")
            print(f"         A: {answer[:40]}...")

    print("\n3. Session statistics:")
    stats = manager.get_session_stats()
    for key, value in stats.items():
        print(f"   📈 {key}: {value}")

    print("\n4. Demonstrating conversation context...")

    # Show conversation context for Alice
    alice_session = manager.get_session(user_sessions["Alice"])
    max_turns = 2
    context = alice_session.get_conversation_context(max_turns=max_turns)

    print(f"\n   👤 Alice's recent context (last {max_turns} turns):")
    for i, turn in enumerate(context, 1):
        print(f"      Turn {turn['turn_id']}: {turn['question'][:30]}...")

    print("\n5. Testing session isolation...")

    # Each user should have their own conversation history
    for user in users:
        session = manager.get_session(user_sessions[user])
        history_length = len(session.conversation_history)
        expected_length = len(conversations[user])

        print(f"   👤 {user}: {history_length} turns (expected: {expected_length}) ✅")
        if history_length == expected_length:
            print(
                f"   👤 {user}: {history_length} turns (expected: {expected_length}) ✅"
            )
        else:
            print(
                f"   👤 {user}: {history_length} turns "
                f"(expected: {expected_length}) ❌ ISOLATION FAILED"
            )
            # Consider if demo should exit here or continue with
            # degraded functionality

    print("\n6. Demonstrating session expiry...")

    # Wait for sessions to expire (demo uses 2-minute timeout)
    print("   ⏳ Waiting for sessions to expire (this is a quick demo)...")

    # Manually expire sessions for demo
    for session_id in user_sessions.values():
        session = manager.get_session(session_id)
        if session:
            # Set last activity to 3 minutes ago
            session.last_activity = datetime.now() - timedelta(minutes=3)

    # Try to get expired sessions
    print("   🧹 Checking for expired sessions...")
    active_before = manager.get_session_stats()["active_sessions"]

    # This will trigger cleanup
    for user, session_id in user_sessions.items():
        session = manager.get_session(session_id)
        if session is None:
            print(f"   ❌ {user}'s session expired and was cleaned up")
        else:
            print(f"   ✅ {user}'s session is still active")

    active_after = manager.get_session_stats()["active_sessions"]
    print(f"   📊 Sessions before cleanup: {active_before}, after: {active_after}")

    print("\n7. Creating new session after expiry...")

    # Create new session for Alice
    new_session_id = manager.create_session()
    new_session = manager.get_session(new_session_id)

    print(f"   👤 Alice gets new session: {new_session_id[:8]}...")
    turns = len(new_session.conversation_history)
    print(f"   📝 New session has {turns} conversation turns (should be 0)")

    print("\n✅ Session Management Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("• ✅ Unique session IDs per user")
    print("• ✅ Conversation isolation between users")
    print("• ✅ Conversation context within sessions")
    print("• ✅ Automatic session expiry and cleanup")
    print("• ✅ Session statistics and monitoring")
    print("• ✅ Fresh start for new sessions")


if __name__ == "__main__":
    demo_session_management()
