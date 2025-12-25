"""CLI mode for batch processing with YAML config."""

import asyncio
import logging
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

import yaml
from tqdm import tqdm

from src.core.config import LAYERS, LayerConfig
from src.core.kmz_generator import KMZGenerator
from src.core.tile_calculator import TileCalculator
from src.core.wmts_client import WMTSClient
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict:
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

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    return config


def validate_config(config: Dict) -> None:
    """
    Validate configuration.

    Args:
        config: Configuration dictionary

    Raises:
        ValueError: If configuration is invalid
    """
    required_keys = ['extent', 'min_zoom', 'max_zoom', 'output', 'layers']

    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")

    # Validate extent
    extent_keys = ['min_lon', 'min_lat', 'max_lon', 'max_lat']
    for key in extent_keys:
        if key not in config['extent']:
            raise ValueError(f"Missing extent key: {key}")

    # Validate layers
    if not isinstance(config['layers'], list) or len(config['layers']) == 0:
        raise ValueError("Layers must be a non-empty list")

    for layer in config['layers']:
        # Support both simple string format and dict format
        if isinstance(layer, str):
            if layer not in LAYERS:
                raise ValueError(
                    f"Invalid layer: {layer}. "
                    f"Valid layers: {', '.join(LAYERS.keys())}"
                )
        elif isinstance(layer, dict):
            if 'name' not in layer:
                raise ValueError("Layer dict must have 'name' field")
            if layer['name'] not in LAYERS:
                raise ValueError(
                    f"Invalid layer: {layer['name']}. "
                    f"Valid layers: {', '.join(LAYERS.keys())}"
                )
            # Validate optional fields
            if 'opacity' in layer and not (0 <= layer['opacity'] <= 100):
                raise ValueError(f"Opacity must be between 0 and 100, got {layer['opacity']}")
            if 'blend_mode' in layer and layer['blend_mode'] not in ['normal', 'multiply', 'screen', 'overlay']:
                raise ValueError(f"Invalid blend_mode: {layer['blend_mode']}")
        else:
            raise ValueError("Layer must be a string or dict")

    # Validate zoom configuration
    min_zoom = config['min_zoom']
    max_zoom = config['max_zoom']

    if not isinstance(min_zoom, int):
        raise ValueError("min_zoom must be an integer")
    if not isinstance(max_zoom, int):
        raise ValueError("max_zoom must be an integer")

    if min_zoom < 0 or min_zoom > 18:
        raise ValueError(f"min_zoom must be between 0 and 18, got {min_zoom}")
    if max_zoom < 0 or max_zoom > 18:
        raise ValueError(f"max_zoom must be between 0 and 18, got {max_zoom}")

    if min_zoom > max_zoom:
        raise ValueError(f"min_zoom ({min_zoom}) cannot be greater than max_zoom ({max_zoom})")


