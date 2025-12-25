"""Map widget with extent selection."""

import tempfile
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import pyqtSignal, pyqtSlot, QUrl, QObject
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineSettings,
    QWebEngineProfile,
    QWebEngineUrlScheme
)
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.core.config import DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM, LAYERS, LayerConfig
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition
from src.gui.tile_compositor import PreviewTileSchemeHandler

# Get absolute paths
VENDOR_DIR = Path(__file__).parent.parent.parent / "resources" / "vendor"
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "resources" / "map_template.html"


class MapBridge(QObject):
    """Bridge for JavaScript to Python communication."""

    extent_changed = pyqtSignal(float, float, float, float)  # south, north, west, east
    extent_cleared = pyqtSignal()  # Emitted when extent is deleted
    zoom_changed = pyqtSignal(int)  # Emitted when preview zoom changes

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

    @pyqtSlot(int)
    def on_zoom_changed(self, zoom: int):
        """
        Receive zoom change from JavaScript.

        Args:
            zoom: Current zoom level
        """
        self.zoom_changed.emit(zoom)


class MapWidget(QWidget):
    """Widget displaying an interactive map for extent selection."""

    extent_changed = pyqtSignal(object)  # Extent object
    extent_cleared = pyqtSignal()  # Emitted when extent is cleared
    preview_zoom_changed = pyqtSignal(int)  # Emitted when preview zoom changes

    # Class variable for URL scheme handler
    _scheme_handler = None

    def __init__(self):
        """Initialize map widget."""
        super().__init__()
        self.current_zoom = DEFAULT_MAP_ZOOM
        self.bridge = MapBridge()
        self.bridge.extent_changed.connect(self._on_extent_received)
        self.bridge.extent_cleared.connect(self._on_extent_cleared)
        self.bridge.zoom_changed.connect(self._on_zoom_changed)

        # Initialize scheme handler if not already done
        if MapWidget._scheme_handler is None:
            MapWidget._scheme_handler = PreviewTileSchemeHandler()

        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Create web view
        self.web_view = QWebEngineView()

        # Install custom URL scheme handler
        profile = self.web_view.page().profile()
        profile.installUrlSchemeHandler(b'preview', MapWidget._scheme_handler)

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

    def create_map(self, layer_compositions: Optional[List[LayerComposition]] = None, zoom: Optional[int] = None):
        """
        Create map and load it in the web view.

        Args:
            layer_compositions: List of LayerComposition objects
            zoom: Zoom level (default: current_zoom)
        """
        if zoom:
            self.current_zoom = zoom

        # Set layer compositions in scheme handler
        if layer_compositions:
            MapWidget._scheme_handler.set_layer_compositions(layer_compositions)
        else:
            # No layers: show blank/transparent tiles
            MapWidget._scheme_handler.set_layer_compositions([])

        # Load template
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            template = f.read()

        # Replace placeholders
        html = template.replace('VENDOR_PATH', str(VENDOR_DIR))
        html = html.replace('MAP_LAT', str(DEFAULT_MAP_CENTER[0]))
        html = html.replace('MAP_LON', str(DEFAULT_MAP_CENTER[1]))
        html = html.replace('MAP_ZOOM', str(self.current_zoom))

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html)
            temp_path = f.name

        # Load the map
        self.web_view.setUrl(QUrl.fromLocalFile(temp_path))

    def update_map_zoom_limits(self, layer_compositions: List[LayerComposition]):
        """
        Update map zoom limits to union of enabled layers.

        Args:
            layer_compositions: List of LayerComposition objects
        """
        import logging
        logger = logging.getLogger(__name__)

        if not layer_compositions:
            min_zoom, max_zoom = 2, 18
        else:
            # Union (not intersection) - allow best detail from any layer
            min_zoom = min(comp.layer_config.min_zoom for comp in layer_compositions)
            max_zoom = max(comp.layer_config.max_zoom for comp in layer_compositions)

        js_code = f"if (typeof updateZoomLimits === 'function') {{ updateZoomLimits({min_zoom}, {max_zoom}); }}"
        self.web_view.page().runJavaScript(js_code)
        logger.info(f"Updated map zoom limits: {min_zoom}-{max_zoom}")

    def update_layer_composition(self, layer_compositions: List[LayerComposition], update_zoom_limits: bool = True):
        """
        Update the map layers with new composition settings.

        Args:
            layer_compositions: List of LayerComposition objects
            update_zoom_limits: Whether to update zoom limits (only needed when layers change)
        """
        # Update the scheme handler with new compositions
        MapWidget._scheme_handler.set_layer_compositions(layer_compositions)

        if update_zoom_limits:
            # Update zoom limits and refresh tiles (updateZoomLimits calls refreshTiles internally)
            self.update_map_zoom_limits(layer_compositions)
        else:
            # Just refresh tiles without changing zoom limits
            self.web_view.page().runJavaScript("if (typeof refreshTiles === 'function') { refreshTiles(); }")

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

    def _on_zoom_changed(self, zoom: int):
        """
        Handle zoom change from JavaScript.

        Args:
            zoom: New zoom level
        """
        self.current_zoom = zoom
        self.preview_zoom_changed.emit(zoom)

    def set_preview_zoom(self, zoom: int):
        """
        Set the preview map zoom level.

        Args:
            zoom: Zoom level to set
        """
        self.web_view.page().runJavaScript(f"if (typeof setPreviewZoom === 'function') {{ setPreviewZoom({zoom}); }}")

    def set_extent(self, extent: Extent):
        """
        Set the extent on the map (draw rectangle and center map).

        Args:
            extent: Extent to display
        """
        js_code = f"""
        if (typeof setExtent === 'function') {{
            setExtent({extent.min_lat}, {extent.max_lat}, {extent.min_lon}, {extent.max_lon});
        }}
        """
        self.web_view.page().runJavaScript(js_code)

    def get_selected_extent(self) -> Optional[Extent]:
        """
        Get the currently selected extent.

        Returns:
            Extent object or None if no extent selected
        """
        # Note: This would require storing the last received extent
        # For now, extents are communicated via signals
        return None
