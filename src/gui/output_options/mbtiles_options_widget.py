"""MBTiles output format options widget."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.models.extent import Extent
from src.models.layer_composition import LayerComposition
from src.models.outputs import MBTilesOutput
from src.outputs import get_output_handler


class MBTilesOptionsWidget(QWidget):
    """Options widget for MBTiles output format."""

    changed = pyqtSignal()

    def __init__(self, initial_options: dict, parent=None):
        """Initialize MBTiles options widget.

        Args:
            initial_options: Initial option values from config
            parent: Parent widget
        """
        super().__init__(parent)
        self.extent: Extent | None = None
        self.min_zoom = 2
        self.max_zoom = 18
        self.layer_compositions: list[LayerComposition] = []

        self._init_ui(initial_options)

    def _init_ui(self, initial_options: dict):
        """Initialize the UI.

        Args:
            initial_options: Initial option values
        """
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 0, 0, 0)

        # Image format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Image Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItem("PNG (Lossless)", "png")
        self.format_combo.addItem("JPEG (Compressed)", "jpg")
        image_format = initial_options.get("image_format", "png")
        idx = self.format_combo.findData(image_format)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addWidget(self.format_combo, 1)
        layout.addLayout(format_layout)

        # JPEG quality slider (only visible when JPEG selected)
        self.quality_layout = QHBoxLayout()
        self.quality_label = QLabel("JPEG Quality:")
        self.quality_layout.addWidget(self.quality_label)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setMinimum(1)
        self.quality_slider.setMaximum(100)
        jpeg_quality = initial_options.get("jpeg_quality", 80)
        self.quality_slider.setValue(jpeg_quality)
        self.quality_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.quality_slider.setTickInterval(10)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)
        self.quality_layout.addWidget(self.quality_slider, 1)
        self.quality_value_label = QLabel(str(jpeg_quality))
        self.quality_layout.addWidget(self.quality_value_label)
        layout.addLayout(self.quality_layout)

        # Update quality visibility based on initial format
        self._update_quality_visibility()

        # Export mode selection
        export_layout = QHBoxLayout()
        export_layout.addWidget(QLabel("Export Mode:"))
        self.export_combo = QComboBox()
        self.export_combo.addItem("Composite (Single File)", "composite")
        self.export_combo.addItem("Separate (One per Layer)", "separate")
        export_mode = initial_options.get("export_mode", "composite")
        idx = self.export_combo.findData(export_mode)
        if idx >= 0:
            self.export_combo.setCurrentIndex(idx)
        self.export_combo.currentIndexChanged.connect(self._on_option_changed)
        export_layout.addWidget(self.export_combo, 1)
        layout.addLayout(export_layout)

        # Metadata group
        metadata_group = QGroupBox("Metadata")
        metadata_layout = QVBoxLayout()

        # Type selection
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("Base Layer", "baselayer")
        self.type_combo.addItem("Overlay", "overlay")
        metadata_type = initial_options.get("metadata_type", "baselayer")
        idx = self.type_combo.findData(metadata_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentIndexChanged.connect(self._on_option_changed)
        type_layout.addWidget(self.type_combo, 1)
        metadata_layout.addLayout(type_layout)

        metadata_group.setLayout(metadata_layout)
        layout.addWidget(metadata_group)

        # Estimates group
        estimate_group = QGroupBox("Estimates")
        estimate_layout = QVBoxLayout()

        self.tile_count_label = QLabel("Tiles: -")
        self.size_estimate_label = QLabel("Size: -")

        estimate_layout.addWidget(self.tile_count_label)
        estimate_layout.addWidget(self.size_estimate_label)

        estimate_group.setLayout(estimate_layout)
        layout.addWidget(estimate_group)

        layout.addStretch()
        self.setLayout(layout)

    def _on_format_changed(self):
        """Handle image format change."""
        self._update_quality_visibility()
        self._on_option_changed()

    def _update_quality_visibility(self):
        """Show/hide JPEG quality controls based on selected format."""
        is_jpeg = self.format_combo.currentData() == "jpg"
        self.quality_label.setVisible(is_jpeg)
        self.quality_slider.setVisible(is_jpeg)
        self.quality_value_label.setVisible(is_jpeg)

    def _on_quality_changed(self):
        """Handle JPEG quality slider change."""
        quality = self.quality_slider.value()
        self.quality_value_label.setText(str(quality))
        self.changed.emit()

    def _on_option_changed(self):
        """Handle option change."""
        self._update_estimates()
        self.changed.emit()

    def get_options(self) -> dict:
        """Get current option values.

        Returns:
            Dictionary of option values
        """
        return {
            "image_format": self.format_combo.currentData(),
            "jpeg_quality": self.quality_slider.value(),
            "export_mode": self.export_combo.currentData(),
            "metadata_type": self.type_combo.currentData(),
        }

    def update_estimates(
        self,
        extent: Extent | None,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
    ):
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
            handler = get_output_handler("mbtiles")
            # Construct output model for estimation
            output = MBTilesOutput(type="mbtiles", path="", **self.get_options())
            estimates = handler.estimate_tiles(
                self.extent,
                self.min_zoom,
                self.max_zoom,
                enabled_layers,
                output,
            )

            self.tile_count_label.setText(estimates["count_label"])
            self.size_estimate_label.setText(estimates["size_label"])
        except Exception:
            # If estimation fails, show placeholder
            self.tile_count_label.setText("Tiles: -")
            self.size_estimate_label.setText("Size: -")
