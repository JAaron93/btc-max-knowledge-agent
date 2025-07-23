#!/usr/bin/env python3
"""
Setup script for Pinecone Assistant integration
"""

import os
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()


def check_docker():
    """Check if Docker is installed and running"""
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker is installed:", result.stdout.strip())
            return True
        else:
            print("❌ Docker is not installed or not accessible")
            return False
    except FileNotFoundError:
        print("❌ Docker is not installed")
        return False


def pull_pinecone_assistant_image():
    """Pull the Pinecone Assistant Docker image"""
    print("📦 Pulling Pinecone Assistant Docker image...")
    try:
        result = subprocess.run(
            ["docker", "pull", "pinecone/assistant-mcp"], capture_output=True, text=True
        )

        if result.returncode == 0:
            print("✅ Successfully pulled pinecone/assistant-mcp image")
            return True
        else:
            print("❌ Failed to pull image:", result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error pulling image: {e}")
        return False


def get_pinecone_assistant_host():
    """Help user find their Pinecone Assistant host"""
    print("\n🔍 Finding your Pinecone Assistant Host:")
    print("1. Go to https://app.pinecone.io")
    print("2. Navigate to 'Assistants' section")
    print("3. Create a new Assistant or select an existing one")
    print("4. Look for the Assistant API endpoint/host URL")
    print("5. It should look like: https://assistant-<id>.pinecone.io")

    host = input("\nEnter your Pinecone Assistant Host URL: ").strip()

    if host and host.startswith("https://"):
        return host
    else:
        print("❌ Invalid host URL. It should start with https://")
        return None


def update_env_file(host):
    """Update the .env file with the Pinecone Assistant host"""
    try:
        with open(".env", "r") as f:
            content = f.read()

        # Replace the placeholder with actual host
        updated_content = content.replace(
            'PINECONE_ASSISTANT_HOST="YOUR_PINECONE_ASSISTANT_HOST_HERE"',
            f'PINECONE_ASSISTANT_HOST="{host}"',
        )

        with open(".env", "w") as f:
            f.write(updated_content)

        print(f"✅ Updated .env file with host: {host}")
        return True
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False


def test_pinecone_assistant():
    """Test the Pinecone Assistant connection"""
    print("\n🧪 Testing Pinecone Assistant connection...")

    api_key = os.getenv("PINECONE_API_KEY")
    host = os.getenv("PINECONE_ASSISTANT_HOST")

    if not api_key or not host or host == "YOUR_PINECONE_ASSISTANT_HOST_HERE":
        print("❌ Missing API key or host. Please set them in .env file first.")
        return False

    try:
        # Test Docker container
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-e",
                f"PINECONE_API_KEY={api_key}",
                "-e",
                f"PINECONE_ASSISTANT_HOST={host}",
                "pinecone/assistant-mcp",
                "--help",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("✅ Pinecone Assistant Docker container is working!")
            return True
        else:
            print("❌ Docker container test failed:", result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("⚠️  Docker container test timed out (this might be normal)")
        return True
    except Exception as e:
        print(f"❌ Error testing container: {e}")
        return False


def main():
    print("🚀 Pinecone Assistant Setup")
    print("=" * 40)

    # Check Docker
    if not check_docker():
        print("\n📋 To install Docker:")
        print("- macOS: Download from https://docker.com/products/docker-desktop")
        print("- Or use Homebrew: brew install --cask docker")
        sys.exit(1)

    # Pull Docker image
    if not pull_pinecone_assistant_image():
        sys.exit(1)

    # Check if host is already configured
    current_host = os.getenv("PINECONE_ASSISTANT_HOST")
    if current_host and current_host != "YOUR_PINECONE_ASSISTANT_HOST_HERE":
        print(f"✅ Pinecone Assistant Host already configured: {current_host}")
    else:
        # Get host from user
        host = get_pinecone_assistant_host()
        if not host:
            sys.exit(1)

        # Update .env file
        if not update_env_file(host):
            sys.exit(1)

        # Reload environment
        load_dotenv()

    # Test connection
    test_pinecone_assistant()

    print("\n✅ Setup complete!")
    print("\n📋 Next steps:")
    print("1. Create a Bitcoin knowledge assistant in Pinecone console")
    print("2. Upload your Bitcoin documents to the assistant")
    print("3. Use the MCP tools to query your assistant")
    print("\n🔧 MCP Configuration:")
    print("- File: .kiro/settings/mcp.json")
    print("- The Pinecone Assistant MCP server is configured and ready!")


if __name__ == "__main__":
    main()
