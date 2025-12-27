"""Protocol for output format handlers."""

from pathlib import Path
from typing import Protocol

from src.models.extent import Extent
from src.models.layer_composition import LayerComposition


class OutputHandler(Protocol):
    """Protocol defining the interface for output format handlers.

    Each output format (KMZ, GeoTIFF, MBTiles, etc.) should implement this protocol
    to integrate with the generation system.
    """

    @staticmethod
    def get_type_name() -> str:
        """Get the unique type identifier for this output format.

        Returns:
            Type name (e.g., "kmz", "geotiff", "mbtiles")
        """
        ...

    @staticmethod
    def get_display_name() -> str:
        """Get the human-readable display name for this output format.

        Returns:
            Display name (e.g., "KMZ (Google Earth)", "GeoTIFF", "MBTiles")
        """
        ...

    @staticmethod
    def get_file_extension() -> str:
        """Get the default file extension for this output format.

        Returns:
            File extension without dot (e.g., "kmz", "tif", "mbtiles")
        """
        ...

    @staticmethod
    def get_file_filter() -> str:
        """Get the file filter string for file dialogs.

        Returns:
            File filter string (e.g., "KMZ Files (*.kmz)", "GeoTIFF Files (*.tif *.tiff)")
        """
        ...

    def generate(
        self,
        output_path: Path,
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
        progress_callback=None,
        **options,
    ) -> Path:
        """Generate the output file.

        Args:
            output_path: Path where the output should be saved
            extent: Geographic extent to generate
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions to include
            progress_callback: Optional callback for progress updates (current, total, message)
            **options: Format-specific options

        Returns:
            Path to the created output file

        Raises:
            Exception: If generation fails
        """
        ...

    def estimate_tiles(
        self, extent: Extent, min_zoom: int, max_zoom: int, layer_compositions: list[LayerComposition], **options
    ) -> dict:
        """Estimate tile count and size for this output.

        Args:
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions
            **options: Format-specific options

        Returns:
            Dictionary with estimation data:
                - "count": Number of tiles/chunks
                - "count_label": Display string for count (e.g., "Tiles: 1,234" or "Chunks: 56")
                - "size_bytes": Estimated size in bytes
                - "size_label": Display string for size (e.g., "Size: ~5.6 MB")
        """
        ...

    @staticmethod
    def get_default_options() -> dict:
        """Get default format-specific options.

        Returns:
            Dictionary of default options for this format
        """
        ...

    @staticmethod
    def validate_options(options: dict) -> None:
        """Validate format-specific options.

        Args:
            options: Dictionary of options to validate

        Raises:
            ValueError: If options are invalid
        """
        ...
