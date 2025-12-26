"""KMZ output format handler."""

from pathlib import Path

from src.core.kmz_generator import KMZGenerator
from src.core.tile_calculator import CHUNK_SIZE, TileCalculator
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition


class KMZOutputHandler:
    """Handler for KMZ (Google Earth) output format.

    Implements the OutputHandler protocol for generating KMZ files.
    """

    @staticmethod
    def get_type_name() -> str:
        """Get the unique type identifier for this output format."""
        return "kmz"

    @staticmethod
    def get_display_name() -> str:
        """Get the human-readable display name for this output format."""
        return "KMZ (Google Earth)"

    @staticmethod
    def get_file_extension() -> str:
        """Get the default file extension for this output format."""
        return "kmz"

    @staticmethod
    def get_file_filter() -> str:
        """Get the file filter string for file dialogs."""
        return "KMZ Files (*.kmz)"

    def generate(
        self,
        output_path: Path,
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
        progress_callback=None,
        **options
    ) -> Path:
        """Generate a KMZ file.

        Args:
            output_path: Path where the KMZ should be saved
            extent: Geographic extent to generate
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions to include
            progress_callback: Optional callback for progress updates
            **options: KMZ-specific options:
                - web_compatible (bool): Enable web compatible mode (default: False)
                - include_timestamp (bool): Include timestamp in KML (default: True)

        Returns:
            Path to the created KMZ file
        """
        web_compatible = options.get("web_compatible", False)
        include_timestamp = options.get("include_timestamp", True)

        generator = KMZGenerator(output_path, progress_callback)
        return generator.create_kmz(
            extent, min_zoom, max_zoom, layer_compositions, web_compatible, include_timestamp
        )

    def estimate_tiles(
        self,
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
        **options
    ) -> dict:
        """Estimate tile count and size for KMZ output.

        Args:
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions
            **options: KMZ-specific options:
                - web_compatible (bool): Enable web compatible mode

        Returns:
            Dictionary with estimation data
        """
        web_compatible = options.get("web_compatible", False)
        enabled_layers = [comp for comp in layer_compositions if comp.enabled]

        if not enabled_layers:
            return {
                "count": 0,
                "count_label": "Tiles: -",
                "size_bytes": 0,
                "size_label": "Size: -",
            }

        if web_compatible:
            # Web compatible mode: calculate chunks at the max zoom
            # (web compatible uses a single zoom level)
            chunk_count = TileCalculator.calculate_chunks_at_zoom(
                extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat,
                max_zoom,
                chunk_size=CHUNK_SIZE
            )

            # Get total tiles for context
            total_tiles = TileCalculator.estimate_tile_count(
                extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, max_zoom
            )

            # Estimate size
            # CHUNK_SIZE^2 tiles per chunk, ~6KB per tile after compression
            avg_chunk_size_kb = (CHUNK_SIZE ** 2) * 6
            size_bytes = chunk_count * avg_chunk_size_kb * 1024
            size_mb = size_bytes / (1024 * 1024)

            return {
                "count": chunk_count,
                "count_label": f"Chunks: {chunk_count:,} ({total_tiles:,} total)",
                "size_bytes": size_bytes,
                "size_label": f"Size: ~{size_mb:.1f} MB (web compatible)",
            }
        else:
            # Regular mode: calculate tiles
            total_tiles = 0
            for zoom in range(min_zoom, max_zoom + 1):
                tile_count = TileCalculator.estimate_tile_count(
                    extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom
                )
                total_tiles += tile_count

            # Format count label
            zoom_levels = max_zoom - min_zoom + 1
            if zoom_levels == 1:
                count_label = f"Tiles: {total_tiles:,}"
            else:
                count_label = f"Tiles: {total_tiles:,} ({zoom_levels} zoom levels)"

            # Estimate size (assume ~50KB per tile on average)
            size_bytes = total_tiles * 50 * 1024
            size_mb = size_bytes / (1024 * 1024)

            size_label = f"Size: ~{size_bytes / 1024:.1f} KB" if size_mb < 1 else f"Size: ~{size_mb:.1f} MB"

            return {
                "count": total_tiles,
                "count_label": count_label,
                "size_bytes": size_bytes,
                "size_label": size_label,
            }

    @staticmethod
    def get_default_options() -> dict:
        """Get default KMZ-specific options."""
        return {
            "web_compatible": False,
            "include_timestamp": True,
        }

    @staticmethod
    def validate_options(options: dict) -> None:
        """Validate KMZ-specific options.

        Args:
            options: Dictionary of options to validate

        Raises:
            ValueError: If options are invalid
        """
        if "web_compatible" in options and not isinstance(options["web_compatible"], bool):
            raise ValueError("web_compatible must be a boolean")

        if "include_timestamp" in options and not isinstance(options["include_timestamp"], bool):
            raise ValueError("include_timestamp must be a boolean")
