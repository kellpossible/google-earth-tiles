"""CLI mode for batch processing with YAML config."""

import logging
from pathlib import Path

import yaml

from src.core.config import LAYERS, build_layer_registry
from src.core.tile_calculator import TileCalculator
from src.models.extent_config import ExtentConfig
from src.models.layer_composition import LayerComposition
from src.models.output_config import OutputConfig
from src.outputs import get_output_handler
from src.utils.kml_extent import calculate_extent_from_kml

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> tuple[dict, Path]:
    """
    Load YAML configuration file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Tuple of (configuration dictionary, config directory path)

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Return config and its directory for relative path resolution
    config_dir = config_file.parent.resolve()

    return config, config_dir


def validate_config(config: dict, layer_registry: dict | None = None) -> None:
    """
    Validate configuration using Pydantic schema validation.

    Args:
        config: Configuration dictionary
        layer_registry: Optional custom layer registry to use instead of default LAYERS

    Raises:
        ValueError: If configuration is invalid
        ImportError: If Pydantic models haven't been generated (run `just codegen`)
    """
    try:
        from pydantic import ValidationError

        from src.models.generated import GoogleEarthTileGeneratorConfiguration
    except ImportError as e:
        raise ImportError(
            "Pydantic models not found. Please run 'just codegen' to generate validation models from schema."
        ) from e

    # Pydantic structural validation
    try:
        GoogleEarthTileGeneratorConfiguration.model_validate(config)
    except ValidationError as e:
        # Convert Pydantic errors to ValueError for consistency
        raise ValueError(f"Configuration validation failed:\n{e}") from e

    # Build layer registry (includes default LAYERS + custom layer_sources)
    if layer_registry is None:
        layer_registry = LAYERS

    # Validate layer names exist in registry (business logic Pydantic can't handle)
    for layer in config["layers"]:
        # Support both simple string format and dict format
        if isinstance(layer, str):
            layer_name = layer
        elif isinstance(layer, dict):
            layer_name = layer["name"]
        else:
            continue  # Pydantic already validated structure

        # Check layer exists in registry
        if layer_name not in layer_registry:
            raise ValueError(f"Invalid layer: {layer_name}. Valid layers: {', '.join(layer_registry.keys())}")


def run_cli(config_path: str) -> int:
    """
    Run CLI mode with config file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Load and validate config
        logger.info(f"Loading configuration from: {config_path}")
        config, config_dir = load_config(config_path)

        # Build layer registry (includes default LAYERS + custom layer_sources)
        layer_registry = build_layer_registry(config)

        validate_config(config, layer_registry)

        # Parse extent configuration
        extent_data = config["extent"]

        extent_config = ExtentConfig.from_dict(extent_data, config_dir=config_dir)

        # Resolve file-based extent if needed
        if extent_config.mode == "file":
            try:
                resolved_extent = calculate_extent_from_kml(extent_config.file_path, extent_config.padding_meters)
                extent_config._resolved_extent = resolved_extent
                logger.info(f"Loaded extent from KML: {extent_config.file_path}")
                if extent_config.padding_meters > 0:
                    logger.info(f"Applied padding: {extent_config.padding_meters} meters")
            except FileNotFoundError as e:
                logger.error(str(e))
                return 1
            except ValueError as e:
                logger.error(f"Invalid KML file: {e}")
                return 1

        extent = extent_config.get_extent()

        if not extent.is_valid():
            logger.error("Invalid extent: coordinates out of range or min > max")
            return 1

        # Validate extent is within Japan region
        if not extent.is_within_japan_region():
            logger.error("Extent is outside valid region. Please select an area within Japan (122°E-154°E, 20°N-46°N)")
            return 1

        if not extent.is_fully_within_japan_region():
            logger.warning("Extent is partially outside valid region. Some tiles may not be available.")

        # Parse outputs
        outputs = []
        for output_dict in config["outputs"]:
            try:
                outputs.append(OutputConfig.from_dict(output_dict, config_dir=config_dir))
            except Exception as e:
                logger.error(f"Invalid output configuration: {e}")
                return 1

        if not outputs:
            logger.error("No outputs specified. At least one output is required.")
            return 1

        layer_specs = config["layers"]

        # Parse zoom configuration
        min_zoom = config["min_zoom"]
        max_zoom = config["max_zoom"]

        # Global metadata (optional)
        name = config.get("name")
        description = config.get("description")
        attribution = config.get("attribution")

        include_timestamp = config.get("include_timestamp", True)
        enable_cache = config.get("enable_cache", True)

        if min_zoom < max_zoom:
            logger.info(f"Multi-zoom enabled: zoom {min_zoom} to {max_zoom}")
        else:
            logger.info(f"Single zoom level: {max_zoom}")

        # Parse layer specifications (support both string and dict formats)
        layer_compositions = []
        layers = []

        for spec in layer_specs:
            # Use LayerComposition.from_dict() to properly parse all fields
            # including lod_mode, selected_zooms, opacity, blend_mode, etc.
            composition = LayerComposition.from_dict(spec, layer_registry)
            layer_compositions.append(composition)
            layers.append(composition.layer_config)

        # No zoom range clamping needed - resampling is supported
        # Users can specify any zoom range from 2-18, regardless of layer native zoom ranges

        # Calculate estimates across all zoom levels
        total_tiles = 0
        for zoom_level in range(min_zoom, max_zoom + 1):
            tile_count = TileCalculator.estimate_tile_count(
                extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom_level
            )
            total_tiles += tile_count * len(layers)

        # Build layer names for display
        layer_names = [comp.layer_config.name for comp in layer_compositions]

        logger.info("Configuration:")
        logger.info(f"  Layers: {', '.join(layer_names)}")
        if min_zoom == max_zoom:
            logger.info(f"  Zoom: {max_zoom}")
        else:
            logger.info(f"  Zoom range: {min_zoom}-{max_zoom} ({max_zoom - min_zoom + 1} levels)")
        logger.info(
            f"  Extent: {extent.min_lon:.4f}, {extent.min_lat:.4f} to {extent.max_lon:.4f}, {extent.max_lat:.4f}"
        )
        logger.info(f"  Total tiles to composite: {total_tiles:,}")
        logger.info(f"  Outputs: {len(outputs)}")

        # Generate outputs (tiles will be fetched on-demand with caching)
        if not enable_cache:
            logger.info("Tile caching disabled")

        for idx, output_config in enumerate(outputs, 1):
            # Get the output handler for this type
            handler = get_output_handler(output_config.output_type)

            logger.info(
                f"Generating output {idx}/{len(outputs)} ({handler.get_display_name()}): {output_config.output_path}"
            )

            # Log format-specific options
            if output_config.web_compatible:
                logger.info(f"  Web compatible mode enabled: single zoom level {max_zoom}")

            # Generate output using the handler
            result_path = handler.generate(
                output_path=output_config.output_path,
                extent=extent,
                min_zoom=min_zoom,
                max_zoom=max_zoom,
                layer_compositions=layer_compositions,
                progress_callback=None,
                name=name,
                description=description,
                attribution=attribution,
                include_timestamp=include_timestamp,
                **output_config.options,
            )
            logger.info(f"✓ Created: {result_path}")

        logger.info("All outputs generated successfully")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1
