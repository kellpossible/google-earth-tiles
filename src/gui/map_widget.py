"""Map widget with extent selection."""

import tempfile
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.core.config import DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM, LAYERS
from src.models.extent import Extent

# Get absolute paths
VENDOR_DIR = Path(__file__).parent.parent.parent / "resources" / "vendor"
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "resources" / "map_template.html"


class MapBridge(QObject):
    """Bridge for JavaScript to Python communication."""

    extent_changed = pyqtSignal(float, float, float, float)  # south, north, west, east
    extent_cleared = pyqtSignal()  # Emitted when extent is deleted

    @pyqtSlot(float, float, float, float)
    def set_extent(self, south: float, north: float, west: float, east: float):
        """
        Receive extent from JavaScript.

        Args:
            south: South latitude
            north: North latitude
            west: West longitude
            east: East longitude
        """
        self.extent_changed.emit(south, north, west, east)

    @pyqtSlot()
    def clear_extent(self):
        """Receive notification that extent was cleared."""
        self.extent_cleared.emit()


class MapWidget(QWidget):
    """Widget displaying an interactive map for extent selection."""

    extent_changed = pyqtSignal(object)  # Extent object
    extent_cleared = pyqtSignal()  # Emitted when extent is cleared

    def __init__(self):
        """Initialize map widget."""
        super().__init__()
        self.current_layer = 'std'
        self.current_zoom = DEFAULT_MAP_ZOOM
        self.bridge = MapBridge()
        self.bridge.extent_changed.connect(self._on_extent_received)
        self.bridge.extent_cleared.connect(self._on_extent_cleared)

        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Create web view
        self.web_view = QWebEngineView()

        # Configure web settings
        settings = self.web_view.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        # Allow local HTML to fetch remote tiles
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        # Set up web channel for JS communication
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        layout.addWidget(self.web_view)
        self.setLayout(layout)

        # Create and load initial map
        self.create_map()

    def create_map(self, layer_name: Optional[str] = None, zoom: Optional[int] = None):
        """
        Create map and load it in the web view.

        Args:
            layer_name: Layer to display (default: current_layer)
            zoom: Zoom level (default: current_zoom)
        """
        if layer_name:
            self.current_layer = layer_name
        if zoom:
            self.current_zoom = zoom

        layer_config = LAYERS.get(self.current_layer, LAYERS['std'])

        # Load template
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            template = f.read()

        # Build layer options HTML
        layer_options = []
        for name, config in LAYERS.items():
            selected = 'selected' if name == self.current_layer else ''
            layer_options.append(
                f'<option value="{name}" {selected}>{config.display_name}</option>'
            )
        layer_options_html = '\n            '.join(layer_options)

        # Build layer data JSON
        import json
        layer_data = {}
        for name, config in LAYERS.items():
            layer_data[name] = {
                'url': config.url_template,
                'min_zoom': config.min_zoom,
                'max_zoom': config.max_zoom,
                'display_name': config.display_name
            }
        layer_data_json = json.dumps(layer_data)

        # Replace placeholders
        html = template.replace('VENDOR_PATH', str(VENDOR_DIR))
        html = html.replace('MAP_LAT', str(DEFAULT_MAP_CENTER[0]))
        html = html.replace('MAP_LON', str(DEFAULT_MAP_CENTER[1]))
        html = html.replace('MAP_ZOOM', str(self.current_zoom))
        html = html.replace('TILE_URL', layer_config.url_template)
        html = html.replace('LAYER_OPTIONS', layer_options_html)
        html = html.replace('LAYER_DATA', layer_data_json)

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html)
            temp_path = f.name

        # Load the map
        self.web_view.setUrl(QUrl.fromLocalFile(temp_path))

    def update_tile_preview(self, layer_name: str, zoom: int):
        """
        Update the map with a different layer or zoom.

        Args:
            layer_name: Layer to display
            zoom: Zoom level
        """
        self.create_map(layer_name, zoom)

    def _on_extent_received(self, south: float, north: float, west: float, east: float):
        """
        Handle extent received from JavaScript.

        Args:
            south: South latitude
            north: North latitude
            west: West longitude
            east: East longitude
        """
        extent = Extent(
            min_lon=west,
            min_lat=south,
            max_lon=east,
            max_lat=north
        )

        if extent.is_valid():
            self.extent_changed.emit(extent)

    def _on_extent_cleared(self):
        """Handle extent cleared from JavaScript."""
        self.extent_cleared.emit()

    def get_selected_extent(self) -> Optional[Extent]:
        """
        Get the currently selected extent.

        Returns:
            Extent object or None if no extent selected
        """
        # Note: This would require storing the last received extent
        # For now, extents are communicated via signals
        return None
