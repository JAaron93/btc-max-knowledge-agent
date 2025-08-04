# Admin Authentication Setup

This document explains how to configure admin authentication for the Bitcoin Knowledge Assistant.

## Environment Variables

Add these environment variables to your `.env` file:

```bash
# Admin Authentication Configuration
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD_HASH=your_hashed_password
ADMIN_SECRET_KEY=your_secret_key_64_hex_characters_32_bytes

# Optional: Admin session configuration
ADMIN_TOKEN_EXPIRY_HOURS=24
ADMIN_SESSION_TIMEOUT_MINUTES=30
```

## Password Hash Generation

**Requirements**: Install the argon2-cffi library:
```bash
pip install argon2-cffi
```

To generate a secure password hash, use the provided utility:

```python
#!/usr/bin/env python3
"""Generate admin password hash"""

import secrets
import getpass
from argon2 import PasswordHasher

def hash_password(password: str) -> str:
    """Hash password using Argon2id (OWASP recommended)"""
    hasher = PasswordHasher()
    return hasher.hash(password)

if __name__ == "__main__":
    password = getpass.getpass("Enter admin password: ")
    password_hash = hash_password(password)
    
    print(f"\nAdd this to your .env file:")
    print(f"ADMIN_PASSWORD_HASH={password_hash}")
    
    # Generate secret key (64 hex characters = 32 bytes)
    secret_key = secrets.token_hex(32)
    print(f"ADMIN_SECRET_KEY={secret_key}")
```

## Credential Setup (All Environments)

**🔒 Security Best Practice**: Always generate unique credentials for each environment.

Run the credential generator script to create secure admin credentials:

```bash
python3 scripts/generate_admin_hash.py
```

This script will:
- Prompt you to create a secure username and password
- Generate a cryptographically secure password hash
- Create a random secret key
- Optionally save credentials to `.env.admin` file with proper permissions

**Never use default or weak credentials in any environment.**

## Admin API Usage

### 1. Login

```bash
curl -X POST "http://localhost:8000/admin/login" \
     -H "Content-Type: application/json" \
     -d '{
       "username": "your_admin_username",
       "password": "your_admin_password"
     }'
```

Response:
```json
{
  "access_token": "your_access_token_here",
  "token_type": "bearer",
  "expires_in_hours": 24,
  "message": "Admin authentication successful"
}
```

### 2. Use Admin Endpoints

First, export the token to an environment variable to avoid exposing it in shell history:

```bash
# Extract token from login response (if saved to file)
export ADMIN_TOKEN=$(jq -r '.access_token' login_response.json)

# Or set it directly (replace with your actual token)
export ADMIN_TOKEN="your_access_token_here"
```

> **Security Note**: Using environment variables prevents sensitive tokens from being stored in shell history, reducing the risk of accidental token exposure.

Then use the environment variable in your curl commands:

```bash
# Get session statistics
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     "http://localhost:8000/admin/sessions/stats"

# Cleanup expired sessions
curl -X POST \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     "http://localhost:8000/admin/sessions/cleanup"

# Get rate limit statistics
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     "http://localhost:8000/admin/sessions/rate-limits"
```

### 3. Logout

```bash
curl -X POST \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     "http://localhost:8000/admin/logout"
```

## Admin Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/login` | POST | Admin authentication |
| `/admin/logout` | POST | Revoke admin session |
| `/admin/session/info` | GET | Get current admin session info |
| `/admin/sessions/stats` | GET | Get session statistics |
| `/admin/sessions/cleanup` | POST | Force cleanup expired sessions |
| `/admin/sessions/rate-limits` | GET | Get rate limiter statistics |
| `/admin/sessions/list` | GET | List all active sessions |
| `/admin/sessions/{session_id}` | DELETE | Force delete any session |
| `/admin/auth/stats` | GET | Get admin auth statistics |
| `/admin/health` | GET | Admin health check |

## Security Features

### Authentication
- **Token-based**: Secure bearer token authentication
- **Password Hashing**: Argon2id with automatic salt generation (OWASP recommended)
- **Session Management**: Time-based token expiry and inactivity timeout

### Authorization
- **Admin-only Access**: All admin endpoints require valid admin token
- **IP Logging**: All admin actions logged with IP addresses
- **Session Validation**: Tokens validated on every request

### Security Measures
- **Brute Force Protection**: Login attempts include delay
- **Session Timeout**: Automatic logout after inactivity
- **Token Expiry**: Tokens expire after 24 hours (configurable)
- **Secure Token Generation**: Cryptographically secure random tokens

## Production Deployment

### 1. Set Strong Credentials
```bash
# Generate strong credentials using the provided script
python3 scripts/generate_admin_hash.py

# The script will output environment variables like:
export ADMIN_USERNAME="your_admin_username"
export ADMIN_PASSWORD_HASH="$argon2id$v=19$m=65536,t=3,p=4$..."
export ADMIN_SECRET_KEY="64_character_random_hex_string_32_bytes"
```

### 2. Network Security
- Use HTTPS in production
- Restrict admin endpoint access by IP if possible
- Consider using a reverse proxy with additional authentication

### 3. Monitoring
- Monitor admin login attempts
- Set up alerts for failed authentication
- Regularly review admin access logs

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check if Authorization header is included
   - Verify token format: `Bearer <token>`
   - Ensure token hasn't expired

2. **403 Forbidden**
   - Token may be expired or invalid
   - Try logging in again to get a new token

3. **Default Password Warning**
   - Set `ADMIN_PASSWORD_HASH` environment variable
   - Use the credential generation script: `python3 scripts/generate_admin_hash.py`

4. **Invalid Secret Key Format**
   - Ensure `ADMIN_SECRET_KEY` is exactly 64 hex characters (32 bytes)
   - Generate with: `python3 -c "import secrets; print(secrets.token_hex(32))"`

### Debug Mode

Enable debug logging to troubleshoot authentication issues:

```python
import logging
logging.getLogger("src.web.admin_auth").setLevel(logging.DEBUG)
```

## Security Best Practices

1. **Generate Unique Credentials**: Always use the credential generator script for all environments
2. **Use Strong Passwords**: Minimum 12 characters with mixed case, numbers, symbols
3. **Rotate Tokens**: Regularly update admin credentials
4. **Monitor Access**: Review admin access logs regularly
5. **Limit Access**: Restrict admin endpoints to trusted networks
6. **Use HTTPS**: Always use encrypted connections in production