async def download_tiles(
    layers: List[LayerConfig],
    extent: Extent,
    zoom: int
) -> Dict[LayerConfig, List]:
    """
    Download tiles for all layers.

    Args:
        layers: List of layer configurations
        extent: Geographic extent
        zoom: Zoom level

    Returns:
        Dictionary mapping layer configs to downloaded tiles
    """
    # Calculate tiles
    tiles_per_layer = TileCalculator.get_tiles_in_extent(
        extent.min_lon,
        extent.min_lat,
        extent.max_lon,
        extent.max_lat,
        zoom
    )

    total_tiles = len(tiles_per_layer) * len(layers)
    logger.info(f"Total tiles to download: {total_tiles:,}")

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp())
    layer_tiles_dict = {}

    # Create progress bar
    pbar = tqdm(total=total_tiles, desc="Downloading tiles", unit="tile")

    # Download tiles for each layer
    for layer in layers:
        logger.info(f"Downloading layer: {layer.display_name}")

        # Create layer directory
        layer_dir = temp_dir / layer.name
        layer_dir.mkdir(exist_ok=True)

        # Convert tiles to (x, y, z) format
        tiles_xyz = [(x, y, zoom) for x, y in tiles_per_layer]

        # Progress callback
        def progress_callback(current, total):
            pbar.update(1)

        # Download tiles
        async with WMTSClient(layer) as client:
            downloaded = await client.download_tiles_batch(
                tiles_xyz,
                layer_dir,
                progress_callback
            )

        layer_tiles_dict[layer] = downloaded

    pbar.close()
    return layer_tiles_dict


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
            min_lon=config['extent']['min_lon'],
            min_lat=config['extent']['min_lat'],
            max_lon=config['extent']['max_lon'],
            max_lat=config['extent']['max_lat'],
        )

        if not extent.is_valid():
            logger.error("Invalid extent: coordinates out of range or min > max")
            return 1

        # Validate extent is within Japan region
        if not extent.is_within_japan_region():
            logger.error(
                "Extent is outside valid region. "
                "Please select an area within Japan (122°E-154°E, 20°N-46°N)"
            )
            return 1

        if not extent.is_fully_within_japan_region():
            logger.warning(
                "Extent is partially outside valid region. "
                "Some tiles may not be available."
            )

        output_path = Path(config['output'])
        layer_specs = config['layers']

        # Parse zoom configuration
        min_zoom = config['min_zoom']
        max_zoom = config['max_zoom']

        if min_zoom < max_zoom:
            logger.info(f"Multi-zoom enabled: zoom {min_zoom} to {max_zoom}")
        else:
            logger.info(f"Single zoom level: {max_zoom}")

        # Parse layer specifications (support both string and dict formats)
        layer_compositions = []
        layers = []

        for spec in layer_specs:
            if isinstance(spec, str):
                # Simple format: just layer name
                layer_config = LAYERS[spec]
                composition = LayerComposition(
                    layer_config=layer_config,
                    opacity=100,  # Default
                    blend_mode='normal'  # Default
                )
            else:
                # Extended format: dict with name, optional opacity and blend_mode
                layer_config = LAYERS[spec['name']]
                composition = LayerComposition(
                    layer_config=layer_config,
                    opacity=spec.get('opacity', 100),  # Default to 100
                    blend_mode=spec.get('blend_mode', 'normal')  # Default to 'normal'
                )

            layer_compositions.append(composition)
            layers.append(layer_config)

        # Validate zoom range for selected layers
        layer_min_zoom = max(layer.min_zoom for layer in layers)
        layer_max_zoom = min(layer.max_zoom for layer in layers)

        # Clamp zoom range to valid layer range
        original_min = min_zoom
        original_max = max_zoom

        min_zoom = max(min_zoom, layer_min_zoom)
        max_zoom = min(max_zoom, layer_max_zoom)

        if min_zoom != original_min or max_zoom != original_max:
            logger.warning(
                f"Zoom range {original_min}-{original_max} adjusted to {min_zoom}-{max_zoom} "
                f"to match layer capabilities"
            )

        if min_zoom > max_zoom:
            logger.error(
                f"No valid zoom range for selected layers. "
                f"Layer range: {layer_min_zoom}-{layer_max_zoom}"
            )
            return 1

        # Calculate estimates across all zoom levels
        total_tiles = 0
        for zoom_level in range(min_zoom, max_zoom + 1):
            tile_count = TileCalculator.estimate_tile_count(
                extent.min_lon, extent.min_lat,
                extent.max_lon, extent.max_lat,
                zoom_level
            )
            total_tiles += tile_count * len(layers)

        # Build layer names for display
        layer_names = [comp.layer_config.name for comp in layer_compositions]

        logger.info(f"Configuration:")
        logger.info(f"  Layers: {', '.join(layer_names)}")
        if min_zoom == max_zoom:
            logger.info(f"  Zoom: {max_zoom}")
        else:
            logger.info(f"  Zoom range: {min_zoom}-{max_zoom} ({max_zoom - min_zoom + 1} levels)")
        logger.info(f"  Extent: {extent.min_lon:.4f}, {extent.min_lat:.4f} to "
                   f"{extent.max_lon:.4f}, {extent.max_lat:.4f}")
        logger.info(f"  Total tiles: {total_tiles:,}")
        logger.info(f"  Output: {output_path}")

        # Download tiles at max zoom level only
        logger.info(f"Downloading tiles at zoom {max_zoom}...")
        layer_tiles_dict = asyncio.run(download_tiles(layers, extent, max_zoom))

        # Generate KMZ
        logger.info("Generating KMZ file...")
        generator = KMZGenerator(output_path)
        result_path = generator.create_kmz(
            layer_tiles_dict,
            min_zoom,
            max_zoom,
            layer_compositions
        )

        # Cleanup temp files
        logger.info("Cleaning up temporary files...")
        for layer, tiles in layer_tiles_dict.items():
            for tile_path, x, y, z in tiles:
                if tile_path.exists():
                    tile_path.unlink()

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
