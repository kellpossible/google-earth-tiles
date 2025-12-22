"""Settings panel for the application."""

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt

from src.core.config import DEFAULT_ZOOM, LAYERS, LayerConfig
from src.core.tile_calculator import TileCalculator
from src.models.extent import Extent


class SettingsPanel(QWidget):
    """Panel for configuring download settings."""

    generate_requested = pyqtSignal(list, int, object, str)  # layers, zoom, extent, output_path

    def __init__(self):
        """Initialize settings panel."""
        super().__init__()
        self.current_extent: Optional[Extent] = None
        self.init_ui()

    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout()

        # Layer selection
        layer_group = QGroupBox("Layers")
        layer_layout = QVBoxLayout()

        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        for layer_key, layer_config in LAYERS.items():
            item = QListWidgetItem(
                f"{layer_config.display_name} ({layer_config.description})"
            )
            item.setData(Qt.ItemDataRole.UserRole, layer_key)
            self.layer_list.addItem(item)

        # Select first layer by default
        self.layer_list.item(0).setSelected(True)

        self.layer_list.itemSelectionChanged.connect(self._on_layer_changed)
        layer_layout.addWidget(self.layer_list)
        layer_group.setLayout(layer_layout)
        layout.addWidget(layer_group)

        # Zoom level
        zoom_group = QGroupBox("Zoom Level")
        zoom_layout = QFormLayout()

        self.zoom_spinner = QSpinBox()
        self.zoom_spinner.setMinimum(2)
        self.zoom_spinner.setMaximum(18)
        self.zoom_spinner.setValue(DEFAULT_ZOOM)
        self.zoom_spinner.valueChanged.connect(self._on_zoom_changed)

        zoom_layout.addRow("Zoom:", self.zoom_spinner)
        self.zoom_range_label = QLabel("Range: 2-18")
        zoom_layout.addRow("", self.zoom_range_label)

        zoom_group.setLayout(zoom_layout)
        layout.addWidget(zoom_group)

        # Output path
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout()

        path_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select output KMZ file...")
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_output_path)

        path_layout.addWidget(self.output_path_edit)
        path_layout.addWidget(self.browse_button)

        output_layout.addLayout(path_layout)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # Extent display
        extent_group = QGroupBox("Selected Extent")
        extent_layout = QFormLayout()

        self.north_edit = QLineEdit()
        self.north_edit.setReadOnly(True)
        self.south_edit = QLineEdit()
        self.south_edit.setReadOnly(True)
        self.east_edit = QLineEdit()
        self.east_edit.setReadOnly(True)
        self.west_edit = QLineEdit()
        self.west_edit.setReadOnly(True)

        extent_layout.addRow("North:", self.north_edit)
        extent_layout.addRow("South:", self.south_edit)
        extent_layout.addRow("East:", self.east_edit)
        extent_layout.addRow("West:", self.west_edit)

        extent_group.setLayout(extent_layout)
        layout.addWidget(extent_group)

        # Estimates
        estimate_group = QGroupBox("Estimates")
        estimate_layout = QVBoxLayout()

        self.tile_count_label = QLabel("Tiles: -")
        self.size_estimate_label = QLabel("Size: -")

        estimate_layout.addWidget(self.tile_count_label)
        estimate_layout.addWidget(self.size_estimate_label)

        estimate_group.setLayout(estimate_layout)
        layout.addWidget(estimate_group)

        # Generate button
        self.generate_button = QPushButton("Generate KMZ")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self._on_generate_clicked)
        self.generate_button.setMinimumHeight(40)

        layout.addWidget(self.generate_button)
        layout.addStretch()

        self.setLayout(layout)
        self._update_zoom_range()

    def _on_layer_changed(self):
        """Handle layer selection change."""
        self._update_zoom_range()
        self._update_estimates()

    def _on_zoom_changed(self):
        """Handle zoom level change."""
        self._update_estimates()

    def _update_zoom_range(self):
        """Update zoom range based on selected layers."""
        selected_layers = self.get_selected_layers()
        if not selected_layers:
            self.zoom_range_label.setText("Range: -")
            return

        # Find intersection of zoom ranges
        min_zoom = max(layer.min_zoom for layer in selected_layers)
        max_zoom = min(layer.max_zoom for layer in selected_layers)

        if min_zoom > max_zoom:
            self.zoom_range_label.setText(f"<font color='red'>No compatible zoom range!</font>")
            self.zoom_spinner.setEnabled(False)
        else:
            self.zoom_range_label.setText(f"Range: {min_zoom}-{max_zoom}")
            self.zoom_spinner.setMinimum(min_zoom)
            self.zoom_spinner.setMaximum(max_zoom)
            self.zoom_spinner.setEnabled(True)

            # Adjust current value if out of range
            if self.zoom_spinner.value() < min_zoom:
                self.zoom_spinner.setValue(min_zoom)
            elif self.zoom_spinner.value() > max_zoom:
                self.zoom_spinner.setValue(max_zoom)

    def _browse_output_path(self):
        """Open file dialog to select output path."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save KMZ File",
            str(Path.home() / "tiles.kmz"),
            "KMZ Files (*.kmz)"
        )

        if file_path:
            self.output_path_edit.setText(file_path)
            self._update_generate_button()

    def update_extent(self, extent: Extent):
        """
        Update the displayed extent.

        Args:
            extent: Geographic extent
        """
        self.current_extent = extent

        self.north_edit.setText(f"{extent.max_lat:.6f}")
        self.south_edit.setText(f"{extent.min_lat:.6f}")
        self.east_edit.setText(f"{extent.max_lon:.6f}")
        self.west_edit.setText(f"{extent.min_lon:.6f}")

        self._update_estimates()
        self._update_generate_button()

    def clear_extent(self):
        """Clear the displayed extent."""
        self.current_extent = None

        self.north_edit.setText("")
        self.south_edit.setText("")
        self.east_edit.setText("")
        self.west_edit.setText("")

        self._update_estimates()
        self._update_generate_button()

    def _update_estimates(self):
        """Update tile count and size estimates."""
        if not self.current_extent:
            self.tile_count_label.setText("Tiles: -")
            self.size_estimate_label.setText("Size: -")
            return

        selected_layers = self.get_selected_layers()
        if not selected_layers:
            self.tile_count_label.setText("Tiles: -")
            self.size_estimate_label.setText("Size: -")
            return

        zoom = self.zoom_spinner.value()

        # Calculate tiles for one layer
        tile_count = TileCalculator.estimate_tile_count(
            self.current_extent.min_lon,
            self.current_extent.min_lat,
            self.current_extent.max_lon,
            self.current_extent.max_lat,
            zoom
        )

        # Multiply by number of layers
        total_tiles = tile_count * len(selected_layers)

        # Estimate size (average across layers)
        total_size_mb = 0
        for layer in selected_layers:
            size_mb = TileCalculator.estimate_download_size(tile_count, layer.extension)
            total_size_mb += size_mb

        self.tile_count_label.setText(f"Tiles: {total_tiles:,}")
        self.size_estimate_label.setText(f"Size: ~{total_size_mb:.1f} MB")

    def _update_generate_button(self):
        """Update generate button enabled state."""
        has_extent = self.current_extent is not None
        has_output = bool(self.output_path_edit.text())
        has_layers = len(self.get_selected_layers()) > 0

        self.generate_button.setEnabled(has_extent and has_output and has_layers)

    def _on_generate_clicked(self):
        """Handle generate button click."""
        selected_layers = self.get_selected_layers()
        zoom = self.zoom_spinner.value()
        output_path = self.output_path_edit.text()

        self.generate_requested.emit(
            selected_layers,
            zoom,
            self.current_extent,
            output_path
        )

    def get_selected_layers(self) -> List[LayerConfig]:
        """
        Get list of selected layer configurations.

        Returns:
            List of selected LayerConfig objects
        """
        selected = []
        for item in self.layer_list.selectedItems():
            layer_key = item.data(Qt.ItemDataRole.UserRole)
            selected.append(LAYERS[layer_key])
        return selected
