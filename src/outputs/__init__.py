"""Output format handlers registry."""

from src.models.output_handler import OutputHandler
from src.outputs.geotiff_output_handler import GeoTIFFOutputHandler
from src.outputs.kmz_output_handler import KMZOutputHandler
from src.outputs.mbtiles_output_handler import MBTilesOutputHandler

# Registry of available output handlers
OUTPUT_HANDLERS: dict[str, type[OutputHandler]] = {
    "kmz": KMZOutputHandler,
    "mbtiles": MBTilesOutputHandler,
    "geotiff": GeoTIFFOutputHandler,
    # Future formats can be added here:
    # "png": PNGOutputHandler,
}


def get_output_handler(output_type: str) -> OutputHandler:
    """Get an output handler instance for the given type.

    Args:
        output_type: Output type name (e.g., "kmz", "geotiff")

    Returns:
        Instance of the output handler

    Raises:
        ValueError: If output type is not supported
    """
    if output_type not in OUTPUT_HANDLERS:
        raise ValueError(
            f"Unsupported output type: {output_type}. "
            f"Supported types: {', '.join(OUTPUT_HANDLERS.keys())}"
        )

    handler_class = OUTPUT_HANDLERS[output_type]
    return handler_class()


def get_available_output_types() -> list[tuple[str, str]]:
    """Get list of available output types.

    Returns:
        List of (type_name, display_name) tuples
    """
    return [
        (handler_class.get_type_name(), handler_class.get_display_name())
        for handler_class in OUTPUT_HANDLERS.values()
    ]


__all__ = [
    "OUTPUT_HANDLERS",
    "get_output_handler",
    "get_available_output_types",
    "KMZOutputHandler",
    "MBTilesOutputHandler",
    "GeoTIFFOutputHandler",
]
