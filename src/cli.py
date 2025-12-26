"""CLI mode for batch processing with YAML config."""

import logging
from pathlib import Path

import yaml

from src.core.config import LAYERS
from src.core.kmz_generator import KMZGenerator
from src.core.tile_calculator import TileCalculator
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """
    Load YAML configuration file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file) as f:
        config = yaml.safe_load(f)

    return config


def validate_config(config: dict) -> None:
    """
    Validate configuration.

    Args:
        config: Configuration dictionary

    Raises:
        ValueError: If configuration is invalid
    """
    required_keys = ["extent", "min_zoom", "max_zoom", "output", "layers"]

    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")

    # Validate extent
    extent_keys = ["min_lon", "min_lat", "max_lon", "max_lat"]
    for key in extent_keys:
        if key not in config["extent"]:
            raise ValueError(f"Missing extent key: {key}")

    # Validate layers
    if not isinstance(config["layers"], list) or len(config["layers"]) == 0:
        raise ValueError("Layers must be a non-empty list")

    for layer in config["layers"]:
        # Support both simple string format and dict format
        if isinstance(layer, str):
            if layer not in LAYERS:
                raise ValueError(f"Invalid layer: {layer}. Valid layers: {', '.join(LAYERS.keys())}")
        elif isinstance(layer, dict):
            if "name" not in layer:
                raise ValueError("Layer dict must have 'name' field")
            if layer["name"] not in LAYERS:
                raise ValueError(f"Invalid layer: {layer['name']}. Valid layers: {', '.join(LAYERS.keys())}")
            # Validate optional fields
            if "opacity" in layer and not (0 <= layer["opacity"] <= 100):
                raise ValueError(f"Opacity must be between 0 and 100, got {layer['opacity']}")
            if "blend_mode" in layer and layer["blend_mode"] not in ["normal", "multiply", "screen", "overlay"]:
                raise ValueError(f"Invalid blend_mode: {layer['blend_mode']}")
            if "export_mode" in layer and layer["export_mode"] not in ["composite", "separate"]:
                raise ValueError(f"Invalid export_mode: {layer['export_mode']}. Must be 'composite' or 'separate'")

            # Validate LOD configuration
            if "lod_mode" in layer:
                lod_mode = layer["lod_mode"]
                if lod_mode not in ["all_zooms", "select_zooms"]:
                    raise ValueError(
                        f"Invalid lod_mode for layer {layer['name']}: '{lod_mode}'. "
                        f"Must be 'all_zooms' or 'select_zooms'"
                    )

                if lod_mode == "select_zooms":
                    if "selected_zooms" not in layer:
                        raise ValueError(
                            f"Layer {layer['name']} has lod_mode='select_zooms' but no selected_zooms provided"
                        )

                    selected_zooms = layer["selected_zooms"]
                    if not isinstance(selected_zooms, list) or not selected_zooms:
                        raise ValueError(f"Layer {layer['name']}: selected_zooms must be a non-empty list")

                    for zoom in selected_zooms:
                        if not isinstance(zoom, int):
                            raise ValueError(
                                f"Layer {layer['name']}: all selected_zooms must be integers, got {type(zoom).__name__}"
                            )
                        if zoom < 0 or zoom > 18:
                            raise ValueError(f"Layer {layer['name']}: zoom levels must be between 0 and 18, got {zoom}")
        else:
            raise ValueError("Layer must be a string or dict")

    # Validate zoom configuration
    min_zoom = config["min_zoom"]
    max_zoom = config["max_zoom"]

    if not isinstance(min_zoom, int):
        raise ValueError("min_zoom must be an integer")
    if not isinstance(max_zoom, int):
        raise ValueError("max_zoom must be an integer")

    if min_zoom < 2 or min_zoom > 18:
        raise ValueError(f"min_zoom must be between 2 and 18, got {min_zoom}")
    if max_zoom < 2 or max_zoom > 18:
        raise ValueError(f"max_zoom must be between 2 and 18, got {max_zoom}")

    if min_zoom > max_zoom:
        raise ValueError(f"min_zoom ({min_zoom}) cannot be greater than max_zoom ({max_zoom})")

    # Validate web_compatible mode
    if "web_compatible" in config:
        web_compatible = config["web_compatible"]
        if not isinstance(web_compatible, bool):
            raise ValueError("web_compatible must be a boolean")

        # Note: web_compatible mode will automatically calculate optimal zoom within range
        # No need to enforce min_zoom == max_zoom here


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
        config = load_config(config_path)
        validate_config(config)

        # Parse configuration
        extent = Extent(
            min_lon=config["extent"]["min_lon"],
            min_lat=config["extent"]["min_lat"],
            max_lon=config["extent"]["max_lon"],
            max_lat=config["extent"]["max_lat"],
        )

        if not extent.is_valid():
            logger.error("Invalid extent: coordinates out of range or min > max")
            return 1

        # Validate extent is within Japan region
        if not extent.is_within_japan_region():
            logger.error("Extent is outside valid region. Please select an area within Japan (122°E-154°E, 20°N-46°N)")
            return 1

        if not extent.is_fully_within_japan_region():
            logger.warning("Extent is partially outside valid region. Some tiles may not be available.")

        output_path = Path(config["output"])
        layer_specs = config["layers"]

        # Parse zoom configuration
        min_zoom = config["min_zoom"]
        max_zoom = config["max_zoom"]
        web_compatible = config.get("web_compatible", False)

        if web_compatible:
            logger.info(f"Web compatible mode enabled: single zoom level {max_zoom}")
        elif min_zoom < max_zoom:
            logger.info(f"Multi-zoom enabled: zoom {min_zoom} to {max_zoom}")
        else:
            logger.info(f"Single zoom level: {max_zoom}")

        # Parse layer specifications (support both string and dict formats)
        layer_compositions = []
        layers = []

        for spec in layer_specs:
            # Use LayerComposition.from_dict() to properly parse all fields
            # including lod_mode, selected_zooms, opacity, blend_mode, etc.
            composition = LayerComposition.from_dict(spec)
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
        logger.info(f"  Output: {output_path}")

        # Generate KMZ (tiles will be fetched on-demand with caching)
        logger.info("Generating KMZ file...")
        generator = KMZGenerator(output_path)
        result_path = generator.create_kmz(extent, min_zoom, max_zoom, layer_compositions, web_compatible)

        logger.info(f"✓ KMZ file created successfully: {result_path}")
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
