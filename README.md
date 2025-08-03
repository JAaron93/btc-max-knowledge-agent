# 🪙 Bitcoin Knowledge Assistant Web Application

A modern web application that provides intelligent Bitcoin and blockchain knowledge using **Pinecone Assistant** with smart document retrieval.

## 🚀 Features

### Core Functionality
- **Session Management** with unique session IDs for conversation isolation
- **Conversation Context** maintained within individual user sessions
- **Automatic Session Cleanup** to prevent memory leaks and ensure privacy
- **Interactive Web UI** built with Gradio
- **RESTful API** powered by FastAPI
- **Intelligent Document Retrieval** from Pinecone Assistant
- **Automatic Source Selection** - no manual configuration needed
- **Production Ready** with Gunicorn and Nginx support
- **Real-time Status Monitoring**
- **Source Attribution** for all answers
- **URL Metadata Storage** with comprehensive validation and tracking

### Security & Reliability
- **Multi-Layer Security System** with input validation, prompt injection detection, and rate limiting
- **Context-Aware Security Monitoring** with dynamic severity assessment
- **Comprehensive Audit Logging** for security events and system monitoring
- **Robust Error Handling** with graceful degradation and retry mechanisms
- **Path Handling Improvements** with proper normalization and existence checking

### Developer Experience
- **Proper Package Structure** with editable installation support
- **Improved Test Framework** with automatic path setup and environment control
- **Enhanced Documentation** with comprehensive guides and examples
- **Better IDE Support** through standard import structure
- **CI/CD Ready** with proper dependency management and test discovery

## 🆕 What's New

### Recent Improvements

#### Security Enhancements
- **Advanced Security Middleware**: Multi-layer protection with input validation, prompt injection detection, and rate limiting
- **Context-Aware Severity Assessment**: Dynamic security event severity based on threat context and frequency
- **Comprehensive Security Monitoring**: Real-time anomaly detection with configurable alerting
- **Enhanced Error Handling**: Graceful degradation with detailed security event logging

#### Development Experience
- **Proper Package Installation**: Use `pip install -e ".[dev]"` for editable installation with development tools
- **Improved Test Framework**: Automatic path setup with environment variable control (`TEST_UTILS_AUTO_SETUP`)
- **Better Import Structure**: Standard absolute imports instead of sys.path manipulation
- **Enhanced Path Handling**: Robust path normalization with existence checking and error handling

#### System Reliability
- **Dynamic Status Endpoints**: Real-time system health monitoring with actual component status
- **Improved Error Recovery**: Better handling of missing directories and configuration issues
- **Enhanced Documentation**: Comprehensive guides for security, testing, and development workflows

#### Session Management
- **User Isolation**: Each user gets a unique session ID ensuring conversation privacy
- **Cryptographically Secure IDs**: 32-character hex strings using UUID4 + timestamp + secure random bytes
- **Session Ownership Validation**: Users can only access and delete their own sessions
- **Rate Limiting**: Anti-enumeration protection with different limits per endpoint type
- **Conversation Context**: Maintains conversation history within sessions for better continuity
- **Automatic Expiry**: Sessions expire after 60 minutes of inactivity with automatic cleanup (configurable via SESSION_TTL_MINUTES environment variable)
- **No Authentication Required**: Sessions are created automatically without user registration
- **Browser Persistence**: Session IDs stored in HTTP-only cookies with Secure and SameSite=Lax attributes for seamless experience
- **Security Logging**: Comprehensive logging of all session access attempts and violations
- **Attack Prevention**: Protects against hijacking, enumeration, CSRF, and cross-user access
- **Memory Management**: Expired sessions are automatically cleaned up to prevent memory leaks

#### Admin Security System
- **Token-Based Authentication**: Secure bearer token authentication for admin access
- **PBKDF2 Password Hashing**: 100,000 iterations with cryptographically secure salt
- **Session Management**: Time-based token expiry (24h) and inactivity timeout (30min)
- **Brute Force Protection**: Login delays and comprehensive attempt logging
- **IP Address Monitoring**: All admin activities logged with client IP addresses
- **Endpoint Protection**: All admin endpoints require valid authentication
- **Secure Token Generation**: 256-bit entropy tokens with automatic cleanup
- **Production Ready**: Configurable credentials and enterprise-grade security

## 📋 Prerequisites

- Python 3.8+
- Pinecone Assistant with uploaded Bitcoin documents
- Virtual environment (recommended)

## 🛠️ Installation

### Development Setup

