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

# Run tests
test:
    uv run pytest tests/

# Update test snapshots
update-snapshots:
    uv run pytest tests/ --update-snapshots

# Install/sync dependencies
sync:
    uv sync

# Run the application
run:
    uv run google-earth-tiles

# Generate Pydantic models from JSON Schema
codegen:
    uv run datamodel-codegen \
        --input schemas/config.schema.yaml \
        --output src/models/generated.py \
        --input-file-type jsonschema \
        --output-model-type pydantic_v2.BaseModel \
        --use-standard-collections \
        --use-schema-description \
        --use-field-description \
        --field-constraints \
        --snake-case-field \
        --use-default \
        --enable-version-header \
        --target-python-version 3.11
    uv run ruff format src/models/generated.py
    uv run ruff check --fix src/models/generated.py
