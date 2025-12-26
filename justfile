# Run linting (ruff + type checking)
lint:
    uv run ruff check .
    uv run ty check

# Format code with ruff
format:
    uv run ruff format .
    uv run ruff check --fix .

# Run type checking on a specific path
lint-path PATH:
    uv run ty check {{PATH}}

# Run tests (if applicable)
test:
    uv run pytest tests/

# Install/sync dependencies
sync:
    uv sync

# Run the application
run:
    uv run google-earth-tiles
