"""KMZ file generator."""

import asyncio
import logging
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import simplekml

from src.core.config import LayerConfig
from src.core.tile_calculator import TileCalculator
from src.models.layer_composition import LayerComposition
from src.gui.tile_compositor import TileCompositor

logger = logging.getLogger(__name__)


class KMZGenerator:
    """Generator for KMZ files with composited layers."""

    def __init__(self, output_path: Path):
        """
        Initialize KMZ generator.

        Args:
            output_path: Path for output KMZ file
        """
        self.output_path = Path(output_path)
        self.kml = simplekml.Kml()
        self.compositor = TileCompositor()

    async def create_kmz_async(
        self,
        layer_tiles_dict: Dict[LayerConfig, List[Tuple[Path, int, int, int]]],
        zoom: int,
        layer_compositions: List[LayerComposition]
    ) -> Path:
        """
        Create KMZ file with composited tiles.

        Args:
            layer_tiles_dict: Dictionary mapping LayerConfig to list of (tile_path, x, y, z) tuples
            zoom: Zoom level
            layer_compositions: List of LayerComposition objects

        Returns:
            Path to created KMZ file
        """
        if not layer_tiles_dict:
            raise ValueError("No tiles provided for KMZ generation")

        # Set document metadata
        self.kml.document.name = f"GSI Tiles - Zoom {zoom}"
        self.kml.document.description = f"Generated: {datetime.now().isoformat()}"

        # Create temporary directory for composited tiles
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Get all unique tile coordinates
            tile_coords = set()
            for tiles in layer_tiles_dict.values():
                for _, x, y, z in tiles:
                    tile_coords.add((x, y, z))

            logger.info(f"Compositing {len(tile_coords)} tiles...")

            # Composite each tile
            composited_tiles = []
            for x, y, z in tile_coords:
                # Composite tile using the same logic as preview
                tile_data = await self.compositor.composite_tile(x, y, z, layer_compositions)

                if tile_data:
                    # Save to temp file
                    tile_path = temp_dir / f"{z}_{x}_{y}.png"
                    with open(tile_path, 'wb') as f:
                        f.write(tile_data)
                    composited_tiles.append((tile_path, x, y, z))

            # Create temporary KML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as kml_file:
                kml_temp_path = Path(kml_file.name)

            # Add composited tiles to KML
            self._add_composited_tiles(composited_tiles, zoom)

            # Save KML
            self.kml.save(str(kml_temp_path))

            # Create KMZ (ZIP file)
            self._create_kmz_archive(kml_temp_path, composited_tiles)

            logger.info(f"Created KMZ file: {self.output_path}")
            return self.output_path

        finally:
            # Cleanup
            await self.compositor.close()
            if kml_temp_path.exists():
                kml_temp_path.unlink()

    def create_kmz(
        self,
        layer_tiles_dict: Dict[LayerConfig, List[Tuple[Path, int, int, int]]],
        zoom: int,
        layer_compositions: List[LayerComposition]
    ) -> Path:
        """
        Create KMZ file with composited tiles (synchronous wrapper).

        Args:
            layer_tiles_dict: Dictionary mapping LayerConfig to list of (tile_path, x, y, z) tuples
            zoom: Zoom level
            layer_compositions: List of LayerComposition objects

        Returns:
            Path to created KMZ file
        """
        # Run async version
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.create_kmz_async(layer_tiles_dict, zoom, layer_compositions)
        )

    def _add_composited_tiles(
        self,
        tiles: List[Tuple[Path, int, int, int]],
        zoom: int,
    ):
        """
        Add composited tiles to the KML document.

        Args:
            tiles: List of (tile_path, x, y, z) tuples
            zoom: Zoom level
        """
        if not tiles:
            return

        # Create folder for composited tiles
        folder = self.kml.newfolder(name="Composited Tiles")

        # Add each tile as GroundOverlay
        for tile_path, x, y, z in tiles:
            bounds = TileCalculator.tile_to_lat_lon_bounds(x, y, z)

            ground = folder.newgroundoverlay(name=f"Tile {z}/{x}/{y}")

            # Set icon path (relative to KMZ root)
            icon_path = f"files/tiles/{z}_{x}_{y}.png"
            ground.icon.href = icon_path

            # Set geographic bounds
            ground.latlonbox.north = bounds['north']
            ground.latlonbox.south = bounds['south']
            ground.latlonbox.east = bounds['east']
            ground.latlonbox.west = bounds['west']

            # Set draw order (higher zoom = drawn on top)
            ground.draworder = zoom

        logger.info(f"Added {len(tiles)} composited tiles to KML")

    def _create_kmz_archive(
        self,
        kml_path: Path,
        composited_tiles: List[Tuple[Path, int, int, int]],
    ):
        """
        Create KMZ archive with KML and composited tile images.

        Args:
            kml_path: Path to KML file
            composited_tiles: List of (tile_path, x, y, z) tuples
        """
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(self.output_path, 'w', zipfile.ZIP_DEFLATED) as kmz:
            # Add KML file (must be named doc.kml at root)
            kmz.write(kml_path, 'doc.kml')

            # Add composited tile images
            for tile_path, x, y, z in composited_tiles:
                if not tile_path.exists():
                    logger.warning(f"Tile file not found: {tile_path}")
                    continue

                # Archive path: files/tiles/{z}_{x}_{y}.png
                arcname = f"files/tiles/{z}_{x}_{y}.png"
                kmz.write(tile_path, arcname)

        logger.info(f"KMZ archive created with {len(composited_tiles)} composited tiles")
