"""Output format-specific option widgets."""

from src.gui.output_options.geotiff_options_widget import GeoTIFFOptionsWidget
from src.gui.output_options.kmz_options_widget import KMZOptionsWidget
from src.gui.output_options.mbtiles_options_widget import MBTilesOptionsWidget

# Registry mapping output type to widget class
OUTPUT_OPTION_WIDGETS = {
    "kmz": KMZOptionsWidget,
    "mbtiles": MBTilesOptionsWidget,
    "geotiff": GeoTIFFOptionsWidget,
}


def get_options_widget(output_type: str):
    """Get the options widget class for a given output type.

    Args:
        output_type: Output type identifier (e.g., "kmz", "mbtiles")

    Returns:
        Options widget class

    Raises:
        ValueError: If output type is not recognized
    """
    if output_type not in OUTPUT_OPTION_WIDGETS:
        raise ValueError(f"Unknown output type: {output_type}")
    return OUTPUT_OPTION_WIDGETS[output_type]


__all__ = [
    "KMZOptionsWidget",
    "MBTilesOptionsWidget",
    "GeoTIFFOptionsWidget",
    "OUTPUT_OPTION_WIDGETS",
    "get_options_widget",
]
