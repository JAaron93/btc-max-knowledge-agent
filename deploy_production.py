#!/usr/bin/env python3
"""
Production deployment script for Bitcoin Knowledge Assistant
Uses Gunicorn for better performance and stability
"""

import os
import signal
import subprocess
import sys
import time

from dotenv import load_dotenv

load_dotenv()


def create_gunicorn_config():
    """Create Gunicorn configuration file"""
    config_content = f"""
# Gunicorn configuration for Bitcoin Knowledge Assistant
bind = "{os.getenv('API_HOST', '0.0.0.0')}:{os.getenv('API_PORT', 8000)}"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
preload_app = True
reload = False

# Logging
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
access_log_format = '%%(h)s %%(l)s %%(u)s %%(t)s "%%(r)s" %%(s)s %%(b)s "%%(f)s" "%%(a)s" %%(D)s'

# Process naming
proc_name = "bitcoin-assistant-api"

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
"""

    os.makedirs("logs", exist_ok=True)

    with open("gunicorn.conf.py", "w") as f:
        f.write(config_content)

    print("✅ Created Gunicorn configuration")


def start_production_api():
    """Start API server with Gunicorn"""
    print("🚀 Starting production API server with Gunicorn...")

    cmd = ["gunicorn", "src.web.bitcoin_assistant_api:app", "-c", "gunicorn.conf.py"]

    return subprocess.Popen(cmd, env=os.environ.copy())


def start_production_ui():
    """Start Gradio UI for production"""
    ui_port = int(os.getenv("UI_PORT", 7860))

    # Check if port is already in use
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("localhost", ui_port))
    sock.close()

    if result == 0:
        print(f"⚠️  Port {ui_port} is already in use. Using port {ui_port + 1} instead.")
        ui_port += 1

    # Set production environment variables
    env = os.environ.copy()
    env["GRADIO_SERVER_NAME"] = os.getenv("UI_HOST", "0.0.0.0")
    env["GRADIO_SERVER_PORT"] = str(ui_port)
    # Log the final port and keep both env vars consistent
    print(f"🎨 Starting production Gradio UI on port {ui_port}...")
    env["UI_PORT"] = str(ui_port)
    cmd = [sys.executable, "src/web/bitcoin_assistant_ui.py"]

    return subprocess.Popen(cmd, env=env)


def check_production_requirements():
    """Check if production requirements are met"""
    import importlib.util

    if importlib.util.find_spec("gunicorn") is not None:
        print("✅ Gunicorn is available")
        print("❌ Gunicorn not found. Installing...")
        print("❌ Gunicorn not found. Please install it before deploying, e.g.:")
        print("    pip install gunicorn")
        return False

    # Check if logs directory exists
    os.makedirs("logs", exist_ok=True)

    return True


def create_systemd_service():
    """Create systemd service file for production deployment"""

    current_dir = os.path.abspath(os.getcwd())
    python_path = sys.executable

    service_content = f"""[Unit]
Description=Bitcoin Knowledge Assistant API
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory={current_dir}
Environment=PATH={os.path.dirname(python_path)}
ExecStart={python_path} {current_dir}/deploy_production.py --daemon
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    with open("bitcoin-assistant.service", "w") as f:
        f.write(service_content)

    print("✅ Created systemd service file: bitcoin-assistant.service")
    print("To install:")
    print("  sudo cp bitcoin-assistant.service /etc/systemd/system/")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable bitcoin-assistant")
    print("  sudo systemctl start bitcoin-assistant")


def create_nginx_config():
    """Create Nginx configuration for reverse proxy"""

    api_port = os.getenv("API_PORT", 8000)
    ui_port = os.getenv("UI_PORT", 7860)

    nginx_config = f"""server {{
    listen 80;
    server_name your-domain.com;  # Replace with your domain
    
    # API endpoints
    location /api/ {{
        proxy_pass http://127.0.0.1:{api_port}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }}
    
    # Gradio UI
    location / {{
        proxy_pass http://127.0.0.1:{ui_port}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for Gradio
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }}
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}}
"""

    with open("nginx-bitcoin-assistant.conf", "w") as f:
        f.write(nginx_config)

    print("✅ Created Nginx configuration: nginx-bitcoin-assistant.conf")
    print("To install:")
    print(
        "  sudo cp nginx-bitcoin-assistant.conf /etc/nginx/sites-available/bitcoin-assistant"
    )
    print(
        "  sudo ln -s /etc/nginx/sites-available/bitcoin-assistant /etc/nginx/sites-enabled/"
    )
    print("  sudo nginx -t")
    print("  sudo systemctl reload nginx")


def main():
    """Main production deployment function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Bitcoin Knowledge Assistant Production Deployment"
    )
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument(
        "--create-configs", action="store_true", help="Create configuration files"
    )
    args = parser.parse_args()

    print("🏭 Bitcoin Knowledge Assistant - Production Deployment")
    print("=" * 60)

    if args.create_configs:
        create_systemd_service()
        create_nginx_config()
        return

    # Check production requirements
    if not check_production_requirements():
        sys.exit(1)

    # Create Gunicorn config
    create_gunicorn_config()

    # Start production servers
    api_process = start_production_api()

    # Wait a bit for API to start
    time.sleep(5)

    ui_process = start_production_ui()

    print("\n🎉 Production Bitcoin Knowledge Assistant is running!")
    print("=" * 60)
    print(f"📡 API Server: http://localhost:{os.getenv('API_PORT', 8000)}")
    print(f"🌐 Web UI: http://localhost:{os.getenv('UI_PORT', 7860)}")
    print(f"📚 API Docs: http://localhost:{os.getenv('API_PORT', 8000)}/docs")
    print("📊 Logs: logs/access.log, logs/error.log")

    if not args.daemon:
        print("\nPress Ctrl+C to stop servers")

        def signal_handler(sig, frame):
            print("\n🛑 Shutting down production servers...")
            api_process.terminate()
            ui_process.terminate()

            api_process.wait()
            ui_process.wait()

            print("✅ Production servers stopped")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        try:
            while api_process.poll() is None and ui_process.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            signal_handler(None, None)
    else:
        print("🔄 Running as daemon...")


if __name__ == "__main__":
    main()
