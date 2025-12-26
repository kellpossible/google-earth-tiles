"""Widget for configuring a single output."""

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from src.models.extent import Extent
from src.models.layer_composition import LayerComposition
from src.models.output_config import OutputConfig
from src.outputs import get_output_handler


class OutputItemWidget(QFrame):
    """Widget for a single output configuration."""

    changed = pyqtSignal()  # Settings changed
    remove_requested = pyqtSignal()  # User wants to remove

    def __init__(self, output_config: OutputConfig, parent=None):
        """Initialize output item widget.

        Args:
            output_config: Output configuration
            parent: Parent widget
        """
        super().__init__(parent)
        self.output_config = output_config

        # State for estimates calculation
        self.extent: Extent | None = None
        self.min_zoom = 2
        self.max_zoom = 18
        self.layer_compositions: list[LayerComposition] = []

        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Set frame style to match LayerItemWidget
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        # Top row: Type dropdown and remove button
        top_row = QHBoxLayout()

        type_label = QLabel("Type:")
        top_row.addWidget(type_label)

        self.type_combo = QComboBox()
        self.type_combo.addItem("KMZ", "kmz")
        self.type_combo.setCurrentText("KMZ")
        self.type_combo.setEnabled(True)  # Enabled but only has one option
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        top_row.addWidget(self.type_combo, 1)

        self.remove_button = QPushButton("✕")
        self.remove_button.setFixedSize(24, 24)
        self.remove_button.setToolTip("Remove output")
        self.remove_button.clicked.connect(self.remove_requested.emit)
        top_row.addWidget(self.remove_button)

        layout.addLayout(top_row)

        # Path row
        path_row = QHBoxLayout()
        path_row.setContentsMargins(20, 0, 0, 0)  # Indent like layer controls

        path_label = QLabel("Path:")
        path_row.addWidget(path_label)

        self.path_edit = QLineEdit()
        # Show empty string if path is empty, not "."
        path_str = str(self.output_config.output_path) if self.output_config.output_path != Path("") else ""
        self.path_edit.setText(path_str)
        self.path_edit.setPlaceholderText("Select output file...")
        self.path_edit.textChanged.connect(self._on_path_changed)
        path_row.addWidget(self.path_edit, 1)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_output_path)
        path_row.addWidget(self.browse_button)

        layout.addLayout(path_row)

        # Web compatible checkbox (KMZ-specific)
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setContentsMargins(20, 0, 0, 0)  # Indent

        self.web_compatible_checkbox = QCheckBox("Google Earth Web Compatible Mode")
        self.web_compatible_checkbox.setChecked(self.output_config.web_compatible)
        self.web_compatible_checkbox.setToolTip(
            "Generate KMZ optimized for Google Earth Web:\n"
            "• Single zoom level (automatically calculated)\n"
            "• Merged tiles into 2048×2048 chunks\n"
            "• No Region/LOD elements\n"
            "• Limited to ~500 chunks per layer"
        )
        self.web_compatible_checkbox.stateChanged.connect(self._on_web_compatible_changed)
        checkbox_layout.addWidget(self.web_compatible_checkbox)

        layout.addLayout(checkbox_layout)

        # Estimates group
        estimate_group = QGroupBox("Estimates")
        estimate_layout = QVBoxLayout()

        self.tile_count_label = QLabel("Tiles: -")
        self.size_estimate_label = QLabel("Size: -")

        estimate_layout.addWidget(self.tile_count_label)
        estimate_layout.addWidget(self.size_estimate_label)

        estimate_group.setLayout(estimate_layout)
        layout.addWidget(estimate_group)

        self.setLayout(layout)

    def _on_type_changed(self):
        """Handle output type change."""
        # Update visibility of KMZ-specific controls
        output_type = self.type_combo.currentData()
        is_kmz = output_type == "kmz"
        self.web_compatible_checkbox.setVisible(is_kmz)

        # Update config
        self.output_config.output_type = output_type
        self.changed.emit()

    def _on_path_changed(self):
        """Handle path change."""
        self.output_config.output_path = Path(self.path_edit.text())
        self.changed.emit()

    def _on_web_compatible_changed(self):
        """Handle web compatible mode change."""
        self.output_config.web_compatible = self.web_compatible_checkbox.isChecked()
        self._update_estimates()
        self.changed.emit()

    def _browse_output_path(self):
        """Open file dialog to select output path."""
        # Default to current path or home directory
        default_path = str(self.output_config.output_path) if self.output_config.output_path else str(Path.home() / "tiles.kmz")

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save KMZ File", default_path, "KMZ Files (*.kmz)"
        )

        if file_path:
            self.path_edit.setText(file_path)
            # Note: _on_path_changed will be called automatically

    def update_estimates(self, extent: Extent | None, min_zoom: int, max_zoom: int, layer_compositions: list[LayerComposition]):
        """Update estimates for this output.

        Args:
            extent: Selected extent (or None if not set)
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of layer compositions
        """
        self.extent = extent
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.layer_compositions = layer_compositions
        self._update_estimates()

    def _update_estimates(self):
        """Calculate and update tile count and size estimates."""
        if not self.extent or not self.layer_compositions:
            self.tile_count_label.setText("Tiles: -")
            self.size_estimate_label.setText("Size: -")
            return

        # Filter to enabled layers only
        enabled_layers = [comp for comp in self.layer_compositions if comp.enabled]
        if not enabled_layers:
            self.tile_count_label.setText("Tiles: -")
            self.size_estimate_label.setText("Size: -")
            return

        try:
            # Use the output handler to calculate estimates
            handler = get_output_handler(self.output_config.output_type)
            estimates = handler.estimate_tiles(
                self.extent,
                self.min_zoom,
                self.max_zoom,
                enabled_layers,
                **self.output_config.options
            )

            self.tile_count_label.setText(estimates["count_label"])
            self.size_estimate_label.setText(estimates["size_label"])
        except Exception:
            # If estimation fails, show placeholder
            self.tile_count_label.setText("Tiles: -")
            self.size_estimate_label.setText("Size: -")

    def get_config(self) -> OutputConfig:
        """Get the current output configuration.

        Returns:
            OutputConfig instance with current settings
        """
        return OutputConfig(
            output_type=self.type_combo.currentData(),
            output_path=Path(self.path_edit.text()),
            options={"web_compatible": self.web_compatible_checkbox.isChecked()}
        )
