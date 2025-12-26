"""Base class for tile-based output generators."""

import logging
from pathlib import Path

from src.core.tile_calculator import TileCalculator
from src.gui.tile_compositor import TileCompositor
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition

logger = logging.getLogger(__name__)


class BaseTileGenerator:
    """Base class for tile-based output generators.

    Provides shared functionality for formats that generate tiles across zoom levels,
    including tile fetching, layer composition, and progress tracking.

    This class extracts common patterns from KMZGenerator to enable code reuse across
    multiple output formats (KMZ, MBTiles, GeoTIFF, PNG directory, etc.).
    """

    def __init__(self, output_path: Path, progress_callback=None, enable_cache: bool = True):
        """Initialize base tile generator.

        Args:
            output_path: Path for output file
            progress_callback: Optional callback(current, total, message) for progress updates
            enable_cache: Whether to use tile caching (default: True)
        """
        self.output_path = Path(output_path)
        self.progress_callback = progress_callback
        self.compositor = TileCompositor(enable_cache=enable_cache)

    async def close(self):
        """Close compositor resources."""
        await self.compositor.close()

    def calculate_total_tiles(
        self, extent: Extent, min_zoom: int, max_zoom: int, composited_count: int, separate_count: int
    ) -> int:
        """Calculate total tiles for progress tracking.

        Args:
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            composited_count: Number of composited layer groups (0 or 1)
            separate_count: Number of separate layers

        Returns:
            Total number of tiles to be generated
        """
        total_tiles = 0
        for zoom_level in range(min_zoom, max_zoom + 1):
            tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom_level
            )
            if composited_count > 0:
                total_tiles += len(tiles_at_zoom)
            total_tiles += len(tiles_at_zoom) * separate_count
        return total_tiles

    @staticmethod
    def separate_layers_by_export_mode(
        layer_compositions: list[LayerComposition],
    ) -> tuple[list[LayerComposition], list[LayerComposition]]:
        """Separate layers into composite and separate groups.

        Extracted from KMZGenerator._separate_layers_by_export_mode().

        When only one layer is enabled, it's automatically treated as separate
        to use format-level opacity instead of pixel-level compositing.

        Args:
            layer_compositions: All layer compositions

        Returns:
            Tuple of (composited_layers, separate_layers)
        """
        composited = []
        separate = []

        enabled_layers = [comp for comp in layer_compositions if comp.enabled]

        # Special case: if only one layer, always treat as separate
        # (use format-level opacity instead of pixel-level compositing)
        if len(enabled_layers) == 1:
            return [], enabled_layers

        # Multi-layer case: respect export_mode setting
        for comp in enabled_layers:
            if comp.export_mode == "separate":
                separate.append(comp)
            else:
                composited.append(comp)

        return composited, separate

    async def fetch_tiles_for_layer(
        self, extent: Extent, min_zoom: int, max_zoom: int, layer_composition: LayerComposition, temp_dir: Path
    ) -> dict[int, list[tuple[Path, int, int, int]]]:
        """Fetch tiles for a single layer across zoom range.

        Extracted from KMZGenerator._fetch_separate_layer_tiles().

        This method leverages the existing TileCompositor to handle all fetching
        and resampling logic, avoiding code duplication. Resampling is automatically
        supported - the compositor will fetch from the nearest available zoom when
        the exact zoom is not available (see LayerComposition.get_available_zooms()).

        Args:
            extent: Geographic extent
            min_zoom: Minimum zoom level to generate
            max_zoom: Maximum zoom level to generate
            layer_composition: Layer composition for this layer
            temp_dir: Temporary directory for tile storage

        Returns:
            Dictionary mapping zoom level to list of (tile_path, x, y, z) tuples
        """
        layer_name = layer_composition.layer_config.name
        tiles_by_zoom = {}

        # Create a temporary composition with opacity=100 to avoid pixel-level opacity
        # Opacity will be applied in format-specific code only for separate layers
        temp_composition = layer_composition.copy()
        temp_composition.opacity = 100

        for zoom_level in range(min_zoom, max_zoom + 1):
            logger.info(f"Fetching {layer_name} tiles at zoom {zoom_level}...")

            # Get tiles in extent
            tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom_level
            )

            fetched_tiles = []
            for x, y in tiles_at_zoom:
                # Use compositor to fetch and resample tile
                # Compositor automatically handles resampling from nearest available zoom
                tile_data = await self.compositor.composite_tile(
                    x,
                    y,
                    zoom_level,
                    [temp_composition],  # Single-layer "composition"
                )

                if tile_data:
                    # Save to temp file with layer name prefix
                    tile_path = temp_dir / f"{layer_name}_{zoom_level}_{x}_{y}.png"
                    with open(tile_path, "wb") as f:
                        f.write(tile_data)
                    fetched_tiles.append((tile_path, x, y, zoom_level))

            tiles_by_zoom[zoom_level] = fetched_tiles
            logger.info(f"Fetched {len(fetched_tiles)} tiles for {layer_name} at zoom {zoom_level}")

        return tiles_by_zoom