1. **Clone and setup environment:**
   ```bash
   git clone <your-repo>
   cd btc-max-knowledge-agent
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install the package with development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```
   
   This installs the `btc_max_knowledge_agent` package in editable mode with all development tools including:
   - `pytest` for testing
   - `black` for code formatting
   - `isort` for import sorting
   - `mypy` for type checking
   - `pylint` for code analysis
   - `pytest-cov` for coverage reports

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

   Required variables:
   ```env
   PINECONE_API_KEY="your_pinecone_api_key"
   PINECONE_ASSISTANT_HOST="https://prod-1-data.ke.pinecone.io/mcp/assistants/genius"
   ELEVEN_LABS_API_KEY="your_elevenlabs_api_key"
   ```

### Production Setup

For production deployments, install without development dependencies:

```bash
pip install .
```

**Note**: Use `pip install -e .` (editable install) for development work where you need code changes to be immediately reflected, while `pip install .` (non-editable) is suitable for production deployments where the code is stable.

### Benefits of Editable Installation

Installing with `pip install -e ".[dev]"` provides several advantages:

- **Proper Import Structure**: Use standard absolute imports instead of sys.path manipulation
- **IDE Support**: Better code completion and navigation
- **Test Discovery**: pytest can find and run tests reliably
- **Development Tools**: Access to formatting, linting, and type checking
- **Consistent Environment**: Same setup across development, testing, and CI/CD

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

### Session Management Endpoints

- `POST /session/new` - Create a new session (rate limited: 10/min per IP)
- `GET /session/{session_id}` - Get session information (requires ownership, rate limited: 20/min per IP)
- `DELETE /session/{session_id}` - Delete a session (requires ownership, rate limited: 5/min per IP)

### Admin Endpoints (Authentication Required)

- `POST /admin/login` - Admin authentication
- `POST /admin/logout` - Revoke admin session
- `GET /admin/sessions/stats` - Get session statistics (admin only)
- `GET /admin/sessions/rate-limits` - Get rate limiter statistics (admin only)
- `POST /admin/sessions/cleanup` - Force cleanup expired sessions (admin only)
- `GET /admin/sessions/list` - List all active sessions (admin only)
- `DELETE /admin/sessions/{session_id}` - Force delete any session (admin only)
- `GET /admin/auth/stats` - Get admin authentication statistics (admin only)
- `GET /admin/health` - Admin health check (admin only)

#### Session Security

Session endpoints include comprehensive security measures:

**Authentication & Authorization:**
- **HTTP-only Cookies**: Secure session identification
- **Ownership Validation**: Users can only access/delete their own sessions
- **Cross-User Protection**: Prevents unauthorized session access

**Rate Limiting (Anti-Enumeration):**
- **Session Info**: 20 requests per minute per IP
- **Session Delete**: 5 requests per minute per IP  
- **Session Create**: 10 requests per minute per IP

**Cryptographically Secure Session IDs:**
- **Multiple Entropy Sources**: UUID4 + nanosecond timestamp + secure random bytes
- **SHA-256 Hashing**: 32-character hex strings for consistent format
- **Collision Detection**: Automatic regeneration on extremely rare collisions

**Security Logging:**
- **Access Attempts**: All session access attempts logged with IP addresses
- **Rate Limit Violations**: Automatic logging of suspicious activity
- **Ownership Violations**: Detailed logging of unauthorized access attempts

**Error Handling:**
- `401 Unauthorized`: Missing or empty session cookie
- `403 Forbidden`: Session ownership violation
- `404 Not Found`: Session doesn't exist or expired
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server-side security errors

### Query Example

```bash
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "What is Bitcoin?",
       "session_id": "optional-session-id"  // Optional: omit to create new session
     }'
```

Response:
```json
{
  "answer": "Bitcoin is a peer-to-peer electronic cash system...",
  "sources": [
    {"name": "bitcoin_fundamentals.txt", "type": "document"},
    {"name": "Bitcoin Guide.pdf", "type": "document"}
  ],
  "session_id": "abc123-def456-ghi789",
  "conversation_turn": 1
}
```

### Session Management Examples

```bash
# Create a new session (returns session cookie)
curl -c cookies.txt -X POST "http://localhost:8000/session/new"

# Get session information (requires session cookie)
curl -b cookies.txt "http://localhost:8000/session/{session_id}"

# Delete session (requires session cookie and ownership)
curl -b cookies.txt -X DELETE "http://localhost:8000/session/{session_id}"

# Attempting to access another user's session returns 403 Forbidden
curl -b other_cookies.txt "http://localhost:8000/session/{different_session_id}"
```

### Admin API Examples

