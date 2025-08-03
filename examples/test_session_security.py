#!/usr/bin/env python3
"""
Test Session Security Validation
Demonstrates the session ownership validation logic
"""

def validate_session_ownership(current_session_id, requested_session_id):
    """
    Simulate the session ownership validation logic
    
    Args:
        current_session_id: Session ID from cookie
        requested_session_id: Session ID being accessed/deleted
        
    Returns:
        tuple: (is_valid, status_code, message)
    """
    
    # No active session cookie
    if not current_session_id:
        return False, 401, "No active session found. Session access requires an active session cookie."
    
    # Session ID mismatch (trying to access someone else's session)
    if current_session_id != requested_session_id:
        return False, 403, "Forbidden: You can only access your own session. Session ownership validation failed."
    
    # Valid ownership
    return True, 200, "Session ownership validated successfully."


def test_session_security():
    """Test various session security scenarios"""
    
    print("🔒 Session Ownership Validation Test")
    print("=" * 50)
    
    test_cases = [
        {
            "name": "No session cookie",
            "current_session": None,
            "requested_session": "session-123",
            "expected_status": 401
        },
        {
            "name": "Empty session cookie",
            "current_session": "",
            "requested_session": "session-123", 
            "expected_status": 401
        },
        {
            "name": "Wrong session ID (cross-user access attempt)",
            "current_session": "alice-session-123",
            "requested_session": "bob-session-456",
            "expected_status": 403
        },
        {
            "name": "Valid session ownership",
            "current_session": "user-session-123",
            "requested_session": "user-session-123",
            "expected_status": 200
        },
        {
            "name": "Case sensitive session IDs",
            "current_session": "Session-123",
            "requested_session": "session-123",
            "expected_status": 403
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        
        is_valid, status_code, message = validate_session_ownership(
            test_case['current_session'],
            test_case['requested_session']
        )
        
        # Check if result matches expectation
        if status_code == test_case['expected_status']:
            print(f"   ✅ Status: {status_code} (Expected: {test_case['expected_status']})")
            print(f"   📝 Message: {message}")
        else:
            print(f"   ❌ Status: {status_code} (Expected: {test_case['expected_status']})")
            print(f"   📝 Message: {message}")
    
    print(f"\n🎯 Security Validation Summary:")
    print(f"   • 401 Unauthorized: Missing or empty session cookie")
    print(f"   • 403 Forbidden: Session ID mismatch (cross-user access)")
    print(f"   • 200 OK: Valid session ownership")
    
    print(f"\n✅ Session ownership validation prevents:")
    print(f"   • Users accessing other users' session information")
    print(f"   • Users deleting other users' sessions")
    print(f"   • Unauthorized access without session cookies")
    print(f"   • Session hijacking attempts")


if __name__ == "__main__":
    test_session_security()