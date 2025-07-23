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
- **URL Metadata Storage** with comprehensive validation and tracking

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

2. **Install the package in development mode:**
   ```bash
   pip install -e .
   ```
   
   This installs the `btc_max_knowledge_agent` package in editable mode, allowing you to use proper imports without sys.path manipulation.

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
| `API_HOST` | API server host | `0.0.0.0` (all interfaces) |
| `API_PORT` | API server port | 8000 |
| `UI_HOST` | UI server host | `0.0.0.0` (all interfaces) |
| `UI_PORT` | UI server port | 7860 |
| `ALLOW_LOCALHOST_URLS` | Allow localhost URLs in testing | true |

> **Note**: For production deployments, it's recommended to set host values to specific hostnames or IP addresses and configure appropriate firewall rules.

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

## 🔗 URL Metadata Storage System

### Overview

The URL metadata storage system enhances document retrieval by storing comprehensive metadata about source URLs alongside vector embeddings. This enables proper source attribution, security validation, and tracking of document origins.

### Key Features

- **Comprehensive URL Metadata**: Stores URL, title, domain, path, protocol, and validation status
- **Security Validation**: Prevents malicious URLs, path traversal attacks, and injection attempts
- **Backward Compatibility**: Works seamlessly with existing vectors lacking URL metadata
- **Error Handling**: Robust retry mechanisms with exponential backoff and fallback strategies
- **Monitoring & Logging**: Complete observability with correlation IDs and detailed metrics
- **Performance Optimized**: Batch operations and concurrent processing support

### URL Metadata Schema

```json
{
    "source_url": "https://example.com/document",
    "url_title": "Document Title",
    "url_domain": "example.com",
    "url_path": "/document",
    "url_protocol": "https",
    "url_validated": true,
    "url_validation_timestamp": "2024-01-01T12:00:00Z",
    "url_security_score": 1.0,
    "metadata_version": "2.0"
}
```

### Security Considerations

#### URL Validation
- **Protocol Allowlist**: Only HTTP/HTTPS URLs are allowed
- **Path Traversal Protection**: Blocks URLs containing `../`, `..\\`, or similar patterns
- **Script Injection Prevention**: Rejects URLs with `javascript:`, `data:`, or other dangerous protocols
- **Domain Validation**: Ensures proper domain format and structure
- **Maximum URL Length**: Enforces reasonable limits to prevent buffer overflows

#### Security Checks Performed
1. Protocol validation (HTTP/HTTPS only)
2. Path traversal detection
3. Script injection prevention
4. Domain format validation
5. URL length limits
6. Character encoding validation

### Error Handling and Retry Mechanisms

#### Retry Strategy
- **Exponential Backoff**: Delays between retries increase exponentially
- **Maximum Attempts**: Configurable retry limits (default: 3)
- **Jittered Delays**: Random jitter prevents thundering herd
- **Circuit Breaker**: Prevents cascading failures
- **Fallback Processing**: Graceful degradation when retries fail

#### Error Categories
- **Validation Errors**: Invalid URL format, security violations
- **Network Errors**: Timeouts, connection failures
- **API Errors**: Rate limits, quota exceeded
- **System Errors**: Resource exhaustion, unexpected failures

### Monitoring and Logging

#### Correlation IDs
Every operation is tracked with a unique correlation ID, enabling end-to-end tracing:
```python
import uuid
# logger setup (replace with your actual logger implementation)
import logging
logger = logging.getLogger(__name__)

correlation_id = str(uuid.uuid4())
logger.info(f"Starting operation: url_validation", extra={"correlation_id": correlation_id})
```

#### Metrics Collected
- **URL Events**: Total validation attempts, successes, failures
- **Performance Metrics**: Operation latency, throughput
- **Error Tracking**: Error types, frequencies, patterns
- **System Health**: Resource usage, queue depths

#### Logging Levels
- **INFO**: Normal operations, validations, queries
- **WARNING**: Validation failures, retries, degraded performance
- **ERROR**: Failed operations, exceptions, API errors
- **CRITICAL**: System failures, data corruption risks

### Migration Guide for Existing Deployments

#### Assessment Phase
1. **Inventory Current Vectors**: Identify vectors without URL metadata
2. **Estimate Volume**: Calculate migration scope and timeline
3. **Plan Downtime**: Determine if maintenance window needed

#### Migration Strategies

##### 1. Gradual Migration (Recommended)
```python
# Process vectors in batches
batch_size = 1000
for batch in get_vector_batches(batch_size):
    enrich_with_url_metadata(batch)
    time.sleep(1)  # Rate limiting
```

##### 2. Retroactive Enrichment
```python
# Add URL metadata to existing vectors
for vector in legacy_vectors:
    if not has_url_metadata(vector):
        metadata = extract_url_metadata(vector.source)
        update_vector_metadata(vector.id, metadata)
```

##### 3. Hybrid Approach
- New vectors: Always include URL metadata
- Legacy vectors: Enrich on-demand during queries
- Background job: Gradually migrate remaining vectors

#### Backward Compatibility

