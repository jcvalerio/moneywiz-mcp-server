# Security Policy

## Supported Versions

Security fixes are provided for the latest released version of `moneywiz-mcp-server`.

## Reporting a Vulnerability

Please do **not** open a public issue for security vulnerabilities.

Use GitHub's private vulnerability reporting from the repository **Security** tab, or create a private security advisory if you have maintainer access.

When reporting, please include:

- A clear description of the issue
- Steps to reproduce, if available
- Potential impact
- Affected versions or commit ranges
- Any suggested mitigation

I will acknowledge valid reports as soon as possible and coordinate a fix before public disclosure.

## Scope

This project is a read-only MCP server for local MoneyWiz data. Security-sensitive areas include:

- Handling of local database paths
- Protection of financial data in logs/errors
- Dependency vulnerabilities
- MCP tool input validation
- CI/CD and release configuration
