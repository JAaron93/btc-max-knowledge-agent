# URL Validation Security Policy

## Policy Statement

This document outlines the URL validation policy for the Bitcoin Knowledge Assistant. The policy aims to balance security with the flexibility needed for development and testing environments.

### Development and Testing Environments
- **Allowed URLs**: Localhost and private IPs (127.0.0.1, ::1) are permitted to facilitate development and CI/CD processes.
- **Configuration**: Enable via the environment variable `ALLOW_PRIVATE_URLS=true`.
- **Monitoring**: Localhost URL usage should be logged for oversight.
- **Targeted**: These rules apply to local development, CI/CD pipelines, and staging environments.

### Production Environment
- **Blocked URLs**: Localhost, private IPs, and loopback addresses are strictly prohibited.
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
1. Draft Policy Review with Stakeholders: [Date]
2. Code Implementation: [Date]
3. Environment Testing: [Date]
4. Rollout and Monitoring: [Date]

## Monitoring and Compliance
Maintain logs of URL validation events to facilitate audits and provide assurance of policy adherence. Conduct routine checks to ensure configurations remain in line with policy specifications.

