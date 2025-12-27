"""GeoTIFF output format handler."""

import asyncio
import logging
from pathlib import Path

from src.core.geotiff_generator import GeoTIFFGenerator
from src.core.tile_calculator import TileCalculator
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition
from src.utils.attribution import build_attribution_from_layers

logger = logging.getLogger(__name__)


class GeoTIFFOutputHandler:
    """Handler for GeoTIFF output format.

    Implements the OutputHandler protocol for generating GeoTIFF files with
    optional pyramids, compression, and both composite and separate layer export modes.
    """

    @staticmethod
    def get_type_name() -> str:
        """Get the unique type identifier for this output format."""
        return "geotiff"

    @staticmethod
    def get_display_name() -> str:
        """Get the human-readable display name for this output format."""
        return "GeoTIFF"

    @staticmethod
    def get_file_extension() -> str:
        """Get the default file extension for this output format."""
        return "tif"

    @staticmethod
    def get_file_filter() -> str:
        """Get the file filter string for file dialogs."""
        return "GeoTIFF Files (*.tif *.tiff)"

    @staticmethod
    def get_default_options() -> dict:
        """Get default GeoTIFF-specific options."""
        return {
            "compression": "lzw",  # "lzw", "deflate", "jpeg", "none"
            "export_mode": "composite",  # "composite" or "separate"
            "multi_zoom": True,  # Include pyramids for multi-zoom support
            "jpeg_quality": 80,  # 1-100 for JPEG compression
            "tiled": True,  # Use tiled GeoTIFF format
            "tile_size": 256,  # Internal tile size (256 or 512)
        }

    @staticmethod
    def validate_options(options: dict) -> None:
        """Validate GeoTIFF-specific options.

        Args:
            options: Dictionary of options to validate

        Raises:
            ValueError: If options are invalid
        """
        if "compression" in options and options["compression"] not in ["lzw", "deflate", "jpeg", "none"]:
            raise ValueError("compression must be 'lzw', 'deflate', 'jpeg', or 'none'")

        if "export_mode" in options and options["export_mode"] not in ["composite", "separate"]:
            raise ValueError("export_mode must be 'composite' or 'separate'")

        if "multi_zoom" in options and not isinstance(options["multi_zoom"], bool):
            raise ValueError("multi_zoom must be a boolean")

        if "jpeg_quality" in options:
            quality = options["jpeg_quality"]
            if not isinstance(quality, int) or not 1 <= quality <= 100:
                raise ValueError("jpeg_quality must be an integer between 1 and 100")

        if "tiled" in options and not isinstance(options["tiled"], bool):
            raise ValueError("tiled must be a boolean")

        if "tile_size" in options and options["tile_size"] not in [256, 512]:
            raise ValueError("tile_size must be 256 or 512")

    def generate(
        self,
        output_path: Path,
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
        progress_callback=None,
        name: str | None = None,
        description: str | None = None,
        attribution: str | None = None,
        **options,
    ) -> Path:
        """Generate GeoTIFF file(s).

        Args:
            output_path: Path where the GeoTIFF should be saved
            extent: Geographic extent to generate
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions to include
            progress_callback: Optional callback for progress updates
            name: Global name/title for the tileset (unused for GeoTIFF)
            description: Global description for the tileset (unused for GeoTIFF)
            attribution: Global attribution string (optional, auto-generates from layers if None)
            **options: GeoTIFF-specific options:
                - compression (str): "lzw", "deflate", "jpeg", or "none" (default: "lzw")
                - export_mode (str): "composite" or "separate" (default: "composite")
                - multi_zoom (bool): Include pyramids for multi-zoom (default: True)
                - jpeg_quality (int): JPEG quality 1-100 (default: 80)
                - tiled (bool): Use tiled GeoTIFF format (default: True)
                - tile_size (int): Internal tile size 256 or 512 (default: 256)

        Returns:
            Path to the created GeoTIFF file (or first file if separate mode)
        """
        export_mode = options.get("export_mode", "composite")

        if export_mode == "composite":
            return self._generate_composite(
                output_path,
                extent,
                min_zoom,
                max_zoom,
                layer_compositions,
                progress_callback,
                attribution,
                **options,
            )
        else:
            return self._generate_separate(
                output_path,
                extent,
                min_zoom,
                max_zoom,
                layer_compositions,
                progress_callback,
                attribution,
                **options,
            )

    @staticmethod
    def _build_attribution(layer_compositions: list[LayerComposition], user_attribution: str | None) -> str:
        """Build attribution string from layer sources.

        If user_attribution is empty, automatically concatenates unique attributions
        from all enabled layers.

        Args:
            layer_compositions: List of layer compositions
            user_attribution: User-provided attribution (may be None or empty)

        Returns:
            Attribution string (user-provided or auto-generated from layers)
        """
        # If user provided attribution, use it as-is
        if user_attribution:
            return user_attribution

        # Otherwise, use shared attribution builder
        return build_attribution_from_layers(layer_compositions)

    def _generate_composite(
        self,
        output_path: Path,
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
        progress_callback,
        attribution: str | None = None,
        **options,
    ) -> Path:
        """Generate single composite GeoTIFF file.

        Args:
            output_path: Path for output file
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions
            progress_callback: Progress callback function
            attribution: Attribution text
            **options: GeoTIFF options

        Returns:
            Path to created GeoTIFF file
        """
        # Remove existing file if it exists
        if output_path.exists():
            output_path.unlink()

        generator = GeoTIFFGenerator(output_path, progress_callback)

        # Filter to enabled layers only
        enabled_layers = [comp for comp in layer_compositions if comp.enabled]

        # Build attribution (auto-generate from layers if not provided)
        final_attribution = self._build_attribution(enabled_layers, attribution)

        # Run async generation
        return asyncio.run(
            generator.generate_geotiff(
                extent,
                min_zoom,
                max_zoom,
                enabled_layers,
                compression=options.get("compression", "lzw"),
                multi_zoom=options.get("multi_zoom", True),
                jpeg_quality=options.get("jpeg_quality", 80),
                tiled=options.get("tiled", True),
                tile_size=options.get("tile_size", 256),
                attribution=final_attribution,
            )
        )

    def _generate_separate(
        self,
        output_path: Path,
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
        progress_callback,
        attribution: str | None = None,
        **options,
    ) -> Path:
        """Generate separate GeoTIFF files, one per layer.

        Args:
            output_path: Base path for output files
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions
            progress_callback: Progress callback function
            attribution: Attribution text
            **options: GeoTIFF options

        Returns:
            Path to first created GeoTIFF file
        """
        base_name = output_path.stem
        parent_dir = output_path.parent

        enabled_layers = [comp for comp in layer_compositions if comp.enabled]
        generated_files = []

        for idx, layer_comp in enumerate(enabled_layers):
            layer_id = layer_comp.layer_config.name

            # Build file path: {base_name}_{layer_id}.tif
            layer_output = parent_dir / f"{base_name}_{layer_id}.tif"

            # Build attribution for this specific layer
            layer_attribution = self._build_attribution([layer_comp], attribution)

            # Remove existing file if it exists
            if layer_output.exists():
                layer_output.unlink()

            # Wrap progress callback for multi-layer tracking
            def make_layer_progress(layer_idx, layer_name):
                def layer_progress(current, total, message):
                    if progress_callback:
                        progress_callback(
                            current,
                            total,
                            f"Layer {layer_idx + 1}/{len(enabled_layers)} ({layer_name}): {message}",
                        )

                return layer_progress

            generator = GeoTIFFGenerator(layer_output, make_layer_progress(idx, layer_id))

            # Run async generation
            asyncio.run(
                generator.generate_geotiff(
                    extent,
                    min_zoom,
                    max_zoom,
                    [layer_comp],
                    compression=options.get("compression", "lzw"),
                    multi_zoom=options.get("multi_zoom", True),
                    jpeg_quality=options.get("jpeg_quality", 80),
                    tiled=options.get("tiled", True),
                    tile_size=options.get("tile_size", 256),
                    attribution=layer_attribution,
                )
            )

            generated_files.append(layer_output)
            logger.info(f"Generated layer file: {layer_output}")

        return generated_files[0] if generated_files else output_path

    def estimate_tiles(
        self, extent: Extent, min_zoom: int, max_zoom: int, layer_compositions: list[LayerComposition], **options
    ) -> dict:
        """Estimate tile count and size for GeoTIFF output.

        Args:
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions
            **options: GeoTIFF-specific options:
                - compression (str): "lzw", "deflate", "jpeg", or "none"
                - export_mode (str): "composite" or "separate"
                - multi_zoom (bool): Include pyramids

        Returns:
            Dictionary with estimation data:
                - count (int): Number of tiles
                - count_label (str): Display string for tile count
                - size_bytes (int): Estimated size in bytes
                - size_label (str): Display string for size
        """
        enabled_layers = [comp for comp in layer_compositions if comp.enabled]
        if not enabled_layers:
            return {
                "count": 0,
                "count_label": "Tiles: -",
                "size_bytes": 0,
                "size_label": "Size: -",
            }

        # Calculate tiles at max zoom (base raster)
        max_zoom_tiles = TileCalculator.estimate_tile_count(
            extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, max_zoom
        )

        # Compression ratios (approximate for aerial imagery)
        compression = options.get("compression", "lzw")
        compression_ratios = {
            "none": 1.0,  # No compression
            "lzw": 0.4,  # 40% of original
            "deflate": 0.35,  # 35% of original (better than LZW)
            "jpeg": 0.15,  # 15% of original (lossy)
        }

        # Base tile size: 256x256 pixels * channels * bytes_per_channel
        # RGBA = 4 channels for PNG/LZW/DEFLATE, RGB = 3 channels for JPEG
        channels = 3 if compression == "jpeg" else 4
        base_tile_bytes = 256 * 256 * channels

        # Apply compression ratio
        compressed_tile_bytes = base_tile_bytes * compression_ratios[compression]

        # Calculate base raster size
        base_size = max_zoom_tiles * compressed_tile_bytes

        # Add pyramid overhead if multi_zoom enabled
        multi_zoom = options.get("multi_zoom", True)
        if multi_zoom and min_zoom < max_zoom:
            # Pyramids add approximately 1/3 additional size
            # (1/4 + 1/16 + 1/64 + ... ≈ 1/3 of base size)
            pyramid_overhead = 1.33
        else:
            pyramid_overhead = 1.0

        total_size = base_size * pyramid_overhead

        # Account for export mode
        export_mode = options.get("export_mode", "composite")
        if export_mode == "separate":
            file_count = len(enabled_layers)
            total_size *= file_count
            size_label_suffix = f" ({file_count} files)"
        else:
            size_label_suffix = ""

        # Format size label
        size_mb = total_size / (1024 * 1024)
        if size_mb < 1:
            size_label = f"Size: ~{total_size / 1024:.1f} KB{size_label_suffix}"
        else:
            size_label = f"Size: ~{size_mb:.1f} MB{size_label_suffix}"

        # Calculate total tiles across all zooms (for display)
        if multi_zoom and min_zoom < max_zoom:
            total_tiles = sum(
                TileCalculator.estimate_tile_count(extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom)
                for zoom in range(min_zoom, max_zoom + 1)
            )
            zoom_levels = max_zoom - min_zoom + 1
            count_label = f"Tiles: {total_tiles:,} ({zoom_levels} zoom levels)"
        else:
            total_tiles = max_zoom_tiles
            count_label = f"Tiles: {total_tiles:,}"

        return {
            "count": total_tiles,
            "count_label": count_label,
            "size_bytes": int(total_size),
            "size_label": size_label,
        }
