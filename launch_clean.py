#!/usr/bin/env python3
"""
Clean launcher for Bitcoin Knowledge Assistant
Handles port conflicts and process cleanup
"""

import os
import signal
import subprocess
import sys
import time

import psutil
from dotenv import load_dotenv

load_dotenv()


def kill_processes_on_port(port):
    """Kill any processes running on the specified port"""
    processes_to_kill = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            # Use modern psutil API compatible with psutil 6+
            connections = proc.net_connections(kind="inet")
            for conn in connections:
                if hasattr(conn, "laddr") and conn.laddr.port == port:
                    print(
                        f"🔄 Stopping process {proc.info['name']} (PID: {proc.info['pid']}) on port {port}"
                    )
                    processes_to_kill.append(proc)
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # Terminate processes and wait with timeout
    killed_count = 0
    for proc in processes_to_kill:
        try:
            proc.terminate()
            killed_count += 1

            # Wait for process to terminate gracefully (up to 5 seconds)
            try:
                proc.wait(timeout=5)
                print(f"✅ Process {proc.pid} terminated gracefully")
            except psutil.TimeoutExpired:
                # Process didn't terminate in time, force kill it
                print(f"⚠️  Process {proc.pid} didn't terminate, force killing...")
                proc.kill()
                try:
                    proc.wait(timeout=2)
                    print(f"🔨 Process {proc.pid} force killed")
                except psutil.TimeoutExpired:
                    print(f"❌ Failed to kill process {proc.pid}")

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process already gone or access denied
            pass

    if killed_count > 0:
        print(f"✅ Cleaned up {killed_count} processes on port {port}")

    return killed_count


def check_dependencies():
    """Check if required dependencies are installed"""
    import importlib.util

    required_packages = ["fastapi", "uvicorn", "gradio", "requests"]

    for package in required_packages:
        if importlib.util.find_spec(package) is None:
            print(f"❌ {package} not found")
            print("Please install requirements: pip install -r requirements.txt")
            return False

    print("✅ All dependencies are installed")
    return True


def start_api_server():
    """Start the FastAPI server"""
    api_port = int(os.getenv("API_PORT", 8000))

    print(f"🚀 Starting FastAPI server on port {api_port}")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.web.bitcoin_assistant_api:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(api_port),
    ]

    # Only add --reload in development environments
    env = os.getenv("ENV", "").lower()
    debug = os.getenv("DEBUG", "").lower()
    environment = os.getenv("ENVIRONMENT", "").lower()

    is_development = (
        env in ("development", "dev")
        or debug in ("true", "1", "yes")
        or environment in ("development", "dev")
    )

    if is_development:
        cmd.append("--reload")
        print("🔄 Development mode: auto-reload enabled")
    else:
        print("🏭 Production mode: auto-reload disabled")

    return subprocess.Popen(cmd)


def start_gradio_ui():
    """Start the Gradio UI"""
    ui_port = int(os.getenv("UI_PORT", 7860))

    print(f"🎨 Starting Gradio UI on port {ui_port}")

    # Set environment variables for the UI
    env = os.environ.copy()
    env["UI_PORT"] = str(ui_port)
    env["UI_HOST"] = "0.0.0.0"

    cmd = [sys.executable, "src/web/bitcoin_assistant_ui.py"]

    return subprocess.Popen(cmd, env=env)


def wait_for_api(max_attempts=30):
    """Wait for API to be ready"""
    import requests

    api_port = int(os.getenv("API_PORT", 8000))
    api_url = f"http://localhost:{api_port}/"
    health_url = f"http://localhost:{api_port}/health"

    # Import centralized retry configuration

    # First check if server is responding at all
    for attempt in range(max_attempts):
        try:
            response = requests.get(api_url, timeout=3)
            if response.status_code == 200:
                print("✅ API server is responding!")
                break
        except Exception:
            pass

        print(f"⏳ Waiting for API server... ({attempt + 1}/{max_attempts})")
        time.sleep(2)
    else:
        print("❌ API server failed to start")
        return False

    # Then check health endpoint (allow more time for Pinecone connection)
    print("🔍 Checking health endpoint...")
    for attempt in range(10):
        try:
            response = requests.get(health_url, timeout=10)
            if response.status_code == 200:
                print("✅ Health check passed!")
                return True
            elif response.status_code == 503:
                print(f"⏳ Service initializing... ({attempt + 1}/10)")
        except Exception as e:
            print(f"⏳ Health check attempt {attempt + 1}/10 failed: {e}")

        time.sleep(3)

    print("⚠️  Health check failed, but API server is running")
    print("   This may indicate a Pinecone connection issue")
    return True  # Continue anyway since basic server is working


def main():
    """Main launcher function"""
    print("🪙 Bitcoin Knowledge Assistant - Clean Launcher")
    print("=" * 55)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Get ports from environment
    api_port = int(os.getenv("API_PORT", 8000))
    ui_port = int(os.getenv("UI_PORT", 7860))

    # Clean up any existing processes on these ports
    print("🧹 Cleaning up existing processes...")
    killed_api = kill_processes_on_port(api_port)
    killed_ui = kill_processes_on_port(ui_port)

    if killed_api or killed_ui:
        print("⏳ Waiting for cleanup to complete...")
        time.sleep(3)

    # Start API server
    api_process = start_api_server()

    # Wait for API to be ready
    if not wait_for_api():
        api_process.terminate()
        sys.exit(1)

    # Start Gradio UI
    ui_process = start_gradio_ui()

    print("\n🎉 Bitcoin Knowledge Assistant is running!")
    print("=" * 55)
    print(f"📡 API Server: http://localhost:{api_port}")
    print(f"🌐 Web UI: http://localhost:{ui_port}")
    print(f"📚 API Docs: http://localhost:{api_port}/docs")
    print("\nPress Ctrl+C to stop both servers")

    def signal_handler(sig, frame):
        print("\n🛑 Shutting down servers...")
        api_process.terminate()
        ui_process.terminate()

        # Wait for processes to terminate
        try:
            api_process.wait(timeout=5)
            ui_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("⚠️  Force killing processes...")
            api_process.kill()
            ui_process.kill()

            # Wait for processes to be fully reaped after kill()
            try:
                api_process.wait(timeout=3)
            except (subprocess.TimeoutExpired, OSError):
                # Ignore exceptions during cleanup
                pass

            try:
                ui_process.wait(timeout=3)
            except (subprocess.TimeoutExpired, OSError):
                # Ignore exceptions during cleanup
                pass

        print("✅ Servers stopped successfully")
        sys.exit(0)

    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Wait for both processes
        while api_process.poll() is None and ui_process.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