The system maintains full compatibility with legacy vectors:
- **Null-safe Operations**: Gracefully handles missing URL fields
- **Version Detection**: Automatically detects metadata schema version
- **Mixed Queries**: Seamlessly queries both legacy and modern vectors
- **Progressive Enhancement**: Adds features without breaking existing functionality

#### Migration Checklist
- [ ] Backup existing vectors
- [ ] Test migration on subset
- [ ] Monitor performance impact
- [ ] Validate data integrity
- [ ] Update monitoring dashboards
- [ ] Document schema changes
- [ ] Train team on new features

### Testing and Validation

#### Test Suites Available
- `test_backward_compatibility_enhanced.py`: Comprehensive compatibility tests
- `test_url_metadata_integration.py`: Integration testing
- `validate_integration.py`: Full system validation
- `demo_url_metadata_complete.py`: End-to-end demonstration

#### Running Tests
```bash
# Run backward compatibility tests
python test_backward_compatibility_enhanced.py

# Run integration validation
python validate_integration.py

# Run with real Pinecone
python validate_integration.py --real-pinecone

# Run complete demo
python demo_url_metadata_complete.py
```

### Performance Considerations

#### Optimization Strategies
- **Batch Processing**: Process multiple URLs in single operations
- **Concurrent Validation**: Parallel URL validation for better throughput
- **Caching**: Cache validation results for frequently accessed URLs
- **Connection Pooling**: Reuse HTTP connections for API calls

#### Performance Metrics
- URL validation: < 50ms per URL
- Batch operations: 100-500 URLs/second
- Query overhead: < 5% with URL metadata
- Memory usage: ~100 bytes per URL metadata entry

### Best Practices

1. **Always Validate URLs**: Never store unvalidated URLs
2. **Use Correlation IDs**: Track operations across systems
3. **Monitor Metrics**: Set up alerts for anomalies
4. **Handle Errors Gracefully**: Implement proper fallbacks
5. **Test Thoroughly**: Validate with both legacy and new data
6. **Document Changes**: Keep schema documentation updated
7. **Plan for Scale**: Design for 10x current volume

## 🧪 Testing

### Running Tests

#### Basic Test Execution

```bash
# Run all tests with verbose output
python run_tests.py --verbose

# Run a specific test file
python run_tests.py tests/test_my_feature.py

# Run tests matching a pattern (e.g., all URL validation tests)
python run_tests.py -k "test_url"

# Run with coverage report
python run_tests.py --cov=src --cov-report=term-missing
```

#### Environment-Specific Test Runs

For development (with localhost URLs allowed):

```bash
export ALLOW_LOCALHOST_URLS=true
python run_tests.py --verbose
```

For production (with localhost URLs blocked):

```bash
export ALLOW_LOCALHOST_URLS=false
python run_tests.py --verbose
```

#### Running Specific Tests

To run a specific test file with detailed output:

```bash
python run_tests.py tests/test_my_feature.py -v
```

To run a specific test class or method:

```bash
python run_tests.py tests/test_my_feature.py::TestMyFeature::test_specific_case -v
```

To run production-specific tests:

```bash
python run_tests.py tests/test_pinecone_url_metadata_prod.py --verbose
```

### Testing Individual Components
```bash
# Test text cleaning
python run_tests.py tests/test_clean_mcp_response.py --verbose

# Test API health
python run_tests.py tests/test_api_health.py --verbose

# Test query functionality
python run_tests.py tests/test_query_endpoint.py --verbose
```

### API Testing
```bash
# Test API health
curl http://localhost:8000/health

# Test query endpoint
curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"question": "What is Bitcoin?"}'
```

### Test URL Validation System

#### Integration Testing Approach
The URL validation system includes both integration and unit tests to ensure comprehensive coverage:

```bash
# Run URL validation integration tests
python -m pytest tests/test_url_metadata_integration.py -v

# Run all URL utility tests
python -m pytest tests/test_url_utils.py -v
```

**Test Coverage Includes:**
- Valid HTTPS URLs
- JavaScript XSS attempts
- Private IP addresses
- Invalid URL formats
- File protocol URLs
- Unicode domain names

#### Testing Strategy

**Integration Tests**
- Verify complete validation pipeline
- Test end-to-end validation
- Validate security-critical logic
- Ensure regression testing coverage

**Unit Tests**
- Fast, predictable test execution
- Test validation coordination logic
- Isolate specific edge cases
- Mock external dependencies

### Test URL Metadata System
```bash
# Test backward compatibility
python -m pytest tests/test_backward_compatibility_enhanced.py -v

# Run integration tests
python validate_integration.py

# Run complete demo
python demo_url_metadata_complete.py
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

4. **URL Validation Failures**
   - Check URL format and protocol
   - Verify no malicious patterns in URL
   - Review security validation logs

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
6. **Enable URL metadata caching** for frequently accessed sources

### Scaling Options

- **Horizontal scaling** with load balancers
- **Database caching** for frequent queries
- **CDN integration** for static assets
- **Container deployment** with Docker
- **URL validation cache** with Redis/Memcached

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly (including URL metadata tests)
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review API documentation at `/docs`
3. Test individual components
4. Check system logs
5. Review URL metadata documentation

---

**Built with ❤️ using FastAPI, Gradio, and Pinecone Assistant**