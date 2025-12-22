"""KMZ file generator."""

import logging
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import simplekml

from src.core.config import LayerConfig
from src.core.tile_calculator import TileCalculator

logger = logging.getLogger(__name__)


class KMZGenerator:
    """Generator for KMZ files with multiple layers."""

    def __init__(self, output_path: Path):
        """
        Initialize KMZ generator.

        Args:
            output_path: Path for output KMZ file
        """
        self.output_path = Path(output_path)
        self.kml = simplekml.Kml()

    def create_kmz(
        self,
        layer_tiles_dict: Dict[LayerConfig, List[Tuple[Path, int, int, int]]],
        zoom: int,
    ) -> Path:
        """
        Create KMZ file with tiles from multiple layers.

        Args:
            layer_tiles_dict: Dictionary mapping LayerConfig to list of (tile_path, x, y, z) tuples
            zoom: Zoom level

        Returns:
            Path to created KMZ file
        """
        if not layer_tiles_dict:
            raise ValueError("No tiles provided for KMZ generation")

        # Set document metadata
        self.kml.document.name = f"GSI Tiles - Zoom {zoom}"
        self.kml.document.description = f"Generated: {datetime.now().isoformat()}"

        # Create temporary KML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as kml_file:
            kml_temp_path = Path(kml_file.name)

        try:
            # Add tiles for each layer
            for layer_config, tiles in layer_tiles_dict.items():
                self._add_layer_tiles(layer_config, tiles, zoom)

            # Save KML
            self.kml.save(str(kml_temp_path))

            # Create KMZ (ZIP file)
            self._create_kmz_archive(kml_temp_path, layer_tiles_dict)

            logger.info(f"Created KMZ file: {self.output_path}")
            return self.output_path

        finally:
            # Cleanup temp KML file
            if kml_temp_path.exists():
                kml_temp_path.unlink()

    def _add_layer_tiles(
        self,
        layer_config: LayerConfig,
        tiles: List[Tuple[Path, int, int, int]],
        zoom: int,
    ):
        """
        Add tiles from a layer to the KML document.

        Args:
            layer_config: Layer configuration
            tiles: List of (tile_path, x, y, z) tuples
            zoom: Zoom level
        """
        if not tiles:
            return

        # Create folder for this layer
        folder = self.kml.newfolder(name=layer_config.display_name)

        # Add each tile as GroundOverlay
        for tile_path, x, y, z in tiles:
            bounds = TileCalculator.tile_to_lat_lon_bounds(x, y, z)

            ground = folder.newgroundoverlay(name=f"{layer_config.name} {z}/{x}/{y}")

            # Set icon path (relative to KMZ root)
            icon_path = f"files/tiles/{layer_config.name}/{z}_{x}_{y}.{layer_config.extension}"
            ground.icon.href = icon_path

            # Set geographic bounds
            ground.latlonbox.north = bounds['north']
            ground.latlonbox.south = bounds['south']
            ground.latlonbox.east = bounds['east']
            ground.latlonbox.west = bounds['west']

            # Set draw order (higher zoom = drawn on top)
            ground.draworder = zoom

        logger.info(
            f"Added {len(tiles)} tiles from layer '{layer_config.display_name}'"
        )

    def _create_kmz_archive(
        self,
        kml_path: Path,
        layer_tiles_dict: Dict[LayerConfig, List[Tuple[Path, int, int, int]]],
    ):
        """
        Create KMZ archive with KML and tile images.

        Args:
            kml_path: Path to KML file
            layer_tiles_dict: Dictionary of tiles by layer
        """
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(self.output_path, 'w', zipfile.ZIP_DEFLATED) as kmz:
            # Add KML file (must be named doc.kml at root)
            kmz.write(kml_path, 'doc.kml')

            # Add tile images organized by layer
            for layer_config, tiles in layer_tiles_dict.items():
                for tile_path, x, y, z in tiles:
                    if not tile_path.exists():
                        logger.warning(f"Tile file not found: {tile_path}")
                        continue

                    # Archive path: files/tiles/{layer_name}/{z}_{x}_{y}.{ext}
                    arcname = (
                        f"files/tiles/{layer_config.name}/"
                        f"{z}_{x}_{y}.{layer_config.extension}"
                    )
                    kmz.write(tile_path, arcname)

        logger.info(f"KMZ archive created with {self._count_tiles(layer_tiles_dict)} tiles")

    @staticmethod
    def _count_tiles(
        layer_tiles_dict: Dict[LayerConfig, List[Tuple[Path, int, int, int]]]
    ) -> int:
        """Count total tiles across all layers."""
        return sum(len(tiles) for tiles in layer_tiles_dict.values())
