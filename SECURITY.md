# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

### How to Report

**Preferred**: Use [GitHub's Private Vulnerability Reporting](https://github.com/fvadicamo/yt-dlp-api/security/advisories/new)

**Alternative**: Open a [security advisory](https://github.com/fvadicamo/yt-dlp-api/security/advisories) or contact the maintainer directly.

**Do NOT** open a public GitHub issue for security vulnerabilities.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Resolution Timeline**: Depends on severity
  - Critical: 24-48 hours
  - High: 7 days
  - Medium: 30 days
  - Low: Next release

### Security Best Practices

When using this API:

1. **API Keys**: Store securely, never commit to repositories
2. **Cookies**: YouTube cookies contain sensitive session data - protect accordingly
3. **Network**: Use HTTPS in production, consider VPN for sensitive deployments
4. **Docker**: Run containers with minimal privileges (already configured as non-root)
5. **Updates**: Keep dependencies updated, monitor for CVEs

## Known Security Measures

This project implements:

- API key authentication for all endpoints
- Input validation against injection attacks
- Path traversal prevention
- Non-root container execution
- Sensitive data redaction in logs
- Rate limiting to prevent abuse