```bash
# Admin login
curl -X POST "http://localhost:8000/admin/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "your_password"}'

# Get session statistics (admin only)
curl -H "Authorization: Bearer your_admin_token" \
     "http://localhost:8000/admin/sessions/stats"

# Force cleanup expired sessions (admin only)
curl -X POST \
     -H "Authorization: Bearer your_admin_token" \
     "http://localhost:8000/admin/sessions/cleanup"

# List all active sessions (admin only)
curl -H "Authorization: Bearer your_admin_token" \
     "http://localhost:8000/admin/sessions/list"
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

#### Core Application Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PINECONE_API_KEY` | Pinecone API key | Required |
| `PINECONE_ASSISTANT_HOST` | Assistant endpoint | Required |
| `ELEVEN_LABS_API_KEY` | ElevenLabs API key for text-to-speech functionality ([Get API key](https://elevenlabs.io/docs/api-reference/authentication)) | Required |
| `API_HOST` | API server host | `0.0.0.0` (all interfaces) |
| `API_PORT` | API server port | 8000 |
| `UI_HOST` | UI server host | `0.0.0.0` (all interfaces) |
| `UI_PORT` | UI server port | 7860 |
| `ALLOW_LOCALHOST_URLS` | Allow localhost URLs in testing | true |

#### Security Configuration Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECURITY_RATE_LIMIT_PER_MINUTE` | Rate limit per client per minute | 100 |
| `SECURITY_MAX_QUERY_LENGTH` | Maximum query length in characters | 4096 |
| `SECURITY_INJECTION_DETECTION_THRESHOLD` | Prompt injection detection threshold (0.0-1.0) | 0.8 |
| `SECURITY_MONITORING_ENABLED` | Enable security event monitoring | true |
| `SECURITY_LOG_RETENTION_DAYS` | Security log retention period | 90 |
| `SECURITY_ALERT_RESPONSE_TIME_SECONDS` | Alert response time threshold | 10 |

#### Development and Testing Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TEST_UTILS_AUTO_SETUP` | Auto-setup src path in test utilities | 1 (enabled) |
| `FASTAPI_DEBUG` | Enable FastAPI debug mode | false |
| `LOG_LEVEL` | Application log level | INFO |

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

### Core Security Components

- **Input validation** with Pydantic models and comprehensive sanitization
- **Rate limiting** through Gunicorn configuration and token bucket algorithms
- **Security headers** in Nginx configuration
- **Environment variable protection** with secure configuration management

### Advanced Security System

The application includes a comprehensive security middleware system with:

#### Multi-Layer Security Validation
- **Input Sanitization**: Prevents XSS, SQL injection, and other malicious input
- **Prompt Injection Detection**: AI-powered detection of prompt manipulation attempts
- **Rate Limiting**: Configurable per-client and system-wide rate limits
- **Authentication**: Secure API key validation with caching

#### Security Event Monitoring
- **Real-time Monitoring**: Tracks security events with contextual severity levels
- **Anomaly Detection**: Identifies unusual patterns and potential threats
- **Alert System**: Configurable alerting based on threat levels and frequency
- **Audit Logging**: Comprehensive security event logging for compliance

#### Dynamic Severity Assessment
The security system uses context-aware severity determination:

```python
# Example: Rate limiting severity based on context
context = {
    'frequency': 'high',
    'attempt_count': 150,
    'user_type': 'anonymous'
}

# Returns SecuritySeverity.ERROR (escalated from WARNING)
severity = get_contextual_severity_for_event_type(
    SecurityEventType.RATE_LIMIT_EXCEEDED, 
    context
)
```

#### Security Configuration
Security settings can be customized via environment variables:

```env
# Security thresholds
SECURITY_RATE_LIMIT_PER_MINUTE=100
SECURITY_MAX_QUERY_LENGTH=4096
SECURITY_INJECTION_DETECTION_THRESHOLD=0.8

# Monitoring settings
SECURITY_MONITORING_ENABLED=true
SECURITY_LOG_RETENTION_DAYS=90
SECURITY_ALERT_RESPONSE_TIME_SECONDS=10
```

For detailed security configuration, see `src/security/README.md`.

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

### Prerequisites

Ensure you've installed the package with development dependencies:

```bash
pip install -e ".[dev]"
```

### Running Tests

#### Basic Test Execution

```bash
# Run all tests with pytest
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Run tests matching a pattern (e.g., all URL validation tests)
pytest -k "test_url" -v

# Run a specific test file
pytest tests/test_security_middleware.py -v
```

#### Environment-Specific Test Runs

For development (with localhost URLs allowed):

```bash
export ALLOW_LOCALHOST_URLS=true
pytest tests/ -v
```

For production (with localhost URLs blocked):

```bash
export ALLOW_LOCALHOST_URLS=false
pytest tests/ -v
```

#### Test Environment Control

The test utilities support environment variable control:

```bash
# Disable automatic src path setup (useful for CI/CD)
export TEST_UTILS_AUTO_SETUP=0
pytest tests/ -v

# Enable automatic setup (default)
export TEST_UTILS_AUTO_SETUP=1
pytest tests/ -v
```

### Testing Individual Components

#### Security System Tests
```bash
# Test security middleware
pytest tests/test_security_middleware.py -v

# Test security models and severity functions
pytest tests/test_security_models.py -v

# Test input validation
pytest tests/test_input_validation.py -v
```

#### Core Functionality Tests
```bash
# Test text cleaning
pytest tests/test_clean_mcp_response.py -v

# Test API health
pytest tests/test_api_health.py -v

# Test query functionality
pytest tests/test_query_endpoint.py -v

# Test multi-tier caching
pytest tests/test_multi_tier_cache.py -v
```

#### Integration Tests
```bash
# Test URL metadata integration
pytest tests/test_url_metadata_integration.py -v

# Test backward compatibility
pytest tests/test_backward_compatibility_enhanced.py -v

# Run integration validation
python validate_integration.py
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
pytest tests/test_backward_compatibility_enhanced.py -v

# Run integration tests
python validate_integration.py

# Run complete demo
python demo_url_metadata_complete.py
```

### Development Workflow Improvements

#### Proper Import Structure
With the editable installation, you can use standard absolute imports:

```python
# ✅ Recommended (with pip install -e ".[dev]")
from btc_max_knowledge_agent.security.models import SecurityEvent
from btc_max_knowledge_agent.utils.config import Config

# ❌ Avoid (old sys.path manipulation)
import sys
sys.path.insert(0, 'src')
from security.models import SecurityEvent
```

#### Test Discovery and Execution
The improved test utilities provide:

- **Automatic Path Setup**: Tests can import modules without manual path manipulation
- **Environment Control**: Use `TEST_UTILS_AUTO_SETUP` to control automatic setup
- **Graceful Error Handling**: Tests work even when src directory structure varies
- **Better IDE Support**: Proper imports enable better code completion and navigation

#### CI/CD Integration
For continuous integration environments:

```yaml
# Example GitHub Actions workflow
- name: Install dependencies
  run: |
    pip install -e ".[dev]"

- name: Run tests
  run: |
    pytest tests/ --cov=src --cov-report=xml

- name: Run security tests
  run: |
    pytest tests/test_security_*.py -v

- name: Validate integration
  run: |
    python validate_integration.py
```

## 🔍 Troubleshooting

### Common Issues

1. **Installation Problems**
   ```bash
   # If you get import errors, ensure proper installation
   pip install -e ".[dev]"
   
   # For test import issues, check environment variable
   export TEST_UTILS_AUTO_SETUP=1
   ```

2. **API Connection Failed**
   - Check if Pinecone Assistant endpoint is correct
   - Verify API keys in `.env` file
   - Ensure Pinecone Assistant has uploaded documents
   - Review security logs for blocked requests

3. **UI Not Loading**
   - Verify API server is running on port 8000
   - Check firewall settings
   - Review console logs for errors
   - Check if security middleware is blocking requests

4. **Empty Responses**
   - Confirm documents are uploaded to Pinecone Assistant
   - Check if assistant is processing files
   - Verify question relevance to knowledge base
   - Review rate limiting logs

5. **Security-Related Issues**
   ```bash
   # Check security event logs
   tail -f logs/security_events.log
   
   # Adjust security thresholds if needed
   export SECURITY_RATE_LIMIT_PER_MINUTE=200
   export SECURITY_INJECTION_DETECTION_THRESHOLD=0.9
   ```

6. **Test Import Failures**
   ```bash
   # Disable automatic path setup if causing issues
   export TEST_UTILS_AUTO_SETUP=0
   
   # Or ensure src directory exists and is properly structured
   ls -la src/
   ```

### Debug Mode

Enable comprehensive debugging:
```bash
# Enable FastAPI debug mode
export FASTAPI_DEBUG=true

# Enable security debug logging
export LOG_LEVEL=DEBUG

# Enable test utilities debug
export TEST_UTILS_AUTO_SETUP=1

# Start with debug logging
uvicorn src.web.bitcoin_assistant_api:app --reload --log-level debug
```

### Health Checks

Use the enhanced health endpoints:
```bash
# Check overall system health
curl http://localhost:8000/health

# Check security system status
curl http://localhost:8000/security/health

# Check security configuration
curl http://localhost:8000/security/status
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