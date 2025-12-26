# Run type checking with ty
lint:
    uv run ty check

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
