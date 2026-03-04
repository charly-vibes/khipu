set dotenv-load

# Install dependencies
sync:
    uv sync --all-extras

# Run all tests
test:
    uv run pytest

# Show coverage report (run 'just test' first)
coverage:
    uv run coverage report

# Lint and format check
lint:
    uv run ruff check .
    uv run ruff format --check .

# Auto-fix lint issues and format
fmt:
    uv run ruff check --fix .
    uv run ruff format .

# Type check
typecheck:
    uv run mypy src/khipu

# Run all checks (lint + typecheck + tests)
check: lint typecheck test

# Run khipu CLI
run *args:
    uv run khipu {{ args }}

# Start MCP server
mcp:
    uv run khipu mcp

# List available backends
backends:
    uv run khipu backends

# Build package
build:
    uv build

# Clean build artifacts
clean:
    rm -rf dist/ .coverage .mypy_cache .ruff_cache __pycache__
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type d -name "*.egg-info" -exec rm -rf {} +
