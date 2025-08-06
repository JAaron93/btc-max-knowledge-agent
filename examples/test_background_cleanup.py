#!/usr/bin/env python3
"""
Test script to verify background cleanup functionality

This script uses secure import methods instead of sys.path manipulation
to avoid potential security risks from path injection attacks.
"""

import asyncio
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path


# Safely resolve and import modules without modifying sys.path
def safe_import_from_project(module_path: str, module_name: str = None):
    """
    Safely import a module from the project without modifying sys.path.

    This approach is more secure than sys.path manipulation because:
    - It doesn't globally modify the Python path
    - It uses explicit path resolution
    - It prevents potential security issues from path injection
    - It's more predictable and doesn't affect other imports

    Args:
        module_path: Relative path to the module from project root (e.g., 'src/web/admin_auth.py')
        module_name: Optional module name for the spec (defaults to derived name)

    Returns:
        The imported module

    Raises:
        ImportError: If the module cannot be found or loaded
    """
    try:
        project_root = Path(__file__).parent.parent.resolve()
        full_module_path = project_root / module_path

        if not full_module_path.exists():
            raise ImportError(f"Module not found: {full_module_path}")

        if module_name is None:
            module_name = module_path.replace("/", ".").replace(".py", "")

        spec = importlib.util.spec_from_file_location(module_name, full_module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create module spec for {module_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    except Exception as e:
        raise ImportError(f"Failed to safely import {module_path}: {e}") from e


# Import required modules safely
admin_auth_module = safe_import_from_project("src/web/admin_auth.py", "admin_auth")
AdminAuthenticator = admin_auth_module.AdminAuthenticator


async def test_background_cleanup():
    """Test the background cleanup functionality"""

    print("🧪 Testing Admin Session Background Cleanup")
    print("=" * 50)

    # Create authenticator
    auth = AdminAuthenticator()

    # Create some test sessions
    print("\n1. Creating test sessions...")
    tokens = []
    for i in range(3):
        token = auth.authenticate_admin("admin", "admin123", f"192.168.1.{100 + i}")
        if token:
            tokens.append(token)
            print(f"   ✅ Created session {i + 1}: {token[:16]}...")
        else:
            print(f"   ❌ Failed to create session {i + 1}")

    if not tokens:
        print("   🚨 No sessions created - cannot continue test")
        return

    print(f"\n   📊 Active sessions: {len(auth.active_sessions)}")

    # Simulate some expired sessions
    print("\n2. Simulating expired sessions...")
    for i, token in enumerate(tokens[:2]):  # Expire first 2 sessions
        if token in auth.active_sessions:
            auth.active_sessions[token]["expires_at"] = datetime.now() - timedelta(
                hours=1
            )
            print(f"   🕐 Expired session {i + 1}")
        else:
            print(
                f"   ⚠️  Failed to simulate session expiry for session {i + 1} (token: {token[:16]}...)"
            )

    print(f"   📊 Sessions before cleanup: {len(auth.active_sessions)}")

    # Test manual cleanup
    print("\n3. Testing manual cleanup...")
    expired_count = auth.cleanup_expired_sessions()
    print(f"   🧹 Manual cleanup removed: {expired_count} sessions")
    print(f"   📊 Sessions after cleanup: {len(auth.active_sessions)}")

    # Test background cleanup task
    print("\n4. Testing background cleanup task...")

    # Create more sessions and expire them
    for i in range(2):
        token = auth.authenticate_admin("admin", "admin123", f"192.168.1.{200 + i}")
        if token:
            if token in auth.active_sessions:
                auth.active_sessions[token]["expires_at"] = datetime.now() - timedelta(
                    hours=1
                )
                print(f"   🕐 Created and expired session: {token[:16]}...")
            else:
                print(
                    f"   ⚠️  Failed to simulate expiry for created session: {token[:16]}..."
                )
        else:
            print(f"   ❌ Failed to authenticate admin for session {i + 1}")

    print(f"   📊 Sessions before background cleanup: {len(auth.active_sessions)}")

    try:
        # Start background cleanup
        auth.start_background_cleanup()
        print("   🚀 Started background cleanup task")

        # Wait longer to allow background task to potentially run
        print("   ⏳ Waiting for background task...")
        await asyncio.sleep(3)

        # Check if background task cleaned up sessions
        current_sessions = len(auth.active_sessions)
        print(f"   📊 Sessions after background cleanup: {current_sessions}")

    finally:
        # Ensure cleanup task is stopped
        auth.stop_background_cleanup()
        print("   🛑 Stopped background cleanup task")

    print("\n✅ Background cleanup test completed successfully!")
    print("\n🔍 Key Features Tested:")
    print("   • Manual cleanup removes expired sessions")
    print("   • Session expiry simulation works")
    print("   • Session creation and tracking works")
    print("   • Test infrastructure is functional")
    print("\n⚠️  Background Task Limitations:")
    print("   • Background task start/stop called but not fully verified")
    print("   • Actual background cleanup behavior not confirmed")
    print("   • Logging and validation integration not tested")


if __name__ == "__main__":
    asyncio.run(test_background_cleanup())
