"""Main application window."""

import logging
from pathlib import Path
from typing import Optional

from PyQt6 import QtGui
from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.core.kmz_generator import KMZGenerator
from src.core.tile_calculator import TileCalculator
from src.gui.file_operations import FileOperations
from src.gui.map_widget import MapWidget
from src.gui.settings_panel import SettingsPanel
from src.models.extent import Extent
from src.models.generation_request import GenerationRequest
from src.models.layer_composition import LayerComposition

logger = logging.getLogger(__name__)


class ExportWorker(QThread):
    """Worker thread for complete export: download tiles, composite, and create KMZ."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(Path)  # output_path
    error = pyqtSignal(str)

    def __init__(self, request: GenerationRequest):
        """
        Initialize export worker.

        Args:
            request: Generation request with all parameters
        """
        super().__init__()
        self.request = request.copy()  # Defensive copy

    def run(self):
        """Run the complete export process."""
        try:
            min_zoom = self.request.min_zoom
            max_zoom = self.request.max_zoom

            # Calculate total work units for progress tracking
            # Estimate based on total tiles across all zoom levels
            total_tiles = 0
            for zoom_level in range(min_zoom, max_zoom + 1):
                tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                    self.request.extent.min_lon,
                    self.request.extent.min_lat,
                    self.request.extent.max_lon,
                    self.request.extent.max_lat,
                    zoom_level
                )
                total_tiles += len(tiles_at_zoom)

            total_units = total_tiles

            # Generate KMZ (tiles will be fetched on-demand with caching)
            is_multi_zoom = min_zoom < max_zoom
            self.progress.emit(
                0,
                total_units,
                "Generating KMZ with LOD pyramid..." if is_multi_zoom else "Generating KMZ..."
            )

            def kmz_progress(current: int, total: int, message: str):
                """Forward KMZ progress to UI."""
                self.progress.emit(current, total, message)

            generator = KMZGenerator(self.request.output_path, kmz_progress)
            result_path = generator.create_kmz(
                self.request.extent,
                min_zoom,
                max_zoom,
                self.request.layer_compositions,
                self.request.web_compatible
            )

            self.finished.emit(result_path)

        except Exception as e:
            logger.exception("Error during export")
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        """Initialize main window."""
        super().__init__()
        self.export_worker = None

        # File operations handler
        self.file_ops = FileOperations(self)

        # Track recent file menu actions for dynamic updates
        self.recent_file_actions = []

        # Debounce timer for map updates (prevents rapid refreshes during slider drag)
        self.map_update_timer = QTimer()
        self.map_update_timer.setSingleShot(True)
        self.map_update_timer.timeout.connect(self._do_map_update_no_zoom)
        self.map_refresh_in_progress = False
        self.pending_refresh_needed = False

        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        # Create menu bar FIRST
        self._create_menu_bar()

        # Set initial window title
        self.setWindowTitle(self.file_ops.get_display_title())
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
        self.settings_panel.setMaximumWidth(500)
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
        self.map_widget.preview_zoom_changed.connect(self.settings_panel.update_preview_zoom)
        self.settings_panel.generate_requested.connect(self.on_generate_clicked)
        self.settings_panel.sync_preview_zoom_requested.connect(self.map_widget.set_preview_zoom)
        self.settings_panel.extent_loaded.connect(self.map_widget.set_extent)

        # Connect layer composition changes to map preview
        # (Individual layer widget signals are connected when layers are added)
        self.settings_panel.changed.connect(self._update_map_preview)
        self.settings_panel.settings_changed_no_zoom.connect(self._update_map_preview_no_zoom)

        # Connect state change tracking
        self.settings_panel.state_changed.connect(self._on_state_changed)

        # Trigger initial map update with default layer
        self._update_map_preview()

    def _update_map_preview(self):
        """Update the map preview when layer list changes (with zoom limit update)."""
        layer_compositions = self.settings_panel.get_layer_compositions()
        self.map_widget.update_layer_composition(layer_compositions, update_zoom_limits=True)

    def _update_map_preview_no_zoom(self):
        """Update the map preview when layer settings change (debounced to avoid race conditions)."""
        # Restart the timer - if user is still dragging, this delays the update
        # Only after 500ms of no changes will the update actually happen
        self.map_update_timer.stop()
        self.map_update_timer.start(500)  # 500ms debounce - increased to reduce load during slider dragging

    def _do_map_update_no_zoom(self):
        """Actually perform the map update (called after debounce timer expires)."""
        # Guard against concurrent refreshes
        if self.map_refresh_in_progress:
            self.pending_refresh_needed = True
            return

        self.map_refresh_in_progress = True

        layer_compositions = self.settings_panel.get_layer_compositions()
        self.map_widget.update_layer_composition(layer_compositions, update_zoom_limits=False)

        # Mark refresh as complete immediately - the debounce timer handles rate limiting
        # Tiles will load asynchronously in the background
        QTimer.singleShot(100, self._on_refresh_complete)

    def _on_refresh_complete(self):
        """Called after a refresh has had time to complete."""
        self.map_refresh_in_progress = False

        # If another refresh was requested while we were busy, do it now
        if self.pending_refresh_needed:
            self.pending_refresh_needed = False
            self._do_map_update_no_zoom()

    def on_generate_clicked(self, request: GenerationRequest):
        """
        Handle generate button click.

        Args:
            request: Generation request with all parameters
        """
        # Validate extent is within Japan region
        if not request.extent.is_within_japan_region():
            QMessageBox.critical(
                self,
                "Invalid Extent",
                "The selected extent is outside the valid region for this WMTS service.\n"
                "Please select an area within Japan (approximately 122°E-154°E, 20°N-46°N)."
            )
            return

        # Warn if partially outside
        if not request.extent.is_fully_within_japan_region():
            reply = QMessageBox.warning(
                self,
                "Extent Warning",
                "The selected extent is partially outside the valid region.\n"
                "Some tiles may not be available. Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Extract just the layer configs for download
        layers = [comp.layer_config for comp in request.layer_compositions]

        # Calculate total tiles across all zoom levels
        total_tiles = 0
        for zoom_level in range(request.min_zoom, request.max_zoom + 1):
            tile_count = TileCalculator.estimate_tile_count(
                request.extent.min_lon, request.extent.min_lat,
                request.extent.max_lon, request.extent.max_lat,
                zoom_level
            )
            total_tiles += tile_count * len(layers)

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
        self.start_download(request)

    def start_download(self, request: GenerationRequest):
        """
        Start export process (download + composite + KMZ creation).

        Args:
            request: Generation request with all parameters
        """
        # Disable generate button
        self.settings_panel.generate_button.setEnabled(False)

        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Create and start unified export worker
        # Note: ExportWorker creates defensive copy via request.copy()
        self.export_worker = ExportWorker(request)
        self.export_worker.progress.connect(self.update_progress)
        self.export_worker.finished.connect(self.on_export_finished)
        self.export_worker.error.connect(self.on_export_error)
        self.export_worker.start()

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

    def on_export_finished(self, result_path: Path):
        """
        Handle export completion.

        Args:
            result_path: Path to created KMZ file
        """
        # Show success message
        QMessageBox.information(
            self,
            "Success",
            f"KMZ file created successfully!\n\nSaved to: {result_path}"
        )

        self.status_bar.showMessage("Ready")
        self.progress_bar.setVisible(False)
        self.settings_panel.generate_button.setEnabled(True)

    def on_export_error(self, error_message: str):
        """
        Handle export error.

        Args:
            error_message: Error message
        """
        QMessageBox.critical(
            self,
            "Export Error",
            f"Failed to export KMZ:\n{error_message}"
        )

        self.progress_bar.setVisible(False)
        self.settings_panel.generate_button.setEnabled(True)
        self.status_bar.showMessage("Export failed")

    def _create_menu_bar(self):
        """Create the menu bar with File menu."""
        menubar = self.menuBar()
        self.file_menu = menubar.addMenu("&File")

        # Open
        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.setStatusTip("Open configuration file")
        open_action.triggered.connect(self._on_open)
        self.file_menu.addAction(open_action)

        # Mark where recent files section starts
        self.recent_files_start_separator = self.file_menu.addSeparator()

        # Recent files will be inserted here dynamically
        # (between start and end separators)

        # Mark where recent files section ends (before Save)
        self.recent_files_end_separator = self.file_menu.addSeparator()

        # Save
        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setStatusTip("Save configuration")
        save_action.triggered.connect(self._on_save)
        self.file_menu.addAction(save_action)

        # Save As
        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.setStatusTip("Save configuration as new file")
        save_as_action.triggered.connect(self._on_save_as)
        self.file_menu.addAction(save_as_action)

        self.file_menu.addSeparator()

        # Quit
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.setStatusTip("Quit application")
        quit_action.triggered.connect(self.close)
        self.file_menu.addAction(quit_action)

        # Initial population of recent files
        self._update_recent_files_menu()

    def _on_open(self):
        """Handle File > Open action."""
        if self.file_ops.open(self.settings_panel.load_state_dict, self.settings_panel.get_state_dict):
            self._update_window_title()
            self._update_recent_files_menu()

    def _on_save(self):
        """Handle File > Save action."""
        if self.file_ops.save(self.settings_panel.get_state_dict):
            self._update_window_title()
            self._update_recent_files_menu()

    def _on_save_as(self):
        """Handle File > Save As action."""
        if self.file_ops.save_as(self.settings_panel.get_state_dict):
            self._update_window_title()
            self._update_recent_files_menu()

    def _update_window_title(self):
        """Update window title based on file state."""
        self.setWindowTitle(self.file_ops.get_display_title())

    def _on_state_changed(self):
        """Handle any state change in settings panel."""
        self.file_ops.mark_dirty()
        self._update_window_title()

    def _update_recent_files_menu(self):
        """Update the Recent Files section in the File menu."""
        # Remove all existing recent file actions
        for action in self.recent_file_actions:
            self.file_menu.removeAction(action)
        self.recent_file_actions.clear()

        recent_files = self.file_ops.get_recent_files()

        if not recent_files:
            # Show "No Recent Files" disabled action
            no_recent = QAction("No Recent Files", self)
            no_recent.setEnabled(False)
            self.file_menu.insertAction(self.recent_files_end_separator, no_recent)
            self.recent_file_actions.append(no_recent)
        else:
            # Add first 5 files directly to menu
            for i, file_path_str in enumerate(recent_files[:5]):
                file_path = Path(file_path_str)

                action = QAction(f"&{i+1} {file_path.name}", self)
                action.setStatusTip(str(file_path))
                action.setData(file_path_str)
                action.triggered.connect(
                    lambda checked, path=file_path_str: self._open_recent_file(path)
                )
                self.file_menu.insertAction(self.recent_files_end_separator, action)
                self.recent_file_actions.append(action)

            # If more than 5 files, create "More" submenu
            if len(recent_files) > 5:
                more_menu = QMenu("&More", self)

                for i, file_path_str in enumerate(recent_files[5:], start=5):
                    file_path = Path(file_path_str)

                    # Use numbered shortcuts (6-9, then 0)
                    if i < 9:
                        action = QAction(f"&{i+1} {file_path.name}", self)
                    else:
                        action = QAction(f"&0 {file_path.name}", self)

                    action.setStatusTip(str(file_path))
                    action.setData(file_path_str)
                    action.triggered.connect(
                        lambda checked, path=file_path_str: self._open_recent_file(path)
                    )
                    more_menu.addAction(action)

                # Insert More submenu
                more_action = self.file_menu.insertMenu(self.recent_files_end_separator, more_menu)
                self.recent_file_actions.append(more_action)

            # Add separator before Clear
            sep = self.file_menu.insertSeparator(self.recent_files_end_separator)
            self.recent_file_actions.append(sep)

            # Add Clear Recent Files
            clear_action = QAction("Clear Recent Files", self)
            clear_action.triggered.connect(self._clear_recent_files)
            self.file_menu.insertAction(self.recent_files_end_separator, clear_action)
            self.recent_file_actions.append(clear_action)

    def _open_recent_file(self, file_path_str: str):
        """
        Open a file from recent files list.

        Args:
            file_path_str: String path to recent file
        """
        if self.file_ops.open_recent(
            Path(file_path_str),
            self.settings_panel.load_state_dict,
            self.settings_panel.get_state_dict
        ):
            self._update_window_title()
            self._update_recent_files_menu()

    def _clear_recent_files(self):
        """Clear the recent files list."""
        self.file_ops.clear_recent_files()
        self._update_recent_files_menu()

    def closeEvent(self, a0: Optional[QtGui.QCloseEvent]) -> None:
        """
        Handle window close event.

        Args:
            a0: Close event
        """
        event = a0  # Reassign for readability
        if event and self.file_ops.prompt_save_before_close(self.settings_panel.get_state_dict):
            event.accept()
        else:
            if event:
                event.ignore()
