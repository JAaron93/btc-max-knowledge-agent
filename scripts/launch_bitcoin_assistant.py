#!/usr/bin/env python3
"""
Launch script for Bitcoin Knowledge Assistant Web Application
"""

import os
import signal
import subprocess
import sys
import time
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def create_log_directory():
    """Create logs directory if it doesn't exist"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    return log_dir


def tail_process_output(process, log_file_path, prefix):
    """Tail process output to both console and log file"""

    def read_output(pipe, output_type):
        with open(log_file_path, "a") as log_file:
            for line in iter(pipe.readline, ""):
                if line:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    log_line = (
                        f"[{timestamp}] {prefix} {output_type}: {line.rstrip()}"
                        "\n"
                    )
                    log_file.write(log_line)
                    log_file.flush()
                    # Optionally print to console (uncomment if needed)
                    # print(f"{prefix} {output_type}: {line.rstrip()}")
            # Ensure the pipe is closed after reading all output to avoid descriptor leaks
            pipe.close()

    # Start threads to handle stdout and stderr
    if process.stdout:
        stdout_thread = threading.Thread(
            target=read_output, args=(process.stdout, "STDOUT"), daemon=True
        )
        stdout_thread.start()

    if process.stderr:
        stderr_thread = threading.Thread(
            target=read_output, args=(process.stderr, "STDERR"), daemon=True
        )
        stderr_thread.start()


def launch_subprocess(name: str, cmd: list[str], logfile: Path):
    """Launch a subprocess and tail its output to a log file."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )
    tail_process_output(process, logfile, name)
    return process
def check_dependencies():
    """Check if required dependencies are installed"""
    import importlib.util

    required_packages = ["fastapi", "uvicorn", "gradio", "requests"]

    for package in required_packages:
        if importlib.util.find_spec(package) is None:
            print(f"❌ {package} not found")
            print("Run: pip install -r requirements.txt")
            return False

    print("✅ All dependencies are installed")
    return True


def check_environment():
    """Check if required environment variables are set"""
    required_vars = ["PINECONE_API_KEY", "PINECONE_ASSISTANT_HOST"]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var) or "your_" in os.getenv(var, ""):
            missing_vars.append(var)

    if missing_vars:
        msg = (
            f"❌ Missing or incomplete environment variables: "
            f"{', '.join(missing_vars)}"
        )
        print(msg)
        print("Please update your .env file with the correct values")
        return False

    print("✅ Environment variables are configured")
    return True


def start_api_server():
    """Start the FastAPI server with proper output handling"""
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", 8000))
    log_dir = create_log_directory()

    print(f"🚀 Starting FastAPI server on {api_host}:{api_port}")
    print(f"📝 API logs will be written to: {log_dir}/api_server.log")

    # Start uvicorn server
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.web.bitcoin_assistant_api:app",
        "--host",
        api_host,
        "--port",
        str(api_port),
        *(
            []
            if os.getenv("API_RELOAD", "false").lower() not in {"1", "true"}
            else ["--reload"]
        ),
    ]

    process = launch_subprocess("API", cmd, log_dir / "api_server.log")
    return process


def start_gradio_ui():
    """Start the Gradio UI with proper output handling"""
    ui_host = os.getenv("UI_HOST", "0.0.0.0")
    ui_port = int(os.getenv("UI_PORT", 7860))
    log_dir = create_log_directory()

    print(f"🎨 Starting Gradio UI on {ui_host}:{ui_port}")
    print(f"📝 UI logs will be written to: {log_dir}/gradio_ui.log")

    # Start Gradio UI with host and port arguments
    cmd = [
        sys.executable,
        "src/web/bitcoin_assistant_ui.py",
        "--host",
        ui_host,
        "--port",
        str(ui_port),
    ]

    process = launch_subprocess("UI", cmd, log_dir / "gradio_ui.log")
    return process


def wait_for_api(api_process, max_attempts=30):
    """Wait for API to be ready, checking if process has exited"""
    import requests

    api_host = os.getenv("API_HOST", "localhost")
    api_url = f"http://{api_host}:{os.getenv('API_PORT', 8000)}/health"

    for attempt in range(max_attempts):
        # Check if the API process has exited
        if api_process.poll() is not None:
            print(f"❌ API process exited with code {api_process.returncode}")
            return False

        try:
            response = requests.get(api_url, timeout=2)
            if response.status_code == 200:
                print("✅ API server is ready!")
                return True
        except Exception:
            pass

        print(f"⏳ Waiting for API server... ({attempt + 1}/{max_attempts})")
        time.sleep(2)

    print("❌ API server failed to start within timeout")
    return False


def main():
    """Main launcher function"""
    print("🪙 Bitcoin Knowledge Assistant Launcher")
    print("=" * 50)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Check environment
    if not check_environment():
        sys.exit(1)

    # Start API server
    api_process = start_api_server()

    # Wait for API to be ready (now checks if process exited)
    if not wait_for_api(api_process):
        api_process.terminate()
        sys.exit(1)

    # Start Gradio UI
    ui_process = start_gradio_ui()

    print("\n🎉 Bitcoin Knowledge Assistant is running!")
    print("=" * 50)
    print(f"📡 API Server: http://localhost:{os.getenv('API_PORT', 8000)}")
    print("🌐 Web UI: http://localhost:" + str(os.getenv('UI_PORT', 7860)))
    print(f"📚 API Docs: http://localhost:{os.getenv('API_PORT', 8000)}/docs")
    print(f"📝 Logs: ./logs/ directory")
    print("\nPress Ctrl+C to stop both servers")

    def signal_handler(sig, frame):
        print("\n🛑 Shutting down servers...")
        api_process.terminate()
        ui_process.terminate()

        # Wait for processes to terminate
        api_process.wait()
        ui_process.wait()

        print("✅ Servers stopped successfully")
        sys.exit(0)

    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Wait for both processes
    while api_process.poll() is None and ui_process.poll() is None:
        time.sleep(1)


if __name__ == "__main__":
    main()
