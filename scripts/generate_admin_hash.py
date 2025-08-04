#!/usr/bin/env python3
"""
Generate Admin Password Hash
Utility to generate secure password hashes for admin authentication
"""

import getpass
import hashlib
import os
import random
import re
import secrets
import string
import sys


def hash_password(password: str) -> str:
    """Hash password using PBKDF2 with salt"""
    salt = secrets.token_bytes(32)
    pwdhash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return salt.hex() + ":" + pwdhash.hex()


def get_common_passwords() -> set:
    """Return a set of common passwords to reject"""
    return {
        "password",
        "password123",
        "123456",
        "123456789",
        "qwerty",
        "abc123",
        "password1",
        "admin",
        "administrator",
        "root",
        "user",
        "guest",
        "welcome",
        "login",
        "passw0rd",
        "p@ssword",
        "p@ssw0rd",
        "12345678",
        "qwerty123",
        "letmein",
        "monkey",
        "dragon",
        "master",
        "shadow",
        "football",
        "baseball",
        "superman",
        "batman",
        "trustno1",
        "iloveyou",
        "welcome123",
        "admin123",
        "administrator123",
        "root123",
        "test",
        "test123",
        "demo",
        "demo123",
        "changeme",
        "change123",
        "default",
        "bitcoin",
        "crypto",
        "blockchain",
        "satoshi",
        "nakamoto",
    }


def validate_password(password: str) -> tuple[bool, list[str]]:
    """
    Validate password strength according to security requirements

    Returns:
        tuple[bool, list[str]]: (is_valid, list_of_error_messages)
    """
    errors = []

    # Check minimum length (12 characters)
    if len(password) < 12:
        errors.append("Password must be at least 12 characters long")

    # Check for uppercase letters
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")

    # Check for lowercase letters
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")

    # Check for numbers
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one number")

    # Check for special characters
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>?/~`]', password):
        errors.append(
            "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;':\",./<>?~`)"
        )

    # Check against common passwords (case-insensitive)
    common_passwords = get_common_passwords()
    if password.lower() in common_passwords:
        errors.append(
            "Password is too common and easily guessable. Please choose a more unique password"
        )

    # Check for simple patterns
    if re.search(
        r"(.)\1{2,}", password
    ):  # Three or more consecutive identical characters
        errors.append(
            "Password should not contain three or more consecutive identical characters"
        )

    # Check for simple sequences
    sequences = [
        "123",
        "234",
        "345",
        "456",
        "567",
        "678",
        "789",
        "890",
        "abc",
        "bcd",
        "cde",
        "def",
        "efg",
        "fgh",
        "ghi",
        "hij",
        "ijk",
        "jkl",
        "klm",
        "lmn",
        "mno",
        "nop",
        "opq",
        "pqr",
        "qrs",
        "rst",
        "stu",
        "tuv",
        "uvw",
        "vwx",
        "wxy",
        "xyz",
    ]

    password_lower = password.lower()
    for seq in sequences:
        if (
            seq in password_lower or seq[::-1] in password_lower
        ):  # Check forward and reverse
            errors.append(
                "Password should not contain simple sequences (e.g., 123, abc)"
            )
            break

    return len(errors) == 0, errors


def generate_password_suggestion() -> str:
    """Generate a secure password suggestion"""
    # Components for a strong password
    uppercase = random.choices(string.ascii_uppercase, k=3)
    lowercase = random.choices(string.ascii_lowercase, k=4)
    digits = random.choices(string.digits, k=3)
    special = random.choices("!@#$%^&*()_+-=[]{}|;:,.<>?", k=2)

    # Combine and shuffle
    all_chars = uppercase + lowercase + digits + special
    random.shuffle(all_chars)

    return "".join(all_chars)


def generate_secret_key() -> str:
    """Generate a secure secret key"""
    return secrets.token_hex(32)


