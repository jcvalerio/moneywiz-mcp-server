#!/bin/bash
# Local CI Simulation Script
# Runs the exact same checks that GitHub Actions CI runs
# This ensures local and CI environments are perfectly aligned

set -e  # Exit on any error

echo "🚀 Running Local CI Simulation..."
echo "This runs the exact same commands as GitHub Actions CI"
echo

# Change to project root
cd "$(dirname "$0")/.."

echo "📋 Step 1: Installing dependencies"
pip install -e ".[dev]" > /dev/null 2>&1
echo "✅ Dependencies installed"
echo

echo "🔍 Step 2: Ruff Linter (exact CI command)"
echo "Running: ruff check . --output-format=github"
ruff check . --output-format=github
echo "✅ Ruff linting passed"
echo

echo "✨ Step 3: Ruff Formatter (exact CI command)"
echo "Running: ruff format --check ."
ruff format --check .
echo "✅ Ruff formatting passed"
echo

echo "🔒 Step 4: Mypy Type Checking (non-blocking, same as CI)"
echo "Running: mypy src/"
if mypy src/; then
    echo "✅ Mypy type checking passed"
else
    echo "⚠️  Mypy has warnings (non-blocking, same as CI)"
fi
echo

echo "🛡️  Step 5: Bandit Security Check"
echo "Running: bandit -r src/"
if bandit -r src/ > /dev/null 2>&1; then
    echo "✅ Bandit security check passed"
else
    echo "⚠️  Bandit has security warnings"
fi
echo

echo "🧪 Step 6: Unit Tests (excluding integration)"
echo "Running: pytest tests/unit/ -m 'not integration'"
pytest tests/unit/ -m "not integration" --tb=short
echo "✅ Unit tests passed"
echo

echo "🎉 All CI checks completed successfully!"
echo "Your code should pass GitHub Actions CI"
