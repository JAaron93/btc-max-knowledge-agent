#!/usr/bin/env python3
"""
Verify Admin Setup
Quick verification that admin credentials are properly configured
"""

import getpass
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_admin_password_securely():
    """Securely get admin password from environment or user input"""
    # First try to get from environment variable (for automated testing)
    password = os.getenv("ADMIN_PASSWORD")

    if not password:
        # If not in environment, prompt user securely
        try:
            password = getpass.getpass("Enter admin password for testing (optional): ")
        except KeyboardInterrupt:
            print("\nPassword input cancelled.")
            return None

    return password


def verify_admin_setup():
    """Verify admin setup and configuration"""

    print("🔐 Bitcoin Knowledge Assistant - Admin Setup Verification")
    print("=" * 60)

    print("\n1. 📁 CHECKING CONFIGURATION FILES")
    print("-" * 40)

    # Check for .env.admin file
    env_admin_path = project_root / ".env.admin"
    if env_admin_path.exists():
        print("✅ .env.admin file found")

        # Read and verify contents
        with open(env_admin_path, "r") as f:
            lines = f.readlines()

        required_vars = ["ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "ADMIN_SECRET_KEY"]
        found_vars = set()

        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                var_name = line.split("=", 1)[0].strip()
                if var_name in required_vars:
                    found_vars.add(var_name)

        for var in required_vars:
            if var in found_vars:
                print(f"✅ {var} configured")
            else:
                print(f"❌ {var} missing")
    else:
        print("❌ .env.admin file not found")
        print("   Run: python scripts/generate_admin_hash.py")

    print("\n2. 🔒 CHECKING GITIGNORE PROTECTION")
    print("-" * 40)

    gitignore_path = project_root / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            gitignore_content = f.read()

        if ".env.admin" in gitignore_content:
            print("✅ .env.admin is in .gitignore (secure)")
        else:
            print("⚠️  .env.admin not found in .gitignore")
    else:
        print("❌ .gitignore file not found")

    print("\n3. 🔧 TESTING ADMIN AUTHENTICATION")
    print("-" * 40)

    # Load environment variables from .env.admin
    if env_admin_path.exists():
        try:
            with open(env_admin_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # Basic validation
                        if key.isidentifier():
                            os.environ[key] = value
        except Exception as e:
            print(f"❌ Failed to load .env.admin: {e}")
            return

    try:
        from src.web.admin_auth import AdminAuthenticator

        auth = AdminAuthenticator()
        print("✅ AdminAuthenticator initialized successfully")

        # Test with configured credentials
        username = os.getenv("ADMIN_USERNAME", "admin")
        password_hash = os.getenv("ADMIN_PASSWORD_HASH")
        secret_key = os.getenv("ADMIN_SECRET_KEY")

        # Validate configuration
        print(f"✅ Admin username configured: {username}")
        if password_hash:
            print("✅ Password hash configured")
        else:
            print("❌ Password hash not found in environment")

        if secret_key:
            print("✅ Secret key configured")
        else:
            print("❌ Secret key not found in environment")

        # Test session management
        try:
            stats = auth.get_admin_stats()
            active_sessions = stats["active_admin_sessions"]
            print(f"✅ Admin stats accessible: {active_sessions} active sessions")
        except Exception as stats_error:
            print(f"⚠️  Admin stats not accessible: {stats_error}")

        # Optional password verification test
        print("\n🔐 OPTIONAL PASSWORD VERIFICATION TEST")
        print("-" * 40)
        test_password = get_admin_password_securely()
        if test_password:
            try:
                # Test password verification (if method exists)
                if hasattr(auth, "verify_password"):
                    is_valid = auth.verify_password(username, test_password)
                    if is_valid:
                        print("✅ Password verification successful")
                    else:
                        print("❌ Password verification failed")
                else:
                    print("⚠️  Password verification method not available")
            except Exception as verify_error:
                print(f"⚠️  Password verification test failed: {verify_error}")
        else:
            print("⏭️  Password verification test skipped")

    except Exception as e:
        print(f"❌ Admin authentication test failed: {e}")

    print("\n4. 🚀 NEXT STEPS")
    print("-" * 40)

    print("To use the admin system:")
    print("1. Start the application:")
    print("   python -m uvicorn src.web.bitcoin_assistant_api:app --reload")
    print()
    print("2. Login to get admin token:")
    print("   curl -X POST 'http://localhost:8000/admin/login' \\")
    print("        -H 'Content-Type: application/json' \\")
    username = os.getenv("ADMIN_USERNAME", "admin")
    print(
        f'        -d \'{{"username": "{username}", '
        '"password": "YOUR_ADMIN_PASSWORD"}}\''
    )
    print()
    print("3. Use admin endpoints:")
    print("   curl -H 'Authorization: Bearer YOUR_TOKEN' \\")
    print("        'http://localhost:8000/admin/sessions/stats'")

    print("\n✅ Admin setup verification complete!")
    print("\n🔒 Security Reminders:")
    print("• Never commit .env.admin to version control")
    print("• Use HTTPS in production")
    print("• Regularly rotate admin credentials")
    print("• Monitor admin access logs")
    print("• Store passwords securely (use environment variables or prompts)")
    print("• Never hardcode passwords in source code")


if __name__ == "__main__":
    verify_admin_setup()
