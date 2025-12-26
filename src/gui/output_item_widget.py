"""Widget for configuring a single output."""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
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
    QSlider,
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
        self.type_combo.addItem("MBTiles", "mbtiles")
        self.type_combo.setCurrentText("KMZ")
        self.type_combo.setEnabled(True)
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

        # MBTiles-specific controls
        # Image format selection
        self.mbtiles_format_layout = QHBoxLayout()
        self.mbtiles_format_layout.setContentsMargins(20, 0, 0, 0)
        self.mbtiles_format_label = QLabel("Image Format:")
        self.mbtiles_format_layout.addWidget(self.mbtiles_format_label)
        self.mbtiles_format_combo = QComboBox()
        self.mbtiles_format_combo.addItem("PNG (Lossless)", "png")
        self.mbtiles_format_combo.addItem("JPEG (Compressed)", "jpg")
        self.mbtiles_format_combo.setCurrentIndex(0)
        self.mbtiles_format_combo.currentIndexChanged.connect(self._on_mbtiles_format_changed)
        self.mbtiles_format_layout.addWidget(self.mbtiles_format_combo, 1)
        layout.addLayout(self.mbtiles_format_layout)

        # JPEG quality slider (only visible when JPEG selected)
        self.jpeg_quality_layout = QHBoxLayout()
        self.jpeg_quality_layout.setContentsMargins(20, 0, 0, 0)
        self.jpeg_quality_label = QLabel("JPEG Quality:")
        self.jpeg_quality_layout.addWidget(self.jpeg_quality_label)
        self.jpeg_quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_quality_slider.setMinimum(1)
        self.jpeg_quality_slider.setMaximum(100)
        self.jpeg_quality_slider.setValue(80)
        self.jpeg_quality_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.jpeg_quality_slider.setTickInterval(10)
        self.jpeg_quality_slider.valueChanged.connect(self._on_jpeg_quality_changed)
        self.jpeg_quality_layout.addWidget(self.jpeg_quality_slider, 1)
        self.jpeg_quality_value_label = QLabel("80")
        self.jpeg_quality_layout.addWidget(self.jpeg_quality_value_label)
        layout.addLayout(self.jpeg_quality_layout)

        # Export mode selection
        self.export_mode_layout = QHBoxLayout()
        self.export_mode_layout.setContentsMargins(20, 0, 0, 0)
        self.export_mode_label = QLabel("Export Mode:")
        self.export_mode_layout.addWidget(self.export_mode_label)
        self.mbtiles_export_combo = QComboBox()
        self.mbtiles_export_combo.addItem("Composite (Single File)", "composite")
        self.mbtiles_export_combo.addItem("Separate (One per Layer)", "separate")
        self.mbtiles_export_combo.setCurrentIndex(0)
        self.mbtiles_export_combo.currentIndexChanged.connect(self._on_mbtiles_export_changed)
        self.export_mode_layout.addWidget(self.mbtiles_export_combo, 1)
        layout.addLayout(self.export_mode_layout)

        # Metadata group
        self.metadata_group = QGroupBox("Metadata")
        metadata_layout = QVBoxLayout()

        # Name field
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.mbtiles_name_edit = QLineEdit()
        self.mbtiles_name_edit.setPlaceholderText("Tileset name...")
        self.mbtiles_name_edit.setText("Tile Export")
        self.mbtiles_name_edit.textChanged.connect(self._on_metadata_changed)
        name_layout.addWidget(self.mbtiles_name_edit, 1)
        metadata_layout.addLayout(name_layout)

        # Description field
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        self.mbtiles_desc_edit = QLineEdit()
        self.mbtiles_desc_edit.setPlaceholderText("Optional description...")
        self.mbtiles_desc_edit.textChanged.connect(self._on_metadata_changed)
        desc_layout.addWidget(self.mbtiles_desc_edit, 1)
        metadata_layout.addLayout(desc_layout)

        # Attribution field
        attr_layout = QHBoxLayout()
        attr_layout.addWidget(QLabel("Attribution:"))
        self.mbtiles_attr_edit = QLineEdit()
        self.mbtiles_attr_edit.setPlaceholderText("Optional attribution...")
        self.mbtiles_attr_edit.textChanged.connect(self._on_metadata_changed)
        attr_layout.addWidget(self.mbtiles_attr_edit, 1)
        metadata_layout.addLayout(attr_layout)

        # Type selection
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.mbtiles_type_combo = QComboBox()
        self.mbtiles_type_combo.addItem("Base Layer", "baselayer")
        self.mbtiles_type_combo.addItem("Overlay", "overlay")
        self.mbtiles_type_combo.setCurrentIndex(0)  # Default to Base Layer
        self.mbtiles_type_combo.currentIndexChanged.connect(self._on_metadata_changed)
        type_layout.addWidget(self.mbtiles_type_combo, 1)
        metadata_layout.addLayout(type_layout)

        self.metadata_group.setLayout(metadata_layout)
        layout.addWidget(self.metadata_group)

        # Initially hide all MBTiles controls
        self._set_mbtiles_controls_visible(False)

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
        output_type = self.type_combo.currentData()
        is_kmz = output_type == "kmz"
        is_mbtiles = output_type == "mbtiles"

        # Update visibility of format-specific controls
        self.web_compatible_checkbox.setVisible(is_kmz)
        self._set_mbtiles_controls_visible(is_mbtiles)

        # Auto-update file extension based on output type
        current_path = Path(self.path_edit.text()) if self.path_edit.text() else None
        if current_path and str(current_path) != ".":
            handler = get_output_handler(output_type)
            new_ext = handler.get_file_extension()

            # Replace extension only if it's a recognized output extension
            current_ext = current_path.suffix.lower().lstrip(".")
            recognized_extensions = ["kmz", "mbtiles"]

            if current_ext in recognized_extensions or not current_ext:
                # Replace or add the correct extension
                new_path = current_path.with_suffix(f".{new_ext}")
                self.path_edit.setText(str(new_path))

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

    def _set_mbtiles_controls_visible(self, visible: bool):
        """Show or hide all MBTiles-specific controls.

        Args:
            visible: True to show controls, False to hide
        """
        # Show/hide all MBTiles control widgets
        for i in range(self.mbtiles_format_layout.count()):
            widget = self.mbtiles_format_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(visible)

        for i in range(self.export_mode_layout.count()):
            widget = self.export_mode_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(visible)

        self.metadata_group.setVisible(visible)

        # JPEG quality is conditional - only show if JPEG is selected
        if visible:
            image_format = self.mbtiles_format_combo.currentData()
            is_jpeg = image_format == "jpg"
            for i in range(self.jpeg_quality_layout.count()):
                widget = self.jpeg_quality_layout.itemAt(i).widget()
                if widget:
                    widget.setVisible(is_jpeg)
        else:
            for i in range(self.jpeg_quality_layout.count()):
                widget = self.jpeg_quality_layout.itemAt(i).widget()
                if widget:
                    widget.setVisible(False)

    def _on_mbtiles_format_changed(self):
        """Handle MBTiles image format change."""
        image_format = self.mbtiles_format_combo.currentData()
        is_jpeg = image_format == "jpg"

        # Show/hide JPEG quality controls
        for i in range(self.jpeg_quality_layout.count()):
            widget = self.jpeg_quality_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(is_jpeg)

        # Update estimates (PNG vs JPEG affects size)
        self._update_estimates()
        self.changed.emit()

    def _on_jpeg_quality_changed(self):
        """Handle JPEG quality slider change."""
        quality = self.jpeg_quality_slider.value()
        self.jpeg_quality_value_label.setText(str(quality))
        self.changed.emit()

    def _on_mbtiles_export_changed(self):
        """Handle MBTiles export mode change."""
        # Update estimates (separate mode affects file count/size)
        self._update_estimates()
        self.changed.emit()

    def _on_metadata_changed(self):
        """Handle MBTiles metadata field changes."""
        self.changed.emit()

    def _browse_output_path(self):
        """Open file dialog to select output path."""
        # Get format-specific file filter and extension
        output_type = self.type_combo.currentData()
        handler = get_output_handler(output_type)
        file_filter = handler.get_file_filter()
        default_ext = handler.get_file_extension()

        # Default to current path or home directory with appropriate extension
        if self.output_config.output_path and str(self.output_config.output_path):
            default_path = str(self.output_config.output_path)
        else:
            default_path = str(Path.home() / f"tiles.{default_ext}")

        file_path, _ = QFileDialog.getSaveFileName(
            self, f"Save {handler.get_display_name()} File", default_path, file_filter
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
        output_type = self.type_combo.currentData()

        # Build format-specific options
        if output_type == "kmz":
            options = {"web_compatible": self.web_compatible_checkbox.isChecked()}
        elif output_type == "mbtiles":
            options = {
                "image_format": self.mbtiles_format_combo.currentData(),
                "jpeg_quality": self.jpeg_quality_slider.value(),
                "export_mode": self.mbtiles_export_combo.currentData(),
                "metadata_name": self.mbtiles_name_edit.text(),
                "metadata_description": self.mbtiles_desc_edit.text(),
                "metadata_attribution": self.mbtiles_attr_edit.text(),
                "metadata_type": self.mbtiles_type_combo.currentData(),
            }
        else:
            options = {}

        return OutputConfig(
            output_type=output_type,
            output_path=Path(self.path_edit.text()),
            options=options
        )