def main():
    """Main function to generate admin credentials"""
    print("🔐 Bitcoin Knowledge Assistant - Admin Credential Generator")
    print("=" * 60)

    print("\n1. Admin Username:")
    username = input("Enter admin username (default: admin): ").strip()
    if not username:
        username = "admin"

    print("\n2. Admin Password:")
    print("Password Requirements:")
    print("• At least 12 characters long")
    print("• Contains uppercase and lowercase letters")
    print("• Contains at least one number")
    print("• Contains at least one special character")
    print("• Not a common or easily guessable password")
    print("• No simple patterns or sequences")

    failed_attempts = 0
    while True:
        password = getpass.getpass("\nEnter admin password: ")

        # Validate password strength
        is_valid, validation_errors = validate_password(password)
        if not is_valid:
            failed_attempts += 1
            print("\n❌ Password validation failed:")
            for error in validation_errors:
                print(f"   • {error}")

            # Offer password suggestion after 2 failed attempts
            if failed_attempts >= 2:
                suggestion = generate_password_suggestion()
                print(
                    f"\n💡 Need help? Here's a secure password suggestion: {suggestion}"
                )
                print("   (You can modify it to make it more memorable)")

            print("\nPlease try again with a stronger password.")
            continue

        # Confirm password
        confirm_password = getpass.getpass("Confirm admin password: ")
        if password != confirm_password:
            print("❌ Passwords do not match. Please try again.")
            continue

        print("✅ Password meets all security requirements")
        break

    print("\n3. Generating secure credentials...")

    # Generate password hash
    password_hash = hash_password(password)

    # Generate secret key
    secret_key = generate_secret_key()

    print("\n✅ Credentials generated successfully!")
    print("\n" + "=" * 60)
    print("Generated admin credentials:")
    print("=" * 60)
    print(f"ADMIN_USERNAME={username}")
    print(f"ADMIN_PASSWORD_HASH={password_hash}")
    print(f"ADMIN_SECRET_KEY={secret_key}")
    print("=" * 60)
    print("ℹ️  These will be saved to .env.admin file (recommended)")

    print("\n📋 Optional configuration:")
    print("ADMIN_TOKEN_EXPIRY_HOURS=24")
    print("ADMIN_SESSION_TIMEOUT_MINUTES=30")

    print("\n🔒 Security Notes:")
    print("• Keep these credentials secure and never commit them to version control")
    print("• The password hash uses PBKDF2 with 200,000 iterations")
    print("• The secret key is 64 characters of cryptographically secure random data")
    print("• Admin tokens expire after 24 hours by default")
    print("• Sessions timeout after 30 minutes of inactivity")

    print("\n🚀 Next Steps:")
    print("1. Save credentials to .env.admin file (recommended)")
    print("2. Restart the application")
    print("3. Test admin login with: POST /admin/login")

    # Offer to save to file
    save_to_file = (
        input("\n💾 Save credentials to .env.admin file? (y/N): ").strip().lower()
    )
    if save_to_file in ["y", "yes"]:
        try:
            # Check if .env.admin already exists
            if os.path.exists(".env.admin"):
                print("⚠️  .env.admin file already exists!")
                overwrite = (
                    input("Do you want to overwrite it? (y/N): ").strip().lower()
                )
                if overwrite not in ["y", "yes"]:
                    print("❌ Operation cancelled. Existing file preserved.")
                    return

            # Create the file with restrictive permissions
            with open(".env.admin", "w") as f:
                f.write("# Admin Authentication Configuration\n")
                f.write("# Generated by generate_admin_hash.py\n")
                f.write(f"ADMIN_USERNAME={username}\n")
                f.write(f"ADMIN_PASSWORD_HASH={password_hash}\n")
                f.write(f"ADMIN_SECRET_KEY={secret_key}\n")
                f.write("\n# Optional configuration\n")
                f.write("ADMIN_TOKEN_EXPIRY_HOURS=24\n")
                f.write("ADMIN_SESSION_TIMEOUT_MINUTES=30\n")

            # Set restrictive file permissions (owner read/write only)
            os.chmod(".env.admin", 0o600)

            print("✅ Credentials saved to .env.admin")
            print("🔒 File permissions set to 600 (owner read/write only)")
            print("⚠️  Remember to add .env.admin to your .gitignore file!")

        except Exception as e:
            print(f"❌ Failed to save credentials: {e}")
            print("💡 Make sure you have write permissions in the current directory")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
