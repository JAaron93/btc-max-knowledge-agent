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


def parse_env_file(file_path):
    """
    Parse a .env-style file and return a dict of key-value pairs.

    This helper function reads a file, strips leading/trailing whitespace
    from each line, and splits it into a key and value at the first '='
    sign. It skips empty lines and lines starting with '#'.

    To prevent silent configuration errors, it also checks if a variable
    is already defined in the environment and prints a warning if so.

    Args:
        file_path (str): The path to the .env file.

    Returns:
        dict: A dictionary of environment variables.
    """
    env_vars = {}
    try:
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    if key.isidentifier():
                        # Warn if the variable is already set in the environment
                        if key in os.environ:
                            print(
                                f'⚠️  Warning: "{key}" is already set in the '
                                f"environment. The value from {file_path} will override it."
                            )
                        env_vars[key] = value
    except Exception as e:
        print(f"❌ Failed to parse {file_path}: {e}")
    return env_vars


def get_admin_password_securely():
    """Securely get admin password from environment or user input with validation"""
    # First try to get from environment variable (for automated testing)
    password = os.getenv("ADMIN_PASSWORD")

    if password:
        # Validate environment password
        if len(password) < 8:
            print(
                "⚠️  Warning: Environment password is too short (minimum 8 characters)"
            )
            print("   Consider updating ADMIN_PASSWORD environment variable")
            return None
        return password

    # If not in environment, prompt user securely with validation loop
    max_attempts = 3
    attempt = 0

    while attempt < max_attempts:
        try:
            password = getpass.getpass(
                "Enter admin password for testing (minimum 8 characters, optional): "
            )

            # Allow empty password (user can skip)
            if not password:
                print("No password provided - skipping admin authentication tests")
                return None

            # Validate password strength
            if len(password) < 8:
                attempt += 1
                remaining = max_attempts - attempt
                if remaining > 0:
                    print(
                        f"❌ Password too short. Must be at least 8 characters. ({remaining} attempts remaining)"
                    )
                    continue
                else:
                    print(
                        "❌ Maximum attempts reached. Admin authentication tests will be skipped."
                    )
                    return None

            # Password meets requirements
            print("✅ Password meets minimum requirements")
            return password

        except KeyboardInterrupt:
            print("\nPassword input cancelled.")
            return None

    return None


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
        env_vars = parse_env_file(env_admin_path)

        # Check for required variables
        required_vars = ["ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "ADMIN_SECRET_KEY"]
        for var in required_vars:
            if var in env_vars:
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
        env_vars = parse_env_file(env_admin_path)
        if env_vars:
            # Set the parsed environment variables
            for key, value in env_vars.items():
                os.environ[key] = value
        else:
            print("❌ Failed to load .env.admin: No valid environment variables found")
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
