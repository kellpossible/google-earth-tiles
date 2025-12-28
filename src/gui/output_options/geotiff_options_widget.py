"""GeoTIFF output format options widget."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
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
from src.models.outputs import GeoTIFFOutput
from src.outputs import get_output_handler


class GeoTIFFOptionsWidget(QWidget):
    """Options widget for GeoTIFF output format."""

    changed = pyqtSignal()

    def __init__(self, initial_options: dict, parent=None):
        """Initialize GeoTIFF options widget.

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

        # Compression selection
        compression_layout = QHBoxLayout()
        compression_layout.addWidget(QLabel("Compression:"))
        self.compression_combo = QComboBox()
        self.compression_combo.addItem("LZW (Lossless)", "lzw")
        self.compression_combo.addItem("DEFLATE (Best)", "deflate")
        self.compression_combo.addItem("JPEG (Lossy)", "jpeg")
        self.compression_combo.addItem("None", "none")
        compression = initial_options.get("compression", "lzw")
        idx = self.compression_combo.findData(compression)
        if idx >= 0:
            self.compression_combo.setCurrentIndex(idx)
        self.compression_combo.currentIndexChanged.connect(self._on_compression_changed)
        compression_layout.addWidget(self.compression_combo, 1)
        layout.addLayout(compression_layout)

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

        # Update quality visibility based on initial compression
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

        # Multi-zoom checkbox
        multi_zoom_layout = QHBoxLayout()
        self.multi_zoom_checkbox = QCheckBox("Include pyramids for all zoom levels")
        multi_zoom = initial_options.get("multi_zoom", True)
        self.multi_zoom_checkbox.setChecked(multi_zoom)
        self.multi_zoom_checkbox.setToolTip(
            "When enabled, generates internal overviews (pyramids) for efficient multi-scale viewing. "
            "When disabled, only generates tiles at the maximum zoom level (smaller file size)."
        )
        self.multi_zoom_checkbox.stateChanged.connect(self._on_option_changed)
        multi_zoom_layout.addWidget(self.multi_zoom_checkbox)
        multi_zoom_layout.addStretch()
        layout.addLayout(multi_zoom_layout)

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

    def _on_compression_changed(self):
        """Handle compression type change."""
        self._update_quality_visibility()
        self._on_option_changed()

    def _update_quality_visibility(self):
        """Show/hide JPEG quality controls based on selected compression."""
        is_jpeg = self.compression_combo.currentData() == "jpeg"
        self.quality_label.setVisible(is_jpeg)
        self.quality_slider.setVisible(is_jpeg)
        self.quality_value_label.setVisible(is_jpeg)

    def _on_quality_changed(self):
        """Handle JPEG quality slider change."""
        quality = self.quality_slider.value()
        self.quality_value_label.setText(str(quality))
        self._on_option_changed()

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
            "compression": self.compression_combo.currentData(),
            "jpeg_quality": self.quality_slider.value(),
            "export_mode": self.export_combo.currentData(),
            "multi_zoom": self.multi_zoom_checkbox.isChecked(),
            "tiled": True,  # Always use tiled format
            "tile_size": 256,  # Default tile size
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
            handler = get_output_handler("geotiff")
            # Construct output model for estimation
            output = GeoTIFFOutput(type="geotiff", path="", **self.get_options())
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
