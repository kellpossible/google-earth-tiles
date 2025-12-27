"""Widget for configuring extent (lat/lon or file-based)."""

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models.extent_config import ExtentConfig
from src.utils.kml_extent import calculate_extent_from_kml


class ExtentWidget(QGroupBox):
    """Widget for configuring extent (lat/lon or file-based)."""

    extent_changed = pyqtSignal(object)  # Extent object
    extent_cleared = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize extent configuration widget."""
        super().__init__("Extent Configuration", parent)

        self.current_extent_config: ExtentConfig | None = None
        self._suppress_signals = False

        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout()

        # Mode selection
        mode_layout = QFormLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Draw on Map", "map")  # Default - use map widget
        self.mode_combo.addItem("From KML File", "file")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addRow("Extent Source:", self.mode_combo)
        layout.addLayout(mode_layout)

        # File mode controls
        self.file_widget = QWidget()
        file_layout = QFormLayout()

        # File path input
        file_path_row = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select KML file...")
        self.file_path_edit.textChanged.connect(self._on_file_path_changed)
        file_path_row.addWidget(self.file_path_edit, 1)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._on_browse_clicked)
        file_path_row.addWidget(self.browse_button)

        file_layout.addRow("KML File:", file_path_row)

        # Padding input
        self.padding_spin = QDoubleSpinBox()
        self.padding_spin.setRange(0, 100000)  # 0 to 100km
        self.padding_spin.setSuffix(" m")
        self.padding_spin.setDecimals(1)
        self.padding_spin.setValue(0)
        self.padding_spin.setToolTip("Uniform padding in meters (applied to all sides)")
        self.padding_spin.valueChanged.connect(self._on_padding_changed)
        file_layout.addRow("Padding:", self.padding_spin)

        self.file_widget.setLayout(file_layout)
        layout.addWidget(self.file_widget)

        # Calculated extent display (for file mode)
        self.extent_display = QWidget()
        extent_layout = QFormLayout()

        self.north_display = QLineEdit()
        self.north_display.setReadOnly(True)
        self.south_display = QLineEdit()
        self.south_display.setReadOnly(True)
        self.east_display = QLineEdit()
        self.east_display.setReadOnly(True)
        self.west_display = QLineEdit()
        self.west_display.setReadOnly(True)

        extent_layout.addRow("North:", self.north_display)
        extent_layout.addRow("South:", self.south_display)
        extent_layout.addRow("East:", self.east_display)
        extent_layout.addRow("West:", self.west_display)

        self.extent_display.setLayout(extent_layout)
        layout.addWidget(self.extent_display)

        self.setLayout(layout)

        # Start with map mode
        self._update_ui_visibility()

    def _on_mode_changed(self):
        """Handle extent mode change."""
        self._update_ui_visibility()

        # Clear current extent when switching modes
        if not self._suppress_signals:
            self.extent_cleared.emit()

    def _update_ui_visibility(self):
        """Update visibility of mode-specific controls."""
        mode = self.mode_combo.currentData()

        is_file_mode = mode == "file"
        self.file_widget.setVisible(is_file_mode)
        self.extent_display.setVisible(is_file_mode)

    def _on_browse_clicked(self):
        """Open file browser for KML file selection."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select KML File",
            str(Path.home()),
            "KML Files (*.kml);;All Files (*)",
        )

        if file_path:
            self.file_path_edit.setText(file_path)

    def _on_file_path_changed(self):
        """Handle file path change - recalculate extent."""
        self._recalculate_extent()

    def _on_padding_changed(self):
        """Handle padding change - recalculate extent."""
        self._recalculate_extent()

    def _recalculate_extent(self):
        """Recalculate extent from KML file + padding."""
        file_path_str = self.file_path_edit.text().strip()
        if not file_path_str:
            self._clear_extent_display()
            if not self._suppress_signals:
                self.extent_cleared.emit()
            return

        file_path = Path(file_path_str)
        padding = self.padding_spin.value()

        try:
            extent = calculate_extent_from_kml(file_path, padding)

            # Update display
            self.north_display.setText(f"{extent.max_lat:.6f}")
            self.south_display.setText(f"{extent.min_lat:.6f}")
            self.east_display.setText(f"{extent.max_lon:.6f}")
            self.west_display.setText(f"{extent.min_lon:.6f}")

            # Store configuration
            self.current_extent_config = ExtentConfig(
                mode="file",
                file_path=file_path,
                padding_meters=padding,
                _resolved_extent=extent,
            )

            # Emit signal
            if not self._suppress_signals:
                self.extent_changed.emit(extent)

        except (FileNotFoundError, ValueError):
            # Clear display on error
            self._clear_extent_display()
            # Could show error in UI here
            if not self._suppress_signals:
                self.extent_cleared.emit()

    def _clear_extent_display(self):
        """Clear the extent display fields."""
        self.north_display.setText("")
        self.south_display.setText("")
        self.east_display.setText("")
        self.west_display.setText("")

    def get_mode(self) -> str:
        """Get current extent mode."""
        return self.mode_combo.currentData()

    def get_extent_config(self) -> ExtentConfig | None:
        """Get current extent configuration (for file mode)."""
        mode = self.get_mode()

        if mode == "file":
            return self.current_extent_config

        return None  # Map mode doesn't use ExtentConfig

    def set_extent_config(self, config: ExtentConfig):
        """Load extent configuration."""
        self._suppress_signals = True

        try:
            if config.mode == "file":
                self.mode_combo.setCurrentIndex(self.mode_combo.findData("file"))
                self.file_path_edit.setText(str(config.file_path))
                self.padding_spin.setValue(config.padding_meters)

                # Recalculate will happen via signal

            # Map mode is handled by parent (map widget draws extent)

        finally:
            self._suppress_signals = False

        # Trigger recalculation
        if config.mode == "file":
            self._recalculate_extent()
