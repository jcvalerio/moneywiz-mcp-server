# Contributing to MoneyWiz MCP Server

Thank you for your interest in contributing to MoneyWiz MCP Server! This document provides guidelines and workflows for contributing to the project.

## 🤝 Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct:
- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on what is best for the community
- Show empathy towards other community members

## 🔄 Development Workflow

We follow a standard GitHub flow for all contributions:

### 1. Fork and Clone
```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/moneywiz-mcp-server.git
cd moneywiz-mcp-server
git remote add upstream https://github.com/jcvalerio/moneywiz-mcp-server.git
```

### 2. Create a Feature Branch
```bash
# Always branch from main
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name

# For bug fixes
git checkout -b fix/issue-description

# For documentation
git checkout -b docs/update-description
```

### 3. Make Your Changes
```bash
# Set up development environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev,test]"

# Run setup
python setup_env.py

# Make your changes and test them
python -m pytest tests/
```

### 4. Commit Your Changes
```bash
# Stage your changes
git add .

# Commit with conventional commits format
git commit -m "feat: Add new feature description"
# or
git commit -m "fix: Fix issue description"
# or
git commit -m "docs: Update documentation"
```

#### Commit Message Format
We use [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code changes that neither fix bugs nor add features
- `perf:` Performance improvements
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

### 5. Push and Create Pull Request
```bash
# Push to your fork
git push origin feature/your-feature-name

# Then create a PR on GitHub
```

## 📋 Pull Request Process

### Before Submitting
- [ ] Update documentation if needed
- [ ] Add tests for new functionality
- [ ] Ensure all tests pass: `python -m pytest tests/`
- [ ] Run linting: `flake8 src/`
- [ ] Update README.md if adding new features

### PR Guidelines
1. **Title**: Use conventional commit format (e.g., "feat: Add expense prediction tool")
2. **Description**: Clearly describe what changes you made and why
3. **Link Issues**: Reference any related issues (e.g., "Fixes #123")
4. **Screenshots**: Include screenshots for UI changes
5. **Breaking Changes**: Clearly mark any breaking changes

### PR Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] Added new tests for new functionality
- [ ] Tested with Claude Desktop

## Checklist
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
```

## 🧪 Testing Guidelines

### Running Tests
```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=moneywiz_mcp_server

# Run specific test file
python -m pytest tests/test_accounts.py -v
```

### Writing Tests
- Place tests in `tests/` directory
- Mirror the source code structure
- Use descriptive test names
- Include both positive and negative test cases
- Mock external dependencies (database, API calls)

## 🎨 Code Style

### Python Style
- Follow PEP 8
- Use type hints for all function signatures
- Maximum line length: 88 characters (Black default)
- Use descriptive variable names

### Tools
```bash
# Format code
black src/

# Sort imports
isort src/

# Type checking
mypy src/

# Linting
flake8 src/
```

## 📚 Documentation

### Code Documentation
- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Include parameter types and return values
- Add usage examples for complex functions

### Project Documentation
- Update README.md for new features
- Keep ARCHITECTURE.md current
- Add entries to CHANGELOG.md
- Update configuration examples if needed

## 🐛 Reporting Issues

### Bug Reports
Please include:
- Python version
- OS and version
- MoneyWiz version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages/logs

### Feature Requests
Please describe:
- The problem you're trying to solve
- Your proposed solution
- Alternative solutions considered
- Any implementation ideas

## 🚀 Release Process

We use semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

Releases are created when significant features or fixes are merged.

## 💡 Getting Help

- Check existing issues and PRs
- Read the documentation
- Ask in discussions
- Join our community chat (if available)

## 🏆 Recognition

Contributors are recognized in:
- The project README
- Release notes
- Special thanks in major releases

Thank you for contributing to MoneyWiz MCP Server! 🎉
