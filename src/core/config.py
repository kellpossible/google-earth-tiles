"""Configuration for WMTS layers and application settings."""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class LayerConfig:
    """Configuration for a tile layer.

    Supports both WMTS sources (via name parameter for GSI) and custom tile URLs.
    """

    name: str
    display_name: str
    extension: str
    min_zoom: int
    max_zoom: int
    description: str
    custom_url_template: Optional[str] = None

    @property
    def url_template(self) -> str:
        """Get the URL template for this layer.

        Uses custom_url_template if provided, otherwise generates GSI WMTS URL.
        """
        if self.custom_url_template:
            return self.custom_url_template
        return f"https://maps.gsi.go.jp/xyz/{self.name}/{{z}}/{{x}}/{{y}}.{self.extension}"


# Available WMTS layers from Japan GSI
LAYERS: Dict[str, LayerConfig] = {
    'std': LayerConfig(
        name='std',
        display_name='Standard Map',
        extension='png',
        min_zoom=2,
        max_zoom=18,
        description='Standard map with roads and labels'
    ),
    'pale': LayerConfig(
        name='pale',
        display_name='Pale Map',
        extension='png',
        min_zoom=2,
        max_zoom=18,
        description='Pale colored base map'
    ),
    'english': LayerConfig(
        name='english',
        display_name='English Map',
        extension='png',
        min_zoom=5,
        max_zoom=8,
        description='Map with English labels'
    ),
    'ort': LayerConfig(
        name='ort',
        display_name='Aerial Photos',
        extension='jpg',
        min_zoom=2,
        max_zoom=18,
        description='Aerial/satellite imagery'
    ),
    'relief': LayerConfig(
        name='relief',
        display_name='Relief Map',
        extension='png',
        min_zoom=5,
        max_zoom=15,
        description='Relief map with hillshade'
    ),
    'seamlessphoto': LayerConfig(
        name='seamlessphoto',
        display_name='Seamless Aerial Photos',
        extension='jpg',
        min_zoom=2,
        max_zoom=18,
        description='Seamless aerial/satellite imagery'
    ),
}

# Download settings
MAX_CONCURRENT_DOWNLOADS = 8
DOWNLOAD_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Tile settings
TILE_SIZE = 256  # pixels
DEFAULT_ZOOM = 12

# UI settings
DEFAULT_MAP_CENTER = [36.5, 138.0]  # Central Japan
DEFAULT_MAP_ZOOM = 6  # Show most of Japan

# Japan region bounds for validation (approximate WMTS coverage area)
JAPAN_REGION_BOUNDS = {
    'min_lon': 122.0,
    'max_lon': 154.0,
    'min_lat': 20.0,
    'max_lat': 46.0,
}
