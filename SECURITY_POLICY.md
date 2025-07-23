# URL Validation Security Policy

## Policy Statement

This document outlines the URL validation policy for the Bitcoin Knowledge Assistant. The policy aims to balance security with the flexibility needed for development and testing environments.

### Development and Testing Environments
- **Allowed URLs**: Localhost and private IPs (127.0.0.1, ::1) are permitted to facilitate development and CI/CD processes.
- **Configuration**: Enable via the environment variable `ALLOW_PRIVATE_URLS=true`.
- **Monitoring**: Localhost URL usage should be logged for oversight.
- **Targeted**: These rules apply to local development, CI/CD pipelines, and staging environments.

### Production Environment
- **Blocked URLs**: The following IP ranges are strictly prohibited:
  - **IPv4 Loopback**: 127.0.0.0/8 (localhost addresses)
  - **IPv4 Private Class A**: 10.0.0.0/8 (private network range)
  - **IPv4 Private Class B**: 172.16.0.0/12 (private network range)
  - **IPv4 Private Class C**: 192.168.0.0/16 (private network range)
  - **IPv6 Loopback**: ::1/128 (localhost address)
  - **IPv6 Unique Local**: fc00::/7 (private IPv6 addresses)
  - **IPv6 Link-Local**: fe80::/10 (link-local addresses)
- **Configuration**: Default set with `ALLOW_PRIVATE_URLS=false`.
- **Enforcement**: Attempts to use blocked URLs will be logged and alerts generated.
- **Rationale**: Prevents SSRF attacks and unauthorized internal network accesses by blocking internal and loopback IP addresses ensuring only external and secure URLs are accessible in production.

## Technical Implementation

1. **Code Updates**: Refactor the `is_secure_url()` function to respect the `ALLOW_PRIVATE_URLS` environment setting.
2. **Configuration**: Establish environment-aware toggles that default to security-first settings.
3. **Testing**: Update unit tests to validate behavior under different environment settings.
4. **Documentation**: Capture these policies in both technical and user-facing documentation.

## Responsibilities
- **Security Team**: Approves policies and oversees compliance.
- **Development Team**: Implements configurations and code changes.
- **QA Team**: Validates functionality across environments.
- **Product Owner**: Aligns policy with business needs and risk tolerance.

## Risk Assessment
- **Security Implications**: Blocking localhost/IPs improves defenses against tunnel-based attacks.
- **Development Needs**: Flexibility necessary to maintain robust CI/CD processes without impediments.

## Implementation Timeline
1. Draft Policy Review with Stakeholders: Within 7 days of policy approval
2. Code Implementation: Within 14 days of stakeholder approval
3. Environment Testing: Within 21 days of code implementation completion
4. Rollout and Monitoring: Within 30 days of successful testing validation

## Monitoring and Compliance

### Log Management
- **Retention Period**: URL validation logs must be retained for 90 days minimum
- **Storage Location**: Centralized secure log server with encrypted storage and access controls
- **Log Format**: Structured JSON logs including timestamp, source IP, requested URL, validation result, and correlation ID
- **Access Control**: Restricted to security team, designated DevOps personnel, and audit processes

### Alerting Thresholds
- **Critical Alert**: Trigger PagerDuty if more than 10 blocked URL attempts per hour from a single source
- **Warning Alert**: Email security team if more than 50 total URL validation failures per hour across all sources
- **Monitoring Alert**: Slack notification for any private IP access attempts in production environment
- **Audit Alert**: Weekly summary report of all URL validation events to security team

### Compliance Monitoring
- **Daily Checks**: Automated verification that `ALLOW_PRIVATE_URLS` configuration matches environment expectations
- **Weekly Audits**: Review blocked URL attempt patterns and update IP blocklists as needed
- **Monthly Reports**: Comprehensive analysis of URL validation trends and security posture assessment
- **Quarterly Reviews**: Policy effectiveness evaluation and stakeholder review of security metrics

