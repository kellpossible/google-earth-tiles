"""KMZ output format options widget."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QGroupBox, QLabel, QVBoxLayout, QWidget

from src.models.extent import Extent
from src.models.layer_composition import LayerComposition
from src.outputs import get_output_handler


class KMZOptionsWidget(QWidget):
    """Options widget for KMZ output format."""

    changed = pyqtSignal()

    def __init__(self, initial_options: dict, parent=None):
        """Initialize KMZ options widget.

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

        # Web compatible checkbox
        self.web_compatible_checkbox = QCheckBox("Google Earth Web Compatible Mode")
        self.web_compatible_checkbox.setChecked(initial_options.get("web_compatible", False))
        self.web_compatible_checkbox.setToolTip(
            "Generate KMZ optimized for Google Earth Web:\n"
            "• Single zoom level (automatically calculated)\n"
            "• Merged tiles into 2048×2048 chunks\n"
            "• No Region/LOD elements\n"
            "• Limited to ~500 chunks per layer"
        )
        self.web_compatible_checkbox.stateChanged.connect(self._on_option_changed)
        layout.addWidget(self.web_compatible_checkbox)

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
            "web_compatible": self.web_compatible_checkbox.isChecked(),
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
            handler = get_output_handler("kmz")
            estimates = handler.estimate_tiles(
                self.extent,
                self.min_zoom,
                self.max_zoom,
                enabled_layers,
                **self.get_options(),
            )

            self.tile_count_label.setText(estimates["count_label"])
            self.size_estimate_label.setText(estimates["size_label"])
        except Exception:
            # If estimation fails, show placeholder
            self.tile_count_label.setText("Tiles: -")
            self.size_estimate_label.setText("Size: -")
