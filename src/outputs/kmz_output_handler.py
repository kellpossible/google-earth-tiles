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
        name: str | None = None,
        description: str | None = None,
        attribution: str | None = None,
        extent_config=None,
        **options,
    ) -> Path:
        """Generate a KMZ file.

        Args:
            output_path: Path where the KMZ should be saved
            extent: Geographic extent to generate
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions to include
            progress_callback: Optional callback for progress updates
            name: Document name/title (optional, uses default based on zoom if None)
            description: Document description (optional, shown in KML description)
            attribution: Global attribution string (optional, auto-generates from layers if None)
            extent_config: ExtentConfig object (needed for KML merging, optional)
            **options: KMZ-specific options:
                - web_compatible (bool): Enable web compatible mode (default: False)
                - include_timestamp (bool): Include timestamp in KML (default: True)
                - attribution_mode (str): "description" or "overlay" (default: "description")
                - merge_extent_kml (bool): Merge extent KML into output (default: False)

        Returns:
            Path to the created KMZ file
        """
        web_compatible = options.get("web_compatible", False)
        include_timestamp = options.get("include_timestamp", True)
        attribution_mode = options.get("attribution_mode", "description")
        merge_extent_kml = options.get("merge_extent_kml", False)

        generator = KMZGenerator(output_path, progress_callback)

        # Setup KML merging if requested
        if merge_extent_kml and extent_config is not None:
            if extent_config.mode == "file" and extent_config.file_path is not None:
                # Validate it's a KML file (not KMZ)
                if extent_config.file_path.suffix.lower() == ".kml":
                    generator._merge_extent_kml_features(extent_config.file_path)
                else:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"merge_extent_kml requires extent file to be KML format, "
                        f"got: {extent_config.file_path.suffix}"
                    )
            else:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning("merge_extent_kml requires extent.type='file', but extent is lat/lon mode")

        return generator.create_kmz(
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

    def estimate_tiles(
        self, extent: Extent, min_zoom: int, max_zoom: int, layer_compositions: list[LayerComposition], **options
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
                extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, max_zoom, chunk_size=CHUNK_SIZE
            )

            # Get total tiles for context
            total_tiles = TileCalculator.estimate_tile_count(
                extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, max_zoom
            )

            # Estimate size
            # CHUNK_SIZE^2 tiles per chunk, ~6KB per tile after compression
            avg_chunk_size_kb = (CHUNK_SIZE**2) * 6
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
            "attribution_mode": "description",  # "description" or "overlay"
            "merge_extent_kml": False,
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

        if "attribution_mode" in options and options["attribution_mode"] not in ["description", "overlay"]:
            raise ValueError("attribution_mode must be 'description' or 'overlay'")

        if "merge_extent_kml" in options and not isinstance(options["merge_extent_kml"], bool):
            raise ValueError("merge_extent_kml must be a boolean")
