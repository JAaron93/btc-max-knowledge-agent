#!/usr/bin/env python3
"""
Launch script for Bitcoin Knowledge Assistant Web Application
"""

import os
import sys
import subprocess
import time
import signal
import threading
from dotenv import load_dotenv

load_dotenv()

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fastapi
        import uvicorn
        import gradio
        import requests
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def check_environment():
    """Check if required environment variables are set"""
    required_vars = [
        'PINECONE_API_KEY',
        'PINECONE_ASSISTANT_HOST'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var) or "your_" in os.getenv(var, ""):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing or incomplete environment variables: {', '.join(missing_vars)}")
        print("Please update your .env file with the correct values")
        return False
    
    print("✅ Environment variables are configured")
    return True

def start_api_server():
    """Start the FastAPI server"""
    api_host = os.getenv('API_HOST', '0.0.0.0')
    api_port = int(os.getenv('API_PORT', 8000))
    
    print(f"🚀 Starting FastAPI server on {api_host}:{api_port}")
    
    # Start uvicorn server
    cmd = [
        sys.executable, "-m", "uvicorn",
        "src.web.bitcoin_assistant_api:app",
        "--host", api_host,
        "--port", str(api_port),
        "--reload"
    ]
    
    return subprocess.Popen(cmd)

def start_gradio_ui():
    """Start the Gradio UI"""
    ui_host = os.getenv('UI_HOST', '0.0.0.0')
    ui_port = int(os.getenv('UI_PORT', 7860))
    
    print(f"🎨 Starting Gradio UI on {ui_host}:{ui_port}")
    
    # Start Gradio UI
    cmd = [
        sys.executable, "src/web/bitcoin_assistant_ui.py"
    ]
    
    return subprocess.Popen(cmd)

def wait_for_api(max_attempts=30):
    """Wait for API to be ready"""
    import requests
    
    api_url = f"http://localhost:{os.getenv('API_PORT', 8000)}/health"
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(api_url, timeout=2)
            if response.status_code == 200:
                print("✅ API server is ready!")
                return True
        except:
            pass
        
        print(f"⏳ Waiting for API server... ({attempt + 1}/{max_attempts})")
        time.sleep(2)
    
    print("❌ API server failed to start")
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
    
    # Wait for API to be ready
    if not wait_for_api():
        api_process.terminate()
        sys.exit(1)
    
    # Start Gradio UI
    ui_process = start_gradio_ui()
    
    print("\n🎉 Bitcoin Knowledge Assistant is running!")
    print("=" * 50)
    print(f"📡 API Server: http://localhost:{os.getenv('API_PORT', 8000)}")
    print(f"🌐 Web UI: http://localhost:{os.getenv('UI_PORT', 7860)}")
    print(f"📚 API Docs: http://localhost:{os.getenv('API_PORT', 8000)}/docs")
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
    
    try:
        # Wait for both processes
        while api_process.poll() is None and ui_process.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()