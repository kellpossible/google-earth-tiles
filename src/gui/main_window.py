"""Main application window."""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, List

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.core.config import LayerConfig
from src.core.kmz_generator import KMZGenerator
from src.core.tile_calculator import TileCalculator
from src.core.wmts_client import WMTSClient
from src.gui.map_widget import MapWidget
from src.gui.settings_panel import SettingsPanel
from src.models.extent import Extent

logger = logging.getLogger(__name__)


class DownloadWorker(QThread):
    """Worker thread for downloading tiles."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(dict)  # layer_tiles_dict
    error = pyqtSignal(str)

    def __init__(
        self,
        layers: List[LayerConfig],
        extent: Extent,
        zoom: int,
    ):
        """
        Initialize worker.

        Args:
            layers: List of layers to download
            extent: Geographic extent
            zoom: Zoom level
        """
        super().__init__()
        self.layers = layers
        self.extent = extent
        self.zoom = zoom
        self.layer_tiles_dict = {}

    def run(self):
        """Run the download process."""
        try:
            # Create temporary directory for tiles
            temp_dir = Path(tempfile.mkdtemp())

            # Calculate total tiles
            tiles_per_layer = TileCalculator.get_tiles_in_extent(
                self.extent.min_lon,
                self.extent.min_lat,
                self.extent.max_lon,
                self.extent.max_lat,
                self.zoom
            )

            total_tiles = len(tiles_per_layer) * len(self.layers)
            completed_tiles = 0

            # Download tiles for each layer
            for layer in self.layers:
                self.progress.emit(
                    completed_tiles,
                    total_tiles,
                    f"Downloading {layer.display_name}..."
                )

                # Create layer directory
                layer_dir = temp_dir / layer.name
                layer_dir.mkdir(exist_ok=True)

                # Convert tiles to (x, y, z) format
                tiles_xyz = [(x, y, self.zoom) for x, y in tiles_per_layer]

                # Download tiles
                downloaded = asyncio.run(self._download_layer_tiles(
                    layer,
                    tiles_xyz,
                    layer_dir,
                    completed_tiles,
                    total_tiles
                ))

                self.layer_tiles_dict[layer] = downloaded
                completed_tiles += len(tiles_per_layer)

            self.progress.emit(total_tiles, total_tiles, "Download complete!")
            self.finished.emit(self.layer_tiles_dict)

        except Exception as e:
            logger.exception("Error during download")
            self.error.emit(str(e))

    async def _download_layer_tiles(
        self,
        layer: LayerConfig,
        tiles: List[tuple],
        output_dir: Path,
        offset: int,
        total: int
    ):
        """
        Download tiles for a layer.

        Args:
            layer: Layer configuration
            tiles: List of (x, y, z) tuples
            output_dir: Output directory
            offset: Offset for progress reporting
            total: Total tiles across all layers

        Returns:
            List of downloaded tiles
        """
        def progress_callback(current, layer_total):
            self.progress.emit(offset + current, total, f"Downloading {layer.display_name}...")

        async with WMTSClient(layer) as client:
            downloaded = await client.download_tiles_batch(
                tiles,
                output_dir,
                progress_callback
            )

        return downloaded


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        """Initialize main window."""
        super().__init__()
        self.download_worker = None
        self.pending_kmz_data = None
        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        self.setWindowTitle("Google Earth Tile Generator")
        self.setGeometry(100, 100, 1200, 800)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout()

        # Left side: Map widget (70% width)
        self.map_widget = MapWidget()
        self.map_widget.setMinimumWidth(700)
        main_layout.addWidget(self.map_widget, 7)

        # Right side: Settings panel (30% width)
        self.settings_panel = SettingsPanel()
        self.settings_panel.setMaximumWidth(400)
        main_layout.addWidget(self.settings_panel, 3)

        central_widget.setLayout(main_layout)

        # Status bar with progress
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.status_bar.showMessage("Ready")

        # Connect signals
        self.map_widget.extent_changed.connect(self.settings_panel.update_extent)
        self.map_widget.extent_cleared.connect(self.settings_panel.clear_extent)
        self.settings_panel.generate_requested.connect(self.on_generate_clicked)

    def on_generate_clicked(
        self,
        layers: List[LayerConfig],
        zoom: int,
        extent: Extent,
        output_path: str
    ):
        """
        Handle generate button click.

        Args:
            layers: Selected layers
            zoom: Zoom level
            extent: Geographic extent
            output_path: Output KMZ path
        """
        # Validate extent is within Japan region
        if not extent.is_within_japan_region():
            QMessageBox.critical(
                self,
                "Invalid Extent",
                "The selected extent is outside the valid region for this WMTS service.\n"
                "Please select an area within Japan (approximately 122°E-154°E, 20°N-46°N)."
            )
            return

        # Warn if partially outside
        if not extent.is_fully_within_japan_region():
            reply = QMessageBox.warning(
                self,
                "Extent Warning",
                "The selected extent is partially outside the valid region.\n"
                "Some tiles may not be available. Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Calculate total tiles
        tile_count = TileCalculator.estimate_tile_count(
            extent.min_lon, extent.min_lat,
            extent.max_lon, extent.max_lat,
            zoom
        )
        total_tiles = tile_count * len(layers)

        # Warn if large download
        if total_tiles > 1000:
            reply = QMessageBox.warning(
                self,
                "Large Download",
                f"This will download {total_tiles:,} tiles.\n"
                f"This may take a while and use significant bandwidth.\n\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Start download
        self.start_download(layers, extent, zoom, output_path)

    def start_download(
        self,
        layers: List[LayerConfig],
        extent: Extent,
        zoom: int,
        output_path: str
    ):
        """
        Start downloading tiles.

        Args:
            layers: Layers to download
            extent: Geographic extent
            zoom: Zoom level
            output_path: Output KMZ path
        """
        # Disable generate button
        self.settings_panel.generate_button.setEnabled(False)

        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Store output path for later
        self.pending_kmz_data = (zoom, output_path)

        # Create and start worker
        self.download_worker = DownloadWorker(layers, extent, zoom)
        self.download_worker.progress.connect(self.update_progress)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.error.connect(self.on_download_error)
        self.download_worker.start()

    def update_progress(self, current: int, total: int, message: str):
        """
        Update progress bar and status.

        Args:
            current: Current progress
            total: Total items
            message: Status message
        """
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_bar.showMessage(f"{message} ({current}/{total})")

    def on_download_finished(self, layer_tiles_dict: Dict):
        """
        Handle download completion.

        Args:
            layer_tiles_dict: Downloaded tiles by layer
        """
        zoom, output_path = self.pending_kmz_data

        self.status_bar.showMessage("Generating KMZ file...")

        try:
            # Generate KMZ
            generator = KMZGenerator(Path(output_path))
            result_path = generator.create_kmz(layer_tiles_dict, zoom)

            # Cleanup temp files
            for layer, tiles in layer_tiles_dict.items():
                for tile_path, x, y, z in tiles:
                    if tile_path.exists():
                        tile_path.unlink()

            # Show success message
            QMessageBox.information(
                self,
                "Success",
                f"KMZ file created successfully!\n\nSaved to: {result_path}"
            )

            self.status_bar.showMessage("Ready")

        except Exception as e:
            logger.exception("Error generating KMZ")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to generate KMZ file:\n{str(e)}"
            )
            self.status_bar.showMessage("Error generating KMZ")

        finally:
            self.progress_bar.setVisible(False)
            self.settings_panel.generate_button.setEnabled(True)
            self.pending_kmz_data = None

    def on_download_error(self, error_message: str):
        """
        Handle download error.

        Args:
            error_message: Error message
        """
        QMessageBox.critical(
            self,
            "Download Error",
            f"Failed to download tiles:\n{error_message}"
        )

        self.progress_bar.setVisible(False)
        self.settings_panel.generate_button.setEnabled(True)
        self.status_bar.showMessage("Download failed")
        self.pending_kmz_data = None
