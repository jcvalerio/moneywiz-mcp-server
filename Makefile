# MoneyWiz MCP Server - Development Makefile
# Modern Python development workflow with Ruff, Black, Mypy, and more

.PHONY: help install install-dev clean lint format type-check security test test-cov test-integration docs pre-commit setup-pre-commit ci-local build

# Default target
help:  ## Show this help
	@echo "MoneyWiz MCP Server - Development Commands"
	@echo "=========================================="
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Installation
install:  ## Install package for production
	pip install -e .

install-dev:  ## Install package with development dependencies
	pip install -e ".[dev,test]"

# Code Quality
lint:  ## Run all linting checks
	@echo "🔍 Running Ruff linter..."
	ruff check .
	@echo "✅ Linting complete!"

lint-fix:  ## Run linting with auto-fix
	@echo "🔧 Running Ruff with auto-fix..."
	ruff check --fix .
	@echo "✅ Auto-fix complete!"

format:  ## Format code with Ruff and Black
	@echo "🎨 Formatting code..."
	ruff format .
	black .
	@echo "✅ Formatting complete!"

format-check:  ## Check code formatting without making changes
	@echo "🔍 Checking code formatting..."
	ruff format --check .
	black --check .
	@echo "✅ Format check complete!"

type-check:  ## Run static type checking with Mypy
	@echo "🔬 Running type checks..."
	mypy src/
	@echo "✅ Type checking complete!"

security:  ## Run security checks
	@echo "🛡️ Running security checks..."
	bandit -r src/
	safety check
	@echo "✅ Security checks complete!"

# Testing
test:  ## Run tests
	@echo "🧪 Running tests..."
	pytest
	@echo "✅ Tests complete!"

test-cov:  ## Run tests with coverage report
	@echo "🧪 Running tests with coverage..."
	pytest --cov=moneywiz_mcp_server --cov-report=term-missing --cov-report=html
	@echo "📊 Coverage report generated in htmlcov/"

test-integration:  ## Run integration tests only
	@echo "🔗 Running integration tests..."
	pytest tests/integration/ -v
	@echo "✅ Integration tests complete!"

test-unit:  ## Run unit tests only
	@echo "🔬 Running unit tests..."
	pytest tests/unit/ -v
	@echo "✅ Unit tests complete!"

# Documentation
docs:  ## Build documentation (if configured)
	@if [ -f "mkdocs.yml" ]; then \
		echo "📚 Building documentation..."; \
		mkdocs build; \
		echo "✅ Documentation built!"; \
	else \
		echo "📝 No documentation configuration found"; \
	fi

docs-serve:  ## Serve documentation locally
	@if [ -f "mkdocs.yml" ]; then \
		echo "🌐 Serving documentation at http://localhost:8000"; \
		mkdocs serve; \
	else \
		echo "📝 No documentation configuration found"; \
	fi

# Pre-commit
setup-pre-commit:  ## Install pre-commit hooks
	@echo "🪝 Installing pre-commit hooks..."
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "✅ Pre-commit hooks installed!"

pre-commit:  ## Run pre-commit hooks on all files
	@echo "🔄 Running pre-commit hooks..."
	pre-commit run --all-files
	@echo "✅ Pre-commit complete!"

# CI/CD Simulation
ci-local:  ## Run complete CI pipeline locally
	@echo "🚀 Running local CI pipeline..."
	@echo "📋 Step 1: Code formatting check"
	$(MAKE) format-check
	@echo "📋 Step 2: Linting"
	$(MAKE) lint
	@echo "📋 Step 3: Type checking"
	$(MAKE) type-check
	@echo "📋 Step 4: Security checks"
	$(MAKE) security
	@echo "📋 Step 5: Tests with coverage"
	$(MAKE) test-cov
	@echo "📋 Step 6: Build package"
	$(MAKE) build
	@echo "🎉 Local CI pipeline complete!"

# Package Management
build:  ## Build package distribution
	@echo "📦 Building package..."
	python -m build
	@echo "✅ Package built in dist/"

build-check:  ## Check built package
	@echo "🔍 Checking package..."
	twine check dist/*
	@echo "✅ Package check complete!"

clean:  ## Clean build artifacts and cache
	@echo "🧹 Cleaning up..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleanup complete!"

# Development workflow
dev-setup:  ## Complete development environment setup
	@echo "🚀 Setting up development environment..."
	$(MAKE) install-dev
	$(MAKE) setup-pre-commit
	@echo "✅ Development environment ready!"

quick-check:  ## Quick code quality check (format + lint + type)
	@echo "⚡ Quick quality check..."
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) type-check
	@echo "✅ Quick check complete!"

# MCP Server specific
run-server:  ## Run MCP server locally
	@echo "🖥️ Starting MoneyWiz MCP Server..."
	python -m moneywiz_mcp_server.main

test-mcp:  ## Test MCP server functionality
	@echo "🧪 Testing MCP server..."
	python test_mcp_minimal.py