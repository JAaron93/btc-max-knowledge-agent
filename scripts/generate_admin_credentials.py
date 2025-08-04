#!/usr/bin/env python3
"""
Generate Admin Credentials Script
Generates secure admin password hash and secret key for production deployment
"""

import secrets
import getpass
import sys

try:
    from argon2 import PasswordHasher
except ImportError:
    print("Error: argon2-cffi library not found.")
    print("Install it with: pip install argon2-cffi")
    sys.exit(1)


def hash_password(password: str) -> str:
    """Hash password using Argon2id (OWASP recommended)"""
    hasher = PasswordHasher()
    return hasher.hash(password)


def generate_secret_key() -> str:
    """Generate a secure 64-character hex string (32 bytes)"""
    return secrets.token_hex(32)


def main():
    print("🔐 Bitcoin Knowledge Assistant - Admin Credentials Generator")
    print("=" * 65)
    
    print("\nThis script will generate secure admin credentials for production deployment.")
    print("The generated credentials should be added to your .env file or environment variables.")
    
    # Get admin username
    print("\n1. Admin Username Configuration")
    print("-" * 35)
    username = input("Enter admin username (default: admin): ").strip()
    if not username:
        username = "admin"
    
    # Get admin password
    print("\n2. Admin Password Configuration")
    print("-" * 35)
    print("Password requirements:")
    print("• Minimum 12 characters")
    print("• Mix of uppercase, lowercase, numbers, and symbols")
    print("• Avoid common passwords or dictionary words")
    
    while True:
        password = getpass.getpass("\nEnter admin password: ")
        if len(password) < 8:
            print("⚠️  Password too short. Minimum 8 characters required.")
            continue
        
        confirm_password = getpass.getpass("Confirm admin password: ")
        if password != confirm_password:
            print("⚠️  Passwords don't match. Please try again.")
            continue
        
        break
    
    # Generate credentials
    print("\n3. Generating Secure Credentials")
    print("-" * 35)
    print("🔄 Hashing password with Argon2id...")
    password_hash = hash_password(password)
    
    print("🔄 Generating secret key (64 hex characters)...")
    secret_key = generate_secret_key()
    
    # Display results
    print("\n4. Generated Credentials")
    print("-" * 35)
    print("✅ Credentials generated successfully!")
    
    print(f"\n📝 Add these to your .env file:")
    print("=" * 50)
    print(f"ADMIN_USERNAME={username}")
    print(f"ADMIN_PASSWORD_HASH={password_hash}")
    print(f"ADMIN_SECRET_KEY={secret_key}")
    print("=" * 50)
    
    print(f"\n🚀 Or set as environment variables:")
    print("=" * 50)
    print(f'export ADMIN_USERNAME="{username}"')
    print(f'export ADMIN_PASSWORD_HASH="{password_hash}"')
    print(f'export ADMIN_SECRET_KEY="{secret_key}"')
    print("=" * 50)
    
    # Security reminders
    print(f"\n🔒 Security Reminders:")
    print("• Keep these credentials secure and private")
    print("• Never commit credentials to version control")
    print("• Use environment variables in production")
    print("• Rotate credentials regularly")
    print("• Monitor admin access logs")
    
    # Verification info
    print(f"\n📊 Credential Information:")
    print(f"• Username: {username}")
    print(f"• Password hash format: Argon2id")
    print(f"• Password hash length: {len(password_hash)} characters")
    print(f"• Secret key length: {len(secret_key)} characters (32 bytes)")
    print(f"• Hash algorithm: Argon2id (OWASP recommended)")
    
    print(f"\n✅ Admin credentials ready for production deployment!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error generating credentials: {e}")
        sys.exit(1)