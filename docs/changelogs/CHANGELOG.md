# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Security Overhaul & Production Hardening

#### New Helper Functions & Utilities
- **AdminAuthenticator class** with comprehensive authentication helpers:
  - `_hash_password()` and `_verify_password()` - Argon2id password hashing helpers
  - `_is_ip_locked_out()`, `_record_failed_attempt()`, `_clear_failed_attempts()` - IP-based rate limiting helpers
  - `cleanup_expired_sessions()` - Session cleanup helper with automated background task support
  - `get_admin_stats()` - Admin statistics helper for monitoring
  - `unlock_ip()` - Manual IP unlock helper for admin intervention
  - Background cleanup monitoring helpers: `_should_allow_cleanup_restart()`, `_record_cleanup_restart()`, `get_cleanup_monitoring_state()`

- **SessionManager class** enhancements:
  - `_generate_session_id()` - Cryptographically secure session ID generation helper
  - `_convert_to_charset()` - Custom character set conversion helper for session IDs
  - `_calculate_recursive_size()` - Memory usage calculation helper for session data
  - Configurable session ID length and character set support

- **RateLimiter classes**:
  - `RateLimiter` - Generic sliding window rate limiter helper
  - `SessionRateLimiter` - Specialized rate limiter for different session endpoints
  - `get_session_rate_limiter()` - Thread-safe singleton helper

- **Admin credential generation scripts**:
  - `scripts/generate_admin_credentials.py` - Production-ready credential generator
  - `scripts/generate_admin_hash.py` - Enhanced password validation and hashing utility
  - Password strength validation helpers with comprehensive security checks

#### Internal API Changes
- **Authentication Migration**: Replaced PBKDF2 with Argon2id hashing algorithm (OWASP recommended)
- **Session Management**: 
  - Added configurable session ID generation with multiple entropy sources
  - Enhanced session cleanup with automatic background tasks and restart monitoring
  - Added memory usage tracking and management for conversation history
- **Rate Limiting**: 
  - Implemented IP-based rate limiting for admin endpoints
  - Added specialized rate limiters for different endpoint types
  - Integrated automatic cleanup of old rate limiting data
- **Background Tasks**:
  - Added resilient background cleanup tasks with exponential backoff restart logic
  - Implemented task monitoring and automatic recovery mechanisms
  - Added comprehensive logging and error handling for background operations

#### Security Enhancements
- **Brute-Force Protection**: IP-based lockout mechanism with configurable attempt limits
- **Session Security**: Enhanced session validation with IP consistency checks and timeout management
- **Password Security**: Strong password validation with common password detection and pattern checking
- **Monitoring**: Comprehensive admin statistics and cleanup monitoring for operational visibility

#### Developer Experience Improvements
- **Credential Generation**: Automated `.env.admin` file creation with secure permissions (0o600)
- **Validation Tools**: Enhanced password strength validation with detailed feedback
- **Testing**: Comprehensive test suite for new security features
- **Documentation**: Updated admin setup and security documentation

### Changed
- Admin authentication system completely overhauled for production readiness
- Session management enhanced with configurable security parameters
- Background task management made more resilient with monitoring and auto-recovery

### Security
- **BREAKING**: Admin password hashes must be migrated from PBKDF2 to Argon2id format
- Enhanced protection against brute-force attacks on admin endpoints
- Improved session security with stricter validation and cleanup
- Added comprehensive rate limiting to prevent abuse

### Technical Notes for Contributors
- New helper functions follow consistent naming patterns with leading underscores for internal methods
- All new security functions include comprehensive error handling and logging
- Background tasks use proper asyncio patterns with cancellation support
- Rate limiting uses thread-safe implementations with memory cleanup
- Session ID generation uses multiple entropy sources for maximum security
