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

    def __init__(self, output_path: Path, progress_callback=None):
        """
        Initialize KMZ generator.

        Args:
            output_path: Path for output KMZ file
            progress_callback: Optional callback(current, total, message) for progress updates
        """
        self.output_path = Path(output_path)
        self.kml = simplekml.Kml()
        self.compositor = TileCompositor()
        self.progress_callback = progress_callback

    @staticmethod
    def calculate_lod_pixels(zoom: int, min_zoom: int, max_zoom: int) -> Tuple[int, int]:
        """
        Calculate LOD pixel thresholds for a zoom level.

        Creates overlapping LOD ranges with low thresholds so higher detail
        tiles appear early. Lower zoom tiles hide as you zoom in, while higher
        zoom tiles stay visible.

        Reference: 
            https://developers.google.com/kml/documentation/regions
            https://www.google.com/earth/outreach/learn/avoiding-overload-with-regions/
            https://developers.google.com/kml/documentation/kmlreference#minlodpixels
            https://developers.google.com/kml/documentation/kmlreference#maxlodpixels

        Args:
            zoom: Current zoom level
            min_zoom: Minimum zoom in LOD range
            max_zoom: Maximum zoom in LOD range

        Returns:
            Tuple of (minLodPixels, maxLodPixels) where -1 means infinite
        """
        if min_zoom == max_zoom:
            # Single zoom level - always visible
            return (-1, -1)
        
        if zoom == max_zoom:
            return (80, -1)
        
        if zoom == min_zoom:
            return (-1, 256)
        
        return (80, 256)

    async def create_kmz_async(
        self,
        extent: 'Extent',
        min_zoom: int,
        max_zoom: int,
        layer_compositions: List[LayerComposition]
    ) -> Path:
        """
        Create KMZ file with composited tiles and optional LOD pyramid.

        Args:
            extent: Geographic extent (Extent object)
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of LayerComposition objects

        Returns:
            Path to created KMZ file
        """
        if not layer_compositions:
            raise ValueError("No layer compositions provided for KMZ generation")

        if min_zoom > max_zoom:
            raise ValueError(f"min_zoom ({min_zoom}) cannot be greater than max_zoom ({max_zoom})")

        # Set document metadata
        if min_zoom < max_zoom:
            self.kml.document.name = f"GSI Tiles - Zoom {min_zoom}-{max_zoom} (LOD)"
        else:
            self.kml.document.name = f"GSI Tiles - Zoom {max_zoom}"
        self.kml.document.description = f"Generated: {datetime.now().isoformat()}"

        # Create temporary directory for composited tiles
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Use provided extent
            min_lon = extent.min_lon
            min_lat = extent.min_lat
            max_lon = extent.max_lon
            max_lat = extent.max_lat

            logger.info(f"Using extent: {min_lon:.6f}, {min_lat:.6f} to {max_lon:.6f}, {max_lat:.6f}")

            # Composite tiles at each zoom level separately
            # This allows using native source tiles at each zoom instead of downsampling
            all_tiles_by_zoom = {}

            # Calculate total tiles across all zoom levels for progress tracking
            total_tiles = 0
            for zoom_level in range(min_zoom, max_zoom + 1):
                tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                    min_lon, min_lat, max_lon, max_lat, zoom_level
                )
                total_tiles += len(tiles_at_zoom)

            # Composite at each zoom level
            composited_count = 0
            for zoom_level in range(min_zoom, max_zoom + 1):
                logger.info(f"Compositing tiles at zoom {zoom_level}...")

                # Calculate tile coordinates for this zoom level
                tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                    min_lon, min_lat, max_lon, max_lat, zoom_level
                )

                composited_tiles = []
                for x, y in tiles_at_zoom:
                    composited_count += 1

                    # Report progress
                    if self.progress_callback:
                        self.progress_callback(
                            composited_count,
                            total_tiles,
                            f"Compositing tile {composited_count}/{total_tiles}..."
                        )

                    # Composite this tile using native source tiles from layer_tiles_dict
                    tile_data = await self.compositor.composite_tile(
                        x, y, zoom_level, layer_compositions,
                        output_min_zoom=min_zoom,
                        output_max_zoom=max_zoom
                    )

                    if tile_data:
                        # Save to temp file
                        tile_path = temp_dir / f"{zoom_level}_{x}_{y}.png"
                        with open(tile_path, 'wb') as f:
                            f.write(tile_data)
                        composited_tiles.append((tile_path, x, y, zoom_level))

                all_tiles_by_zoom[zoom_level] = composited_tiles
                logger.info(f"Composited {len(composited_tiles)} tiles at zoom {zoom_level}")

            # Report compositing completion
            if self.progress_callback:
                self.progress_callback(total_tiles, total_tiles, "Compositing complete")

            # Phase 3: Create KML with all zoom levels
            if self.progress_callback:
                self.progress_callback(0, 1, "Creating KML document...")

            # Create temporary KML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as kml_file:
                kml_temp_path = Path(kml_file.name)

            # Add tiles for each zoom level with LOD
            lod_kml_config = None
            if min_zoom < max_zoom:
                lod_kml_config = {'min_zoom': min_zoom, 'max_zoom': max_zoom}

            for zoom_level in sorted(all_tiles_by_zoom.keys(), reverse=True):
                self._add_composited_tiles(
                    all_tiles_by_zoom[zoom_level],
                    zoom_level,
                    lod_kml_config
                )

            # Save KML
            self.kml.save(str(kml_temp_path))

            # Phase 4: Create KMZ archive
            if self.progress_callback:
                self.progress_callback(0, 1, "Creating KMZ archive...")

            all_tiles = []
            for tiles in all_tiles_by_zoom.values():
                all_tiles.extend(tiles)

            # Create KMZ (ZIP file)
            self._create_kmz_archive(kml_temp_path, all_tiles)

            logger.info(f"Created KMZ file: {self.output_path}")
            return self.output_path

        finally:
            # Cleanup
            await self.compositor.close()
            if kml_temp_path.exists():
                kml_temp_path.unlink()

    def create_kmz(
        self,
        extent: 'Extent',
        min_zoom: int,
        max_zoom: int,
        layer_compositions: List[LayerComposition]
    ) -> Path:
        """
        Create KMZ file with composited tiles and optional LOD (synchronous wrapper).

        Args:
            extent: Geographic extent (Extent object)
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
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
            self.create_kmz_async(extent, min_zoom, max_zoom, layer_compositions)
        )

    def _add_composited_tiles(
        self,
        tiles: List[Tuple[Path, int, int, int]],
        zoom: int,
        lod_config: dict = None
    ):
        """
        Add composited tiles to the KML document.

        Args:
            tiles: List of (tile_path, x, y, z) tuples
            zoom: Zoom level for these tiles
            lod_config: Optional LOD config with 'min_zoom' and 'max_zoom'
        """
        if not tiles:
            return

        # Create folder for this zoom level
        if lod_config:
            folder_name = f"Zoom {zoom}"
        else:
            folder_name = "Composited Tiles"

        folder = self.kml.newfolder(name=folder_name)

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

            # Add Region and LOD if configured
            if lod_config:
                min_lod, max_lod = self.calculate_lod_pixels(
                    zoom,
                    lod_config['min_zoom'],
                    lod_config['max_zoom']
                )

                # Create Region with LatLonAltBox matching tile bounds
                ground.region.latlonaltbox.north = bounds['north']
                ground.region.latlonaltbox.south = bounds['south']
                ground.region.latlonaltbox.east = bounds['east']
                ground.region.latlonaltbox.west = bounds['west']

                # Set LOD pixel thresholds
                ground.region.lod.minlodpixels = min_lod
                ground.region.lod.maxlodpixels = max_lod

            # Set draw order (higher zoom = drawn on top)
            ground.draworder = zoom

        logger.info(f"Added {len(tiles)} tiles at zoom {zoom} to KML")

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
