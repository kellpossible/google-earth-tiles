"""KMZ file generator."""

import asyncio
import logging
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import simplekml
from PIL import Image

from src.core.base_tile_generator import BaseTileGenerator
from src.core.tile_calculator import CHUNK_SIZE, TileCalculator
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition

logger = logging.getLogger(__name__)


class KMZGenerator(BaseTileGenerator):
    """Generator for KMZ files with composited layers."""

    def __init__(self, output_path: Path, progress_callback=None, enable_cache: bool = True):
        """
        Initialize KMZ generator.

        Args:
            output_path: Path for output KMZ file
            progress_callback: Optional callback(current, total, message) for progress updates
            enable_cache: Whether to use tile caching (default: True)
        """
        super().__init__(output_path, progress_callback, enable_cache)
        self.kml = simplekml.Kml()

    @staticmethod
    def calculate_lod_pixels(zoom: int, min_zoom: int, max_zoom: int) -> tuple[int, int]:
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

    def _add_separate_layer_tiles(
        self,
        layer_name: str,
        tiles_by_zoom: dict[int, list[tuple[Path, int, int, int]]],
        opacity: int,
        lod_config: dict | None = None,
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
            zoom_folder_name = f"Zoom {zoom_level}" if lod_config else f"{layer_name} Tiles"

            zoom_folder = layer_folder.newfolder(name=zoom_folder_name)

            # Add each tile as GroundOverlay
            for _tile_path, x, y, z in tiles:
                bounds = TileCalculator.tile_to_lat_lon_bounds(x, y, z)

                ground = zoom_folder.newgroundoverlay(name=f"Tile {z}/{x}/{y}")

                # Set icon path (relative to KMZ root)
                icon_path = f"files/tiles/{layer_name}/{z}_{x}_{y}.png"
                ground.icon.href = icon_path

                # Set geographic bounds
                ground.latlonbox.north = bounds["north"]
                ground.latlonbox.south = bounds["south"]
                ground.latlonbox.east = bounds["east"]
                ground.latlonbox.west = bounds["west"]

                # Apply KML-level opacity via color
                ground.color = kml_color

                # Add Region and LOD if configured
                if lod_config:
                    min_lod, max_lod = self.calculate_lod_pixels(
                        zoom_level, lod_config["min_zoom"], lod_config["max_zoom"]
                    )

                    ground.region.latlonaltbox.north = bounds["north"]
                    ground.region.latlonaltbox.south = bounds["south"]
                    ground.region.latlonaltbox.east = bounds["east"]
                    ground.region.latlonaltbox.west = bounds["west"]

                    ground.region.lod.minlodpixels = min_lod
                    ground.region.lod.maxlodpixels = max_lod

                # Set draw order
                ground.draworder = zoom_level

            logger.info(f"Added {len(tiles)} tiles for {layer_name} at zoom {zoom_level} to KML")

    def _add_attribution_overlay(self, attribution: str | None, layer_compositions: list[LayerComposition]):
        """
        Add attribution as a screen overlay in the bottom-left corner.

        Args:
            attribution: Attribution text (or None to auto-generate)
            layer_compositions: List of layer compositions for auto-generation
        """
        # Get attribution text
        if attribution:
            attr_text = attribution
        else:
            from src.utils.attribution import build_attribution_from_layers

            attr_text = build_attribution_from_layers(layer_compositions)

        # Only add overlay if we have attribution text
        if not attr_text:
            return

        # Create screen overlay
        screen = self.kml.newscreenoverlay(name="Attribution")
        screen.icon.href = ""  # No icon, just text via description
        screen.description = attr_text

        # Position in bottom-left corner
        screen.overlayxy = simplekml.OverlayXY(
            x=0, y=0, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction
        )
        # Type checker doesn't recognize Units.pixel, but it exists at runtime
        screen.screenxy = simplekml.ScreenXY(x=10, y=10, xunits=simplekml.Units.pixel, yunits=simplekml.Units.pixel)  # type: ignore[attr-defined]
        screen.size = simplekml.Size(x=0, y=0, xunits=simplekml.Units.pixel, yunits=simplekml.Units.pixel)  # type: ignore[attr-defined]

        logger.info("Added attribution screen overlay to KML")

    def _merge_extent_kml_features(self, extent_kml_path: Path):
        """
        Prepare KML features from extent file for merging.

        Stores features in self._extent_features_to_merge for
        post-processing after simplekml generates base KML.

        Args:
            extent_kml_path: Path to KML extent file
        """
        from src.utils.kml_extent import extract_kml_features

        try:
            # Extract features from extent KML
            features = extract_kml_features(extent_kml_path)

            if not features:
                logger.warning(f"No features found in extent KML to merge: {extent_kml_path}")
                return

            # Store features for later merging (after simplekml generates base KML)
            if not hasattr(self, "_extent_features_to_merge"):
                self._extent_features_to_merge = []

            self._extent_features_to_merge.extend(features)

            logger.info(f"Prepared {len(features)} features from extent KML for merging")

        except Exception as e:
            logger.error(f"Failed to prepare extent KML features for merging: {e}")
            # Non-fatal - continue with tile generation

    def _merge_kml_features_post_save(self, kml_path: Path, features: list):
        """
        Merge KML features into saved KML file (post-processing).

        This is necessary because simplekml doesn't support importing arbitrary
        KML elements. We generate the base KML with simplekml, then parse and
        enhance it with ElementTree.

        Args:
            kml_path: Path to KML file saved by simplekml
            features: List of ElementTree Elements to merge
        """
        import xml.etree.ElementTree as ET

        from src.utils.kml_extent import KML_NS

        try:
            # Parse the simplekml-generated KML
            tree = ET.parse(kml_path)
            root = tree.getroot()

            # Find the Document element
            doc = root.find(".//kml:Document", KML_NS)
            if doc is None:
                logger.error("No Document element found in generated KML")
                return

            # Create a Folder for extent features
            extent_folder = ET.SubElement(doc, f"{{{KML_NS['kml']}}}Folder")
            name_elem = ET.SubElement(extent_folder, f"{{{KML_NS['kml']}}}name")
            name_elem.text = "Extent Boundary"

            # Add all features to the folder
            for feature in features:
                extent_folder.append(feature)

            # Write back with XML declaration and proper formatting
            tree.write(
                kml_path,
                encoding="UTF-8",
                xml_declaration=True,
                method="xml",
            )

            logger.info(f"Merged {len(features)} features into KML")

        except Exception as e:
            logger.error(f"Failed to merge KML features post-save: {e}")

    async def create_kmz_async(
        self,
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
        web_compatible: bool = False,
        include_timestamp: bool = True,
        name: str | None = None,
        description: str | None = None,
        attribution: str | None = None,
        attribution_mode: str = "description",
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
            web_compatible: Enable Google Earth Web compatibility mode (default False)
            include_timestamp: Include timestamp in KML document description (default True)
            attribution: Global attribution string (optional, auto-generates from layers if None)
            attribution_mode: How to display attribution - "description" or "overlay" (default "description")

        Returns:
            Path to created KMZ file
        """
        if not layer_compositions:
            raise ValueError("No layer compositions provided for KMZ generation")

        if min_zoom > max_zoom:
            raise ValueError(f"min_zoom ({min_zoom}) cannot be greater than max_zoom ({max_zoom})")

        # Branch to web compatible generation if enabled
        if web_compatible:
            # Calculate optimal zoom for web compatible mode
            composited_layers, separate_layers = self.separate_layers_by_export_mode(layer_compositions)
            effective_layer_count = (1 if composited_layers else 0) + len(separate_layers)

            calculated_max_zoom = TileCalculator.find_max_web_compatible_zoom(
                extent.min_lon,
                extent.min_lat,
                extent.max_lon,
                extent.max_lat,
                effective_layer_count,
            )

            logger.info(
                f"Web compatible mode: Calculated max zoom {calculated_max_zoom} for {effective_layer_count} layer(s)"
            )

            # Determine actual zoom to use
            if calculated_max_zoom < min_zoom:
                raise ValueError(
                    f"Web compatible mode requires zoom <= {calculated_max_zoom} "
                    f"for {effective_layer_count} layer(s) within the extent, "
                    f"but min_zoom is {min_zoom}. Consider reducing min_zoom or the extent size."
                )

            actual_zoom = min(max_zoom, calculated_max_zoom)

            if actual_zoom < max_zoom:
                logger.warning(
                    f"Web compatible mode: Requested max_zoom={max_zoom} exceeds limit. "
                    f"Using zoom {actual_zoom} instead (calculated max: {calculated_max_zoom})."
                )

            logger.info(f"Web compatible mode: Using zoom {actual_zoom} (range: {min_zoom}-{max_zoom})")

            return await self._create_kmz_web_compatible(
                extent,
                actual_zoom,
                layer_compositions,
                include_timestamp,
                name,
                description,
                attribution,
                attribution_mode,
            )

        # Separate layers by export mode (handles single-layer special case)
        composited_layers, separate_layers = self.separate_layers_by_export_mode(layer_compositions)

        if not composited_layers and not separate_layers:
            raise ValueError("No enabled layers to export")

        # Set document metadata
        if name:
            self.kml.document.name = name
        elif min_zoom < max_zoom:
            self.kml.document.name = f"GSI Tiles - Zoom {min_zoom}-{max_zoom} (LOD)"
        else:
            self.kml.document.name = f"GSI Tiles - Zoom {max_zoom}"

        # Build description (conditionally include attribution based on mode)
        description_parts = []

        # Add user description if provided
        if description:
            description_parts.append(description)

        # Add attribution to description only if mode is "description"
        if attribution_mode == "description":
            if attribution:
                description_parts.append(attribution)
            else:
                from src.utils.attribution import build_attribution_from_layers

                auto_attr = build_attribution_from_layers(layer_compositions)
                if auto_attr:
                    description_parts.append(auto_attr)

        # Add base description
        description_parts.append("GSI Tiles from https://maps.gsi.go.jp")

        # Add timestamp if requested
        if include_timestamp:
            description_parts.append(f"Generated: {datetime.now().isoformat()}")

        self.kml.document.description = "\n\n".join(description_parts)

        # Create temporary directory for tiles
        temp_dir = Path(tempfile.mkdtemp())
        kml_temp_path = None

        try:
            logger.info(
                f"Using extent: {extent.min_lon:.6f}, {extent.min_lat:.6f} to {extent.max_lon:.6f}, {extent.max_lat:.6f}"
            )
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
                                processed_count, total_tiles, f"Compositing tile {processed_count}/{total_tiles}..."
                            )

                        tile_data = await self.compositor.composite_tile(x, y, zoom_level, composited_layers)

                        if tile_data:
                            tile_path = temp_dir / f"composited_{zoom_level}_{x}_{y}.png"
                            with open(tile_path, "wb") as f:
                                f.write(tile_data)
                            composited_tiles.append((tile_path, x, y, zoom_level))

                    composited_tiles_by_zoom[zoom_level] = composited_tiles
                    logger.info(f"Composited {len(composited_tiles)} tiles at zoom {zoom_level}")

            # Phase 2: Fetch tiles for separate layers
            separate_layers_tiles = {}
            for layer_comp in separate_layers:
                logger.info(f"Fetching separate layer: {layer_comp.layer_config.name}...")

                # Update progress before fetching (tiles will update within the method)
                tiles_by_zoom = await self.fetch_tiles_for_layer(extent, min_zoom, max_zoom, layer_comp, temp_dir)

                # Update progress after layer completion
                for tiles in tiles_by_zoom.values():
                    processed_count += len(tiles)

                if self.progress_callback:
                    self.progress_callback(processed_count, total_tiles, f"Fetched {layer_comp.layer_config.name}")

                separate_layers_tiles[layer_comp.layer_config.name] = tiles_by_zoom

            # Phase 3: Create KML
            if self.progress_callback:
                self.progress_callback(0, 1, "Creating KML document...")

            with tempfile.NamedTemporaryFile(mode="w", suffix=".kml", delete=False) as kml_file:
                kml_temp_path = Path(kml_file.name)

            lod_kml_config = None
            if min_zoom < max_zoom:
                lod_kml_config = {"min_zoom": min_zoom, "max_zoom": max_zoom}

            # Add composited tiles to KML
            if composited_layers:
                # If there are separate layers, nest composited tiles under "Layer: Base"
                base_folder = None
                if separate_layers:
                    base_folder = self.kml.newfolder(name="Layer: Base")

                for zoom_level in sorted(composited_tiles_by_zoom.keys(), reverse=True):
                    self._add_composited_tiles(
                        composited_tiles_by_zoom[zoom_level], zoom_level, lod_kml_config, parent_folder=base_folder
                    )

            # Add separate layers to KML
            for layer_comp in separate_layers:
                layer_name = layer_comp.layer_config.name
                if layer_name in separate_layers_tiles:
                    self._add_separate_layer_tiles(
                        layer_name, separate_layers_tiles[layer_name], layer_comp.opacity, lod_kml_config
                    )

            # Add screen overlay for attribution if mode is "overlay"
            if attribution_mode == "overlay":
                self._add_attribution_overlay(attribution, layer_compositions)

            # Save KML
            self.kml.save(str(kml_temp_path))

            # Merge extent KML features if requested
            if hasattr(self, "_extent_features_to_merge") and self._extent_features_to_merge:
                self._merge_kml_features_post_save(kml_temp_path, self._extent_features_to_merge)
                self._extent_features_to_merge = []

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
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
        web_compatible: bool = False,
        include_timestamp: bool = True,
        name: str | None = None,
        description: str | None = None,
        attribution: str | None = None,
        attribution_mode: str = "description",
    ) -> Path:
        """
        Create KMZ file with composited tiles and optional LOD (synchronous wrapper).

        Args:
            extent: Geographic extent (Extent object)
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of LayerComposition objects
            web_compatible: Enable Google Earth Web compatibility mode (default False)
            include_timestamp: Include timestamp in KML document description (default True)
            attribution: Global attribution string (optional, auto-generates from layers if None)
            attribution_mode: How to display attribution - "description" or "overlay" (default "description")

        Returns:
            Path to created KMZ file
        """
        # Run async version (Python 3.14 compatible)
        return asyncio.run(
            self.create_kmz_async(
                extent,
                min_zoom,
                max_zoom,
                layer_compositions,
                web_compatible,
                include_timestamp,
                name,
                description,
                attribution,
                attribution_mode,
            )
        )

    def _add_composited_tiles(
        self, tiles: list[tuple[Path, int, int, int]], zoom: int, lod_config: dict | None = None, parent_folder=None
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
        folder_name = f"Zoom {zoom}" if lod_config else "Composited Tiles"

        # Use parent folder if provided, otherwise use root kml
        kml_or_folder = parent_folder if parent_folder else self.kml
        folder = kml_or_folder.newfolder(name=folder_name)

        # Add each tile as GroundOverlay
        for _tile_path, x, y, z in tiles:
            bounds = TileCalculator.tile_to_lat_lon_bounds(x, y, z)

            ground = folder.newgroundoverlay(name=f"Tile {z}/{x}/{y}")

            # Set icon path (relative to KMZ root)
            icon_path = f"files/tiles/composited/{z}_{x}_{y}.png"
            ground.icon.href = icon_path

            # Set geographic bounds
            ground.latlonbox.north = bounds["north"]
            ground.latlonbox.south = bounds["south"]
            ground.latlonbox.east = bounds["east"]
            ground.latlonbox.west = bounds["west"]

            # Add Region and LOD if configured
            if lod_config:
                min_lod, max_lod = self.calculate_lod_pixels(zoom, lod_config["min_zoom"], lod_config["max_zoom"])

                # Create Region with LatLonAltBox matching tile bounds
                ground.region.latlonaltbox.north = bounds["north"]
                ground.region.latlonaltbox.south = bounds["south"]
                ground.region.latlonaltbox.east = bounds["east"]
                ground.region.latlonaltbox.west = bounds["west"]

                # Set LOD pixel thresholds
                ground.region.lod.minlodpixels = min_lod
                ground.region.lod.maxlodpixels = max_lod

            # Set draw order (higher zoom = drawn on top)
            ground.draworder = zoom

        logger.info(f"Added {len(tiles)} tiles at zoom {zoom} to KML")

    def _create_kmz_archive(
        self,
        kml_path: Path,
        composited_tiles: list[tuple[Path, int, int, int]],
    ):
        """
        Create KMZ archive with KML and composited tile images.

        Args:
            kml_path: Path to KML file
            composited_tiles: List of (tile_path, x, y, z) tuples
        """
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(self.output_path, "w", zipfile.ZIP_DEFLATED) as kmz:
            # Add KML file (must be named doc.kml at root)
            kmz.write(kml_path, "doc.kml")

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
        composited_tiles: list[tuple[Path, int, int, int]],
        separate_layers_tiles: dict[str, dict[int, list[tuple[Path, int, int, int]]]],
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

        with zipfile.ZipFile(self.output_path, "w", zipfile.ZIP_DEFLATED) as kmz:
            # Add KML file (must be named doc.kml at root)
            kmz.write(kml_path, "doc.kml")

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

        logger.info(
            f"KMZ archive created with {composited_count} composited tiles and {separate_count} separate layer tiles"
        )

    def _create_chunks_from_tiles(
        self,
        tiles: list[tuple[Path, int, int, int]],
        chunk_grid: list[dict],
        zoom: int,
        temp_dir: Path,
        output_prefix: str,
    ) -> list[dict]:
        """
        Create chunks by grouping and merging tiles.

        Args:
            tiles: List of (tile_path, x, y, z) for tiles already saved to disk
            chunk_grid: Grid of chunks with tile coordinates and bounds
            zoom: Zoom level
            temp_dir: Temporary directory for chunk storage
            output_prefix: Prefix for chunk filenames (e.g., "composited" or layer name)

        Returns:
            List of chunk dicts with chunk_x, chunk_y, bounds, image_path
        """
        chunks = []

        # Create a map of (x, y) -> tile_path for quick lookup
        tile_map = {(x, y): path for path, x, y, z in tiles}

        for chunk_info in chunk_grid:
            chunk_tiles = []

            # Collect tiles for this chunk
            for x, y in chunk_info["tiles"]:
                if (x, y) in tile_map:
                    tile_path = tile_map[(x, y)]
                    chunk_tiles.append((tile_path, x, y, zoom))

            if chunk_tiles:
                # Merge tiles into chunk
                chunk_image = self.merge_tiles_to_chunk(chunk_tiles, zoom)

                # Save chunk
                chunk_x = chunk_info["chunk_x"]
                chunk_y = chunk_info["chunk_y"]
                chunk_path = temp_dir / f"chunk_{output_prefix}_{zoom}_{chunk_x}_{chunk_y}.png"
                chunk_image.save(chunk_path, format="PNG")
                chunk_image.close()

                chunks.append(
                    {"chunk_x": chunk_x, "chunk_y": chunk_y, "bounds": chunk_info["bounds"], "image_path": chunk_path}
                )

                # Clean up individual tile files
                for tile_path, _, _, _ in chunk_tiles:
                    if tile_path.exists():
                        tile_path.unlink()

        return chunks

    def merge_tiles_to_chunk(
        self, tiles: list[tuple[Path, int, int, int]], zoom: int, chunk_size: int = CHUNK_SIZE
    ) -> Image.Image:
        """
        Merge 256x256 tiles into a single chunk image.

        Args:
            tiles: List of (tile_path, x, y, z) tuples
            zoom: Zoom level (for coordinate calculation)
            chunk_size: Number of tiles per chunk dimension (default 2 for 512x512)

        Returns:
            PIL Image of merged chunk (up to chunk_size*256 x chunk_size*256)
        """
        if not tiles:
            raise ValueError("Cannot merge empty tile list")

        # Find tile coordinate bounds
        x_coords = [x for _, x, y, z in tiles]
        y_coords = [y for _, x, y, z in tiles]
        x_min, y_min = min(x_coords), min(y_coords)
        x_max, y_max = max(x_coords), max(y_coords)

        # Create canvas (may be smaller than chunk_size*256 for partial chunks at edges)
        width = (x_max - x_min + 1) * 256
        height = (y_max - y_min + 1) * 256
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # Place each tile
        for tile_path, x, y, _z in tiles:
            if not tile_path.exists():
                logger.warning(f"Tile not found: {tile_path}")
                continue

            try:
                tile_img = Image.open(tile_path)

                # Sanity check: ensure tile is 256x256 as expected
                if tile_img.size != (256, 256):
                    logger.error(f"Tile size mismatch: expected 256x256, got {tile_img.size} for {tile_path}")
                    tile_img.close()
                    continue

                # Calculate position in canvas
                paste_x = (x - x_min) * 256
                paste_y = (y - y_min) * 256

                canvas.paste(tile_img, (paste_x, paste_y))
                tile_img.close()
            except Exception as e:
                logger.warning(f"Error loading tile {tile_path}: {e}")

        return canvas

    async def _create_kmz_web_compatible(
        self,
        extent: Extent,
        zoom: int,
        layer_compositions: list[LayerComposition],
        include_timestamp: bool = True,
        name: str | None = None,
        description: str | None = None,
        attribution: str | None = None,
        attribution_mode: str = "description",
    ) -> Path:
        """
        Create web-compatible KMZ with merged chunks.

        Args:
            extent: Geographic extent
            zoom: Single zoom level (min_zoom == max_zoom)
            layer_compositions: Layer compositions

        Returns:
            Path to created KMZ file
        """
        # Separate layers
        composited_layers, separate_layers = self.separate_layers_by_export_mode(layer_compositions)

        # Set document metadata
        if name:
            self.kml.document.name = name
        else:
            self.kml.document.name = f"GSI Tiles - Zoom {zoom} (Web Compatible)"

        # Build description (conditionally include attribution based on mode)
        description_parts = []

        # Add user description if provided
        if description:
            description_parts.append(description)

        # Add attribution to description only if mode is "description"
        if attribution_mode == "description":
            if attribution:
                description_parts.append(attribution)
            else:
                from src.utils.attribution import build_attribution_from_layers

                auto_attr = build_attribution_from_layers(layer_compositions)
                if auto_attr:
                    description_parts.append(auto_attr)

        # Add base description
        description_parts.append("GSI Tiles from https://maps.gsi.go.jp")
        description_parts.append("Optimized for Google Earth Web")

        # Add timestamp if requested
        if include_timestamp:
            description_parts.append(f"Generated: {datetime.now().isoformat()}")

        self.kml.document.description = "\n\n".join(description_parts)

        temp_dir = Path(tempfile.mkdtemp())
        kml_temp_path = None

        try:
            # Get all tiles at this zoom
            tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom
            )

            # Calculate chunk grid (2x2 tiles per chunk = 512x512 pixels)
            chunk_grid = TileCalculator.get_chunk_grid(tiles_at_zoom, zoom, chunk_size=CHUNK_SIZE)

            logger.info(f"Web compatible mode: {len(chunk_grid)} chunks at zoom {zoom}")

            # Calculate progress
            total_chunks = len(chunk_grid)
            if composited_layers:
                total_chunks += len(chunk_grid)
            for _sep_layer in separate_layers:
                total_chunks += len(chunk_grid)

            current_chunk = 0

            # Phase 1: Generate composited chunks
            composited_chunks = []
            if composited_layers:
                logger.info("Fetching composited tiles...")

                # Get all tiles in extent at this zoom
                tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                    extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom
                )

                # Fetch all composited tiles
                composited_tiles = []
                for x, y in tiles_at_zoom:
                    if self.progress_callback:
                        progress = len(composited_tiles) / len(tiles_at_zoom) if tiles_at_zoom else 0
                        self.progress_callback(
                            int(progress * len(chunk_grid)),
                            total_chunks,
                            f"Fetching composited tiles ({len(composited_tiles)}/{len(tiles_at_zoom)})...",
                        )

                    # Compositor automatically handles resampling from nearest available zoom
                    tile_data = await self.compositor.composite_tile(x, y, zoom, composited_layers)

                    if tile_data:
                        tile_path = temp_dir / f"tile_composited_{zoom}_{x}_{y}.png"
                        with open(tile_path, "wb") as f:
                            f.write(tile_data)
                        composited_tiles.append((tile_path, x, y, zoom))

                # Create chunks from tiles using shared helper
                logger.info(f"Creating {len(chunk_grid)} composited chunks...")
                composited_chunks = self._create_chunks_from_tiles(
                    composited_tiles, chunk_grid, zoom, temp_dir, "composited"
                )

                current_chunk += len(chunk_grid)
                if self.progress_callback:
                    self.progress_callback(
                        current_chunk, total_chunks, f"Created {len(composited_chunks)} composited chunks"
                    )

            # Phase 2: Generate separate layer chunks
            separate_chunks_by_layer = {}
            for layer_comp in separate_layers:
                layer_name = layer_comp.layer_config.name
                logger.info(f"Fetching tiles for layer: {layer_name}...")

                # Fetch tiles using shared method (handles opacity=100 and resampling)
                tiles_by_zoom = await self.fetch_tiles_for_layer(extent, zoom, zoom, layer_comp, temp_dir)

                # Extract tiles for the single zoom level
                layer_tiles = tiles_by_zoom.get(zoom, [])

                # Create chunks from tiles using shared helper
                logger.info(f"Creating {len(chunk_grid)} chunks for layer: {layer_name}...")
                layer_chunks = self._create_chunks_from_tiles(layer_tiles, chunk_grid, zoom, temp_dir, layer_name)

                separate_chunks_by_layer[layer_name] = layer_chunks

                current_chunk += len(chunk_grid)
                if self.progress_callback:
                    self.progress_callback(
                        current_chunk, total_chunks, f"Created {len(layer_chunks)} chunks for {layer_name}"
                    )

            # Phase 3: Create KML
            with tempfile.NamedTemporaryFile(mode="w", suffix=".kml", delete=False) as kml_file:
                kml_temp_path = Path(kml_file.name)

            # Add chunks to KML
            if composited_chunks:
                base_folder = None
                if separate_layers:
                    base_folder = self.kml.newfolder(name="Layer: Base")

                self._add_composited_chunks(composited_chunks, zoom, base_folder)

            for layer_comp in separate_layers:
                layer_name = layer_comp.layer_config.name
                if layer_name in separate_chunks_by_layer:
                    self._add_separate_layer_chunks(
                        layer_name, separate_chunks_by_layer[layer_name], zoom, layer_comp.opacity
                    )

            # Add screen overlay for attribution if mode is "overlay"
            if attribution_mode == "overlay":
                self._add_attribution_overlay(attribution, layer_compositions)

            # Save KML
            self.kml.save(str(kml_temp_path))

            # Merge extent KML features if requested
            if hasattr(self, "_extent_features_to_merge") and self._extent_features_to_merge:
                self._merge_kml_features_post_save(kml_temp_path, self._extent_features_to_merge)
                self._extent_features_to_merge = []

            # Phase 4: Create KMZ archive
            self._create_kmz_archive_chunks(kml_temp_path, composited_chunks, separate_chunks_by_layer, zoom)

            logger.info(f"Created web-compatible KMZ file: {self.output_path}")
            return self.output_path

        finally:
            await self.compositor.close()
            if kml_temp_path and kml_temp_path.exists():
                kml_temp_path.unlink()

    def _add_composited_chunks(self, chunks: list[dict], zoom: int, parent_folder=None):
        """
        Add composited tile chunks to KML (web compatible mode).

        Args:
            chunks: List of chunk dicts with 'chunk_x', 'chunk_y', 'bounds', 'image_path'
            zoom: Zoom level
            parent_folder: Optional parent folder
        """
        if not chunks:
            return

        folder_name = f"Composited Tiles (Zoom {zoom})"
        kml_or_folder = parent_folder if parent_folder else self.kml
        folder = kml_or_folder.newfolder(name=folder_name)

        for chunk in chunks:
            chunk_x = chunk["chunk_x"]
            chunk_y = chunk["chunk_y"]
            bounds = chunk["bounds"]

            ground = folder.newgroundoverlay(name=f"Chunk {zoom}/{chunk_x}/{chunk_y}")

            # Set icon path (relative to KMZ root)
            icon_path = f"files/chunks/composited/{zoom}_{chunk_x}_{chunk_y}.png"
            ground.icon.href = icon_path

            # Set geographic bounds
            ground.latlonbox.north = bounds["north"]
            ground.latlonbox.south = bounds["south"]
            ground.latlonbox.east = bounds["east"]
            ground.latlonbox.west = bounds["west"]

            # NO Region/LOD elements in web compatible mode

            # Set draw order
            ground.draworder = zoom

        logger.info(f"Added {len(chunks)} chunks at zoom {zoom} to KML")

    def _add_separate_layer_chunks(self, layer_name: str, chunks: list[dict], zoom: int, opacity: int):
        """
        Add separate layer chunks to KML (web compatible mode).

        Args:
            layer_name: Layer name
            chunks: List of chunk dicts
            zoom: Zoom level
            opacity: Layer opacity (0-100)
        """
        # Create folder for this layer
        layer_folder = self.kml.newfolder(name=f"Layer: {layer_name}")

        # Convert opacity to KML color (alpha in hex)
        alpha_value = int((opacity / 100.0) * 255)
        alpha_hex = f"{alpha_value:02x}"
        kml_color = f"{alpha_hex}ffffff"

        for chunk in chunks:
            chunk_x = chunk["chunk_x"]
            chunk_y = chunk["chunk_y"]
            bounds = chunk["bounds"]

            ground = layer_folder.newgroundoverlay(name=f"Chunk {zoom}/{chunk_x}/{chunk_y}")

            icon_path = f"files/chunks/{layer_name}/{zoom}_{chunk_x}_{chunk_y}.png"
            ground.icon.href = icon_path

            ground.latlonbox.north = bounds["north"]
            ground.latlonbox.south = bounds["south"]
            ground.latlonbox.east = bounds["east"]
            ground.latlonbox.west = bounds["west"]

            ground.color = kml_color

            # NO Region/LOD elements

            ground.draworder = zoom

        logger.info(f"Added {len(chunks)} chunks for {layer_name} at zoom {zoom} to KML")

    def _create_kmz_archive_chunks(
        self, kml_path: Path, composited_chunks: list[dict], separate_chunks_by_layer: dict[str, list[dict]], zoom: int
    ):
        """
        Create KMZ archive with chunk images.

        Args:
            kml_path: Path to KML file
            composited_chunks: List of composited chunk dicts
            separate_chunks_by_layer: Dict of layer_name -> chunk list
            zoom: Zoom level
        """
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(self.output_path, "w", zipfile.ZIP_DEFLATED) as kmz:
            # Add KML
            kmz.write(kml_path, "doc.kml")

            # Add composited chunks
            for chunk in composited_chunks:
                chunk_x = chunk["chunk_x"]
                chunk_y = chunk["chunk_y"]
                image_path = chunk["image_path"]

                arcname = f"files/chunks/composited/{zoom}_{chunk_x}_{chunk_y}.png"
                kmz.write(image_path, arcname)

            # Add separate layer chunks
            for layer_name, chunks in separate_chunks_by_layer.items():
                for chunk in chunks:
                    chunk_x = chunk["chunk_x"]
                    chunk_y = chunk["chunk_y"]
                    image_path = chunk["image_path"]

                    arcname = f"files/chunks/{layer_name}/{zoom}_{chunk_x}_{chunk_y}.png"
                    kmz.write(image_path, arcname)

        total_chunks = len(composited_chunks) + sum(len(chunks) for chunks in separate_chunks_by_layer.values())
        logger.info(f"KMZ archive created with {total_chunks} chunks")
