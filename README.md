# 🪙 Bitcoin Knowledge Assistant Web Application

A modern web application that provides intelligent Bitcoin and blockchain knowledge using **Pinecone Assistant** with smart document retrieval.

## 🚀 Features

- **Interactive Web UI** built with Gradio
- **RESTful API** powered by FastAPI
- **Intelligent Document Retrieval** from Pinecone Assistant
- **Automatic Source Selection** - no manual configuration needed
- **Production Ready** with Gunicorn and Nginx support
- **Real-time Status Monitoring**
- **Source Attribution** for all answers

## 📋 Prerequisites

- Python 3.8+
- Pinecone Assistant with uploaded Bitcoin documents
- Virtual environment (recommended)

## 🛠️ Installation

1. **Clone and setup environment:**
   ```bash
   git clone <your-repo>
   cd btc-max-knowledge-agent
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

   Required variables:
   ```env
   PINECONE_API_KEY="your_pinecone_api_key"
   PINECONE_ASSISTANT_HOST="https://prod-1-data.ke.pinecone.io/mcp/assistants/genius"
   ```

## 🚀 Quick Start

### Development Mode

Launch both API and UI servers:
```bash
python launch_bitcoin_assistant.py
```

This will start:
- **FastAPI server** on http://localhost:8000
- **Gradio UI** on http://localhost:7860

### Manual Launch

Start API server only:
```bash
uvicorn src.web.bitcoin_assistant_api:app --host 0.0.0.0 --port 8000 --reload
```

Start UI only:
```bash
python src/web/bitcoin_assistant_ui.py
```

## 🏭 Production Deployment

### Using Gunicorn

1. **Start production servers:**
   ```bash
   python deploy_production.py
   ```

2. **Create configuration files:**
   ```bash
   python deploy_production.py --create-configs
   ```

### Using Systemd (Linux)

1. **Create service file:**
   ```bash
   python deploy_production.py --create-configs
   sudo cp bitcoin-assistant.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable bitcoin-assistant
   sudo systemctl start bitcoin-assistant
   ```

2. **Check status:**
   ```bash
   sudo systemctl status bitcoin-assistant
   ```

### Using Nginx (Reverse Proxy)

1. **Install Nginx configuration:**
   ```bash
   sudo cp nginx-bitcoin-assistant.conf /etc/nginx/sites-available/bitcoin-assistant
   sudo ln -s /etc/nginx/sites-available/bitcoin-assistant /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

## 📡 API Endpoints

### Core Endpoints

- `GET /` - API information
- `GET /health` - Health check and status
- `POST /query` - Query Bitcoin knowledge
- `GET /sources` - List available sources
- `GET /docs` - Interactive API documentation

### Query Example

```bash
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "What is Bitcoin?"
     }'
```

Response:
```json
{
  "answer": "Bitcoin is a peer-to-peer electronic cash system...",
  "sources": [
    {"name": "bitcoin_fundamentals.txt", "type": "document"},
    {"name": "Bitcoin Guide.pdf", "type": "document"}
  ]
}
```

## 🎨 Web Interface Features

### Main Interface
- **Question Input** with sample questions
- **Automatic Source Selection** - Pinecone Assistant optimizes retrieval
- **Real-time Responses** with source attribution
- **Clean Formatting** with proper text processing

### System Monitoring
- **API Health Check** - Verify connection status
- **Knowledge Base Info** - List available sources
- **Response Time Monitoring**

### Sample Questions
- "What is Bitcoin and how does it work?"
- "Explain the Lightning Network"
- "What are decentralized applications (dApps)?"
- "Tell me about the GENIUS Act"

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PINECONE_API_KEY` | Pinecone API key | Required |
| `PINECONE_ASSISTANT_HOST` | Assistant endpoint | Required |
| `API_HOST` | API server host | 0.0.0.0 |
| `API_PORT` | API server port | 8000 |
| `UI_HOST` | UI server host | 0.0.0.0 |
| `UI_PORT` | UI server port | 7860 |

### Gunicorn Configuration

The production deployment uses optimized Gunicorn settings:
- **4 workers** for better performance
- **Uvicorn worker class** for async support
- **Request limits** for security
- **Logging** to files in `logs/` directory

## 📊 Monitoring & Logs

### Log Files (Production)
- `logs/access.log` - HTTP access logs
- `logs/error.log` - Application errors

### Health Monitoring
- `GET /health` - API health status
- Pinecone Assistant connection status
- Response time metrics

## 🛡️ Security Features

- **Input validation** with Pydantic models
- **Rate limiting** through Gunicorn configuration
- **Security headers** in Nginx configuration
- **Environment variable protection**

## 🧪 Testing

### Test API Connection
```bash
python test_mcp_tools.py
```

### Test Individual Components
```bash
# Test text cleaning
python clean_mcp_response.py

# Test API health
curl http://localhost:8000/health

# Test query endpoint
curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"question": "What is Bitcoin?"}'
```

## 🔍 Troubleshooting

### Common Issues

1. **API Connection Failed**
   - Check if Pinecone Assistant endpoint is correct
   - Verify API keys in `.env` file
   - Ensure Pinecone Assistant has uploaded documents

2. **UI Not Loading**
   - Verify API server is running on port 8000
   - Check firewall settings
   - Review console logs for errors

3. **Empty Responses**
   - Confirm documents are uploaded to Pinecone Assistant
   - Check if assistant is processing files
   - Verify question relevance to knowledge base

### Debug Mode

Enable debug logging:
```bash
export FASTAPI_DEBUG=true
uvicorn src.web.bitcoin_assistant_api:app --reload --log-level debug
```

## 📈 Performance Optimization

### Production Recommendations

1. **Use Gunicorn** with multiple workers
2. **Enable Nginx** for static file serving and caching
3. **Set up SSL/TLS** for HTTPS
4. **Configure monitoring** with tools like Prometheus
5. **Use Redis** for caching frequent queries

### Scaling Options

- **Horizontal scaling** with load balancers
- **Database caching** for frequent queries
- **CDN integration** for static assets
- **Container deployment** with Docker

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review API documentation at `/docs`
3. Test individual components
4. Check system logs

---

**Built with ❤️ using FastAPI, Gradio, and Pinecone Assistant**