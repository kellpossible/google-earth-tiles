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

    @staticmethod
    def _separate_layers_by_export_mode(
        layer_compositions: List[LayerComposition]
    ) -> Tuple[List[LayerComposition], List[LayerComposition]]:
        """
        Separate layers into composite and separate groups.

        When only one layer is enabled, it's automatically treated as separate
        to use KML-level opacity instead of pixel-level compositing.

        Args:
            layer_compositions: All layer compositions

        Returns:
            Tuple of (composited_layers, separate_layers)
        """
        composited = []
        separate = []

        enabled_layers = [comp for comp in layer_compositions if comp.enabled]

        # Special case: if only one layer, always treat as separate
        # (use KML-level opacity instead of pixel-level compositing)
        if len(enabled_layers) == 1:
            return [], enabled_layers

        # Multi-layer case: respect export_mode setting
        for comp in enabled_layers:
            if comp.export_mode == "separate":
                separate.append(comp)
            else:
                composited.append(comp)

        return composited, separate

    async def _fetch_separate_layer_tiles(
        self,
        extent: 'Extent',
        min_zoom: int,
        max_zoom: int,
        layer_composition: LayerComposition,
        temp_dir: Path
    ) -> Dict[int, List[Tuple[Path, int, int, int]]]:
        """
        Fetch tiles for a single separate layer, reusing compositor logic.

        This method leverages the existing TileCompositor to handle all
        fetching and resampling logic, avoiding code duplication.

        Args:
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_composition: Layer composition for this layer
            temp_dir: Temporary directory for tile storage

        Returns:
            Dictionary mapping zoom level to list of (tile_path, x, y, z) tuples
        """
        layer_name = layer_composition.layer_config.name
        tiles_by_zoom = {}

        # Create a temporary composition with opacity=100 to avoid pixel-level opacity
        # The compositor will handle all fetching and resampling logic
        temp_composition = layer_composition.copy()
        temp_composition.opacity = 100  # No pixel-level opacity for separate layers

        for zoom_level in range(min_zoom, max_zoom + 1):
            logger.info(f"Fetching {layer_name} tiles at zoom {zoom_level}...")

            # Get tiles in extent
            tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom_level
            )

            fetched_tiles = []
            for x, y in tiles_at_zoom:
                # Update progress if callback exists
                if self.progress_callback:
                    # Progress tracking will be handled by the main loop
                    pass

                # Use compositor to fetch and resample tile
                # Compositor handles all LOD logic (get_available_zooms, find_best_source_zoom, resampling)
                tile_data = await self.compositor.composite_tile(
                    x, y, zoom_level,
                    [temp_composition],  # Single-layer "composition"
                    output_min_zoom=min_zoom,
                    output_max_zoom=max_zoom
                )

                if tile_data:
                    # Save to temp file with layer name prefix
                    tile_path = temp_dir / f"{layer_name}_{zoom_level}_{x}_{y}.png"
                    with open(tile_path, 'wb') as f:
                        f.write(tile_data)
                    fetched_tiles.append((tile_path, x, y, zoom_level))

            tiles_by_zoom[zoom_level] = fetched_tiles
            logger.info(f"Fetched {len(fetched_tiles)} tiles for {layer_name} at zoom {zoom_level}")

        return tiles_by_zoom

    def _add_separate_layer_tiles(
        self,
        layer_name: str,
        tiles_by_zoom: Dict[int, List[Tuple[Path, int, int, int]]],
        opacity: int,
        lod_config: dict = None
    ):
        """
        Add a separate layer's tiles to KML with its own folder and KML-level opacity.

        Args:
            layer_name: Name of the layer
            tiles_by_zoom: Dictionary mapping zoom to list of (tile_path, x, y, z) tuples
            opacity: Opacity 0-100 for KML-level transparency
            lod_config: Optional LOD config with 'min_zoom' and 'max_zoom'
        """
        # Create top-level folder for this layer
        layer_folder = self.kml.newfolder(name=f"Layer: {layer_name}")

        # Convert opacity (0-100) to KML alpha (00-FF in hex)
        # KML alpha: 00 = transparent, FF = opaque
        alpha_value = int((opacity / 100.0) * 255)
        alpha_hex = f"{alpha_value:02x}"
        # KML color format: aabbggrr (alpha, blue, green, red)
        # For opacity-only control, use white (ffffff) with opacity alpha
        kml_color = f"{alpha_hex}ffffff"

        for zoom_level in sorted(tiles_by_zoom.keys(), reverse=True):
            tiles = tiles_by_zoom[zoom_level]
            if not tiles:
                continue

            # Create folder for this zoom level
            if lod_config:
                zoom_folder_name = f"Zoom {zoom_level}"
            else:
                zoom_folder_name = f"{layer_name} Tiles"

            zoom_folder = layer_folder.newfolder(name=zoom_folder_name)

            # Add each tile as GroundOverlay
            for tile_path, x, y, z in tiles:
                bounds = TileCalculator.tile_to_lat_lon_bounds(x, y, z)

                ground = zoom_folder.newgroundoverlay(name=f"Tile {z}/{x}/{y}")

                # Set icon path (relative to KMZ root)
                icon_path = f"files/tiles/{layer_name}/{z}_{x}_{y}.png"
                ground.icon.href = icon_path

                # Set geographic bounds
                ground.latlonbox.north = bounds['north']
                ground.latlonbox.south = bounds['south']
                ground.latlonbox.east = bounds['east']
                ground.latlonbox.west = bounds['west']

                # Apply KML-level opacity via color
                ground.color = kml_color

                # Add Region and LOD if configured
                if lod_config:
                    min_lod, max_lod = self.calculate_lod_pixels(
                        zoom_level,
                        lod_config['min_zoom'],
                        lod_config['max_zoom']
                    )

                    ground.region.latlonaltbox.north = bounds['north']
                    ground.region.latlonaltbox.south = bounds['south']
                    ground.region.latlonaltbox.east = bounds['east']
                    ground.region.latlonaltbox.west = bounds['west']

                    ground.region.lod.minlodpixels = min_lod
                    ground.region.lod.maxlodpixels = max_lod

                # Set draw order
                ground.draworder = zoom_level

            logger.info(f"Added {len(tiles)} tiles for {layer_name} at zoom {zoom_level} to KML")

    async def create_kmz_async(
        self,
        extent: 'Extent',
        min_zoom: int,
        max_zoom: int,
        layer_compositions: List[LayerComposition]
    ) -> Path:
        """
        Create KMZ file with composited and/or separate layers.

        Supports both composited layers (pixel-level opacity and blending) and
        separate layers (KML-level opacity). Single layers are automatically
        treated as separate to use KML-level opacity.

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

        # Separate layers by export mode (handles single-layer special case)
        composited_layers, separate_layers = self._separate_layers_by_export_mode(layer_compositions)

        if not composited_layers and not separate_layers:
            raise ValueError("No enabled layers to export")

        # Set document metadata
        if min_zoom < max_zoom:
            self.kml.document.name = f"GSI Tiles - Zoom {min_zoom}-{max_zoom} (LOD)"
        else:
            self.kml.document.name = f"GSI Tiles - Zoom {max_zoom}"
        self.kml.document.description = f"Generated: {datetime.now().isoformat()}"

        # Create temporary directory for tiles
        temp_dir = Path(tempfile.mkdtemp())
        kml_temp_path = None

        try:
            logger.info(f"Using extent: {extent.min_lon:.6f}, {extent.min_lat:.6f} to {extent.max_lon:.6f}, {extent.max_lat:.6f}")
            logger.info(f"Composited layers: {len(composited_layers)}, Separate layers: {len(separate_layers)}")

            # Calculate total tiles for progress tracking
            total_tiles = 0
            for zoom_level in range(min_zoom, max_zoom + 1):
                tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                    extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom_level
                )
                # Count composited tiles + separate layer tiles
                if composited_layers:
                    total_tiles += len(tiles_at_zoom)
                total_tiles += len(tiles_at_zoom) * len(separate_layers)

            processed_count = 0

            # Phase 1: Composite tiles (if any composited layers)
            composited_tiles_by_zoom = {}
            if composited_layers:
                logger.info(f"Compositing {len(composited_layers)} layers together...")
                for zoom_level in range(min_zoom, max_zoom + 1):
                    logger.info(f"Compositing tiles at zoom {zoom_level}...")

                    tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                        extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom_level
                    )

                    composited_tiles = []
                    for x, y in tiles_at_zoom:
                        processed_count += 1

                        if self.progress_callback:
                            self.progress_callback(
                                processed_count,
                                total_tiles,
                                f"Compositing tile {processed_count}/{total_tiles}..."
                            )

                        tile_data = await self.compositor.composite_tile(
                            x, y, zoom_level, composited_layers,
                            output_min_zoom=min_zoom,
                            output_max_zoom=max_zoom
                        )

                        if tile_data:
                            tile_path = temp_dir / f"composited_{zoom_level}_{x}_{y}.png"
                            with open(tile_path, 'wb') as f:
                                f.write(tile_data)
                            composited_tiles.append((tile_path, x, y, zoom_level))

                    composited_tiles_by_zoom[zoom_level] = composited_tiles
                    logger.info(f"Composited {len(composited_tiles)} tiles at zoom {zoom_level}")

            # Phase 2: Fetch tiles for separate layers
            separate_layers_tiles = {}
            for layer_comp in separate_layers:
                logger.info(f"Fetching separate layer: {layer_comp.layer_config.name}...")

                # Update progress before fetching (tiles will update within the method)
                tiles_by_zoom = await self._fetch_separate_layer_tiles(
                    extent, min_zoom, max_zoom, layer_comp, temp_dir
                )

                # Update progress after layer completion
                for tiles in tiles_by_zoom.values():
                    processed_count += len(tiles)

                if self.progress_callback:
                    self.progress_callback(
                        processed_count,
                        total_tiles,
                        f"Fetched {layer_comp.layer_config.name}"
                    )

                separate_layers_tiles[layer_comp.layer_config.name] = tiles_by_zoom

            # Phase 3: Create KML
            if self.progress_callback:
                self.progress_callback(0, 1, "Creating KML document...")

            with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as kml_file:
                kml_temp_path = Path(kml_file.name)

            lod_kml_config = None
            if min_zoom < max_zoom:
                lod_kml_config = {'min_zoom': min_zoom, 'max_zoom': max_zoom}

            # Add composited tiles to KML
            if composited_layers:
                # If there are separate layers, nest composited tiles under "Layer: Base"
                base_folder = None
                if separate_layers:
                    base_folder = self.kml.newfolder(name="Layer: Base")

                for zoom_level in sorted(composited_tiles_by_zoom.keys(), reverse=True):
                    self._add_composited_tiles(
                        composited_tiles_by_zoom[zoom_level],
                        zoom_level,
                        lod_kml_config,
                        parent_folder=base_folder
                    )

            # Add separate layers to KML
            for layer_comp in separate_layers:
                layer_name = layer_comp.layer_config.name
                if layer_name in separate_layers_tiles:
                    self._add_separate_layer_tiles(
                        layer_name,
                        separate_layers_tiles[layer_name],
                        layer_comp.opacity,
                        lod_kml_config
                    )

            # Save KML
            self.kml.save(str(kml_temp_path))

            # Phase 4: Create KMZ archive
            if self.progress_callback:
                self.progress_callback(0, 1, "Creating KMZ archive...")

            # Collect all composited tiles
            all_composited_tiles = []
            for tiles in composited_tiles_by_zoom.values():
                all_composited_tiles.extend(tiles)

            # Create KMZ with multi-layer support
            self._create_kmz_archive_multi(kml_temp_path, all_composited_tiles, separate_layers_tiles)

            logger.info(f"Created KMZ file: {self.output_path}")
            return self.output_path

        finally:
            # Cleanup
            await self.compositor.close()
            if kml_temp_path and kml_temp_path.exists():
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
        lod_config: dict = None,
        parent_folder=None
    ):
        """
        Add composited tiles to the KML document.

        Args:
            tiles: List of (tile_path, x, y, z) tuples
            zoom: Zoom level for these tiles
            lod_config: Optional LOD config with 'min_zoom' and 'max_zoom'
            parent_folder: Optional parent folder to nest zoom folders under
        """
        if not tiles:
            return

        # Create folder for this zoom level
        if lod_config:
            folder_name = f"Zoom {zoom}"
        else:
            folder_name = "Composited Tiles"

        # Use parent folder if provided, otherwise use root kml
        kml_or_folder = parent_folder if parent_folder else self.kml
        folder = kml_or_folder.newfolder(name=folder_name)

        # Add each tile as GroundOverlay
        for tile_path, x, y, z in tiles:
            bounds = TileCalculator.tile_to_lat_lon_bounds(x, y, z)

            ground = folder.newgroundoverlay(name=f"Tile {z}/{x}/{y}")

            # Set icon path (relative to KMZ root)
            icon_path = f"files/tiles/composited/{z}_{x}_{y}.png"
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

                # Archive path: files/tiles/composited/{z}_{x}_{y}.png
                arcname = f"files/tiles/composited/{z}_{x}_{y}.png"
                kmz.write(tile_path, arcname)

        logger.info(f"KMZ archive created with {len(composited_tiles)} composited tiles")

    def _create_kmz_archive_multi(
        self,
        kml_path: Path,
        composited_tiles: List[Tuple[Path, int, int, int]],
        separate_layers_tiles: Dict[str, Dict[int, List[Tuple[Path, int, int, int]]]]
    ):
        """
        Create KMZ archive with KML and tile images organized by layer.

        Args:
            kml_path: Path to KML file
            composited_tiles: List of (tile_path, x, y, z) tuples for composited tiles
            separate_layers_tiles: Dictionary mapping layer_name to tiles_by_zoom
        """
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(self.output_path, 'w', zipfile.ZIP_DEFLATED) as kmz:
            # Add KML file (must be named doc.kml at root)
            kmz.write(kml_path, 'doc.kml')

            # Add composited tile images
            composited_count = 0
            for tile_path, x, y, z in composited_tiles:
                if not tile_path.exists():
                    logger.warning(f"Composited tile file not found: {tile_path}")
                    continue

                # Archive path: files/tiles/composited/{z}_{x}_{y}.png
                arcname = f"files/tiles/composited/{z}_{x}_{y}.png"
                kmz.write(tile_path, arcname)
                composited_count += 1

            # Add separate layer tile images
            separate_count = 0
            for layer_name, tiles_by_zoom in separate_layers_tiles.items():
                for tiles in tiles_by_zoom.values():
                    for tile_path, x, y, z in tiles:
                        if not tile_path.exists():
                            logger.warning(f"Separate layer tile file not found: {tile_path}")
                            continue

                        # Archive path: files/tiles/{layer_name}/{z}_{x}_{y}.png
                        arcname = f"files/tiles/{layer_name}/{z}_{x}_{y}.png"
                        kmz.write(tile_path, arcname)
                        separate_count += 1

        logger.info(f"KMZ archive created with {composited_count} composited tiles and {separate_count} separate layer tiles")
