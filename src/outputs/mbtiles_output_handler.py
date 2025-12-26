"""MBTiles output format handler."""

import asyncio
import logging
from pathlib import Path

from src.core.mbtiles_generator import MBTilesGenerator
from src.core.tile_calculator import TileCalculator
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition
from src.utils.attribution import build_attribution_from_layers

logger = logging.getLogger(__name__)


class MBTilesOutputHandler:
    """Handler for MBTiles output format.

    Implements the OutputHandler protocol for generating MBTiles databases.
    Supports both PNG and JPEG image formats, and both composite and separate
    layer export modes.
    """

    @staticmethod
    def get_type_name() -> str:
        """Get the unique type identifier for this output format."""
        return "mbtiles"

    @staticmethod
    def get_display_name() -> str:
        """Get the human-readable display name for this output format."""
        return "MBTiles"

    @staticmethod
    def get_file_extension() -> str:
        """Get the default file extension for this output format."""
        return "mbtiles"

    @staticmethod
    def get_file_filter() -> str:
        """Get the file filter string for file dialogs."""
        return "MBTiles Files (*.mbtiles)"

    @staticmethod
    def get_default_options() -> dict:
        """Get default MBTiles-specific options."""
        return {
            "image_format": "png",  # "png" or "jpg"
            "export_mode": "composite",  # "composite" or "separate"
            "jpeg_quality": 80,  # 1-100 for JPEG compression
            # Metadata fields
            "metadata_type": "baselayer",  # "overlay" or "baselayer"
        }

    @staticmethod
    def validate_options(options: dict) -> None:
        """Validate MBTiles-specific options.

        Args:
            options: Dictionary of options to validate

        Raises:
            ValueError: If options are invalid
        """
        if "image_format" in options and options["image_format"] not in ["png", "jpg"]:
            raise ValueError("image_format must be 'png' or 'jpg'")

        if "export_mode" in options and options["export_mode"] not in ["composite", "separate"]:
            raise ValueError("export_mode must be 'composite' or 'separate'")

        if "jpeg_quality" in options:
            quality = options["jpeg_quality"]
            if not isinstance(quality, int) or not 1 <= quality <= 100:
                raise ValueError("jpeg_quality must be an integer between 1 and 100")

        if "metadata_type" in options and options["metadata_type"] not in ["overlay", "baselayer"]:
            raise ValueError("metadata_type must be 'overlay' or 'baselayer'")

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
        """Generate MBTiles file(s).

        Args:
            output_path: Path where the MBTiles should be saved
            extent: Geographic extent to generate
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions to include
            progress_callback: Optional callback for progress updates
            name: Global name/title for the tileset (default: "Tile Export")
            description: Global description for the tileset (optional)
            attribution: Global attribution string (optional, auto-generates from layers if None)
            **options: MBTiles-specific options:
                - image_format (str): "png" or "jpg" (default: "png")
                - export_mode (str): "composite" or "separate" (default: "composite")
                - jpeg_quality (int): JPEG quality 1-100 (default: 80)
                - metadata_type (str): "overlay" or "baselayer"

        Returns:
            Path to the created MBTiles file (or first file if separate mode)
        """
        export_mode = options.get("export_mode", "composite")

        if export_mode == "composite":
            return self._generate_composite(
                output_path, extent, min_zoom, max_zoom, layer_compositions, progress_callback, name, description, attribution, **options
            )
        else:
            return self._generate_separate(
                output_path, extent, min_zoom, max_zoom, layer_compositions, progress_callback, name, description, attribution, **options
            )

    @staticmethod
    def _build_attribution(layer_compositions: list[LayerComposition], user_attribution: str) -> str:
        """Build attribution string from layer sources.

        If user_attribution is empty, automatically concatenates unique attributions
        from all enabled layers.

        Args:
            layer_compositions: List of layer compositions
            user_attribution: User-provided attribution (may be empty)

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
        name: str | None = None,
        description: str | None = None,
        attribution: str | None = None,
        **options,
    ) -> Path:
        """Generate single composite MBTiles file.

        Args:
            output_path: Path for output file
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions
            progress_callback: Progress callback function
            **options: MBTiles options

        Returns:
            Path to created MBTiles file
        """
        # Remove existing file if it exists
        if output_path.exists():
            output_path.unlink()

        generator = MBTilesGenerator(output_path, progress_callback)

        # Filter to enabled layers only
        enabled_layers = [comp for comp in layer_compositions if comp.enabled]

        # Build attribution (auto-generate from layers if not provided)
        final_attribution = self._build_attribution(enabled_layers, attribution or "")

        metadata_config = {
            "name": name or "Tile Export",
            "description": description or "",
            "attribution": final_attribution,
            "type": options.get("metadata_type", "overlay"),
        }

        # Run async generation (Python 3.14 compatible)
        return asyncio.run(
            generator.generate_mbtiles(
                extent,
                min_zoom,
                max_zoom,
                enabled_layers,
                options.get("image_format", "png"),
                metadata_config,
                options.get("jpeg_quality", 80),
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
        name: str | None = None,
        description: str | None = None,
        attribution: str | None = None,
        **options,
    ) -> Path:
        """Generate separate MBTiles files, one per layer.

        Args:
            output_path: Base path for output files
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions
            progress_callback: Progress callback function
            **options: MBTiles options

        Returns:
            Path to first created MBTiles file
        """
        base_name = output_path.stem
        parent_dir = output_path.parent

        enabled_layers = [comp for comp in layer_compositions if comp.enabled]
        generated_files = []

        for idx, layer_comp in enumerate(enabled_layers):
            layer_id = layer_comp.layer_config.name

            # Build file path: {base_name}_{layer_id}.mbtiles
            layer_output = parent_dir / f"{base_name}_{layer_id}.mbtiles"

            # Build attribution for this specific layer
            layer_attribution = self._build_attribution([layer_comp], attribution or "")

            # Update metadata name to include layer
            metadata_name = name or "Tile Export"
            layer_metadata = {
                "name": f"{metadata_name} - {layer_id}",
                "description": description or "",
                "attribution": layer_attribution,
                "type": options.get("metadata_type", "overlay"),
            }

            # Remove existing file if it exists
            if layer_output.exists():
                layer_output.unlink()

            # Wrap progress callback for multi-layer tracking (bind loop variables)
            def make_layer_progress(layer_idx, layer_name):
                def layer_progress(current, total, message):
                    if progress_callback:
                        progress_callback(
                            current, total, f"Layer {layer_idx+1}/{len(enabled_layers)} ({layer_name}): {message}"
                        )
                return layer_progress

            generator = MBTilesGenerator(layer_output, make_layer_progress(idx, layer_id))

            # Run async generation (Python 3.14 compatible)
            asyncio.run(
                generator.generate_mbtiles(
                    extent,
                    min_zoom,
                    max_zoom,
                    [layer_comp],
                    options.get("image_format", "png"),
                    layer_metadata,
                    options.get("jpeg_quality", 80),
                )
            )

            generated_files.append(layer_output)
            logger.info(f"Generated layer file: {layer_output}")

        return generated_files[0] if generated_files else output_path

    def estimate_tiles(
        self, extent: Extent, min_zoom: int, max_zoom: int, layer_compositions: list[LayerComposition], **options
    ) -> dict:
        """Estimate tile count and size for MBTiles output.

        Args:
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions
            **options: MBTiles-specific options:
                - image_format (str): "png" or "jpg"
                - export_mode (str): "composite" or "separate"

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

        # Calculate total tiles
        total_tiles = sum(
            TileCalculator.estimate_tile_count(extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom)
            for zoom in range(min_zoom, max_zoom + 1)
        )

        # Estimate size based on format
        image_format = options.get("image_format", "png")
        # PNG tiles: ~50KB average (varies by content), JPEG tiles: ~30KB average (compressed)
        avg_tile_kb = 50 if image_format == "png" else 30

        # Account for export mode
        export_mode = options.get("export_mode", "composite")
        if export_mode == "separate":
            # Multiple files, one per layer
            file_count = len(enabled_layers)
            total_tiles_all_files = total_tiles * file_count
            size_bytes = total_tiles_all_files * avg_tile_kb * 1024

            # Add SQLite overhead (10% per file)
            size_bytes = int(size_bytes * 1.1)

            size_mb = size_bytes / (1024 * 1024)

            count_label = f"Tiles: {total_tiles:,} × {file_count} files = {total_tiles_all_files:,}"
            size_label = f"Size: ~{size_mb:.1f} MB ({file_count} files)"
        else:
            # Single composite file
            size_bytes = total_tiles * avg_tile_kb * 1024

            # Add SQLite overhead (10%)
            size_bytes = int(size_bytes * 1.1)

            size_mb = size_bytes / (1024 * 1024)

            zoom_levels = max_zoom - min_zoom + 1
            if zoom_levels == 1:
                count_label = f"Tiles: {total_tiles:,}"
            else:
                count_label = f"Tiles: {total_tiles:,} ({zoom_levels} zoom levels)"

            size_label = f"Size: ~{size_bytes / 1024:.1f} KB" if size_mb < 1 else f"Size: ~{size_mb:.1f} MB"

        return {
            "count": total_tiles,
            "count_label": count_label,
            "size_bytes": size_bytes,
            "size_label": size_label,
        }
