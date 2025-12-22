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
    japanese_name: str
    full_description: str
    info_url: str
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
        description='Standard map with roads and labels',
        japanese_name='標準地図',
        full_description='Electronic topographic map with standard cartographic styling. '
                         'Shows detailed road networks, building outlines, geographic labels, '
                         'elevation contours, and administrative boundaries. Suitable for general '
                         'reference mapping across Japan and surrounding regions.',
        info_url='https://maps.gsi.go.jp/development/ichiran.html'
    ),
    'pale': LayerConfig(
        name='pale',
        display_name='Pale Map',
        extension='png',
        min_zoom=2,
        max_zoom=18,
        description='Pale colored base map',
        japanese_name='淡色地図',
        full_description='Lighter-toned version of the standard map designed specifically for use as '
                         'a background layer beneath thematic overlays. The reduced color intensity '
                         'allows custom data visualizations to stand out while maintaining essential '
                         'geographic context.',
        info_url='https://maps.gsi.go.jp/development/ichiran.html'
    ),
    'english': LayerConfig(
        name='english',
        display_name='English Map',
        extension='png',
        min_zoom=5,
        max_zoom=8,
        description='Map with English labels',
        japanese_name='English',
        full_description='International map of Japan with English labeling for place names, features, '
                         'and geographic regions. Designed for international reference, tourism '
                         'applications, and global users requiring romanized toponymy.',
        info_url='https://maps.gsi.go.jp/development/ichiran.html'
    ),
    'ort': LayerConfig(
        name='ort',
        display_name='Orthographic Aerial Photos',
        extension='jpg',
        min_zoom=2,
        max_zoom=18,
        description='Corrected aerial photography',
        japanese_name='電子国土基本図（オルソ画像）',
        full_description='Geometrically corrected aerial photographs captured from 2007 onwards. '
                         'These orthophotos provide high-precision geospatial reference imagery '
                         'suitable for accurate measurement, analysis, and overlay with other datasets. '
                         'Updated regularly to reflect current ground conditions.',
        info_url='https://maps.gsi.go.jp/development/ichiran.html'
    ),
    'relief': LayerConfig(
        name='relief',
        display_name='Color-Coded Elevation Map',
        extension='png',
        min_zoom=5,
        max_zoom=15,
        description='Elevation shown through color gradation',
        japanese_name='色別標高図',
        full_description='Topographic visualization displaying elevation through color gradation and '
                         'shading effects. Higher elevations appear in warmer colors while lower areas '
                         'use cooler tones, making terrain features and landforms immediately apparent. '
                         'Useful for understanding regional topography and terrain characteristics.',
        info_url='https://maps.gsi.go.jp/development/ichiran.html'
    ),
    'seamlessphoto': LayerConfig(
        name='seamlessphoto',
        display_name='Seamless Aerial Photos',
        extension='jpg',
        min_zoom=2,
        max_zoom=18,
        description='Composite recent aerial imagery',
        japanese_name='シームレス空中写真',
        full_description='Composite aerial imagery created by seamlessly combining the most recent '
                         'photographs from various sources maintained by the Geospatial Information '
                         'Authority of Japan. Provides nationwide coverage showing current ground '
                         'conditions, land use patterns, and development status.',
        info_url='https://maps.gsi.go.jp/development/ichiran.html'
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
