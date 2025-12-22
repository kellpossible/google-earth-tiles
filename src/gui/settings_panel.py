"""Settings panel for the application."""

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.config import DEFAULT_ZOOM, LAYERS, LayerConfig
from src.core.tile_calculator import TileCalculator
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition


# Blend modes supported by KML (Google Earth)
BLEND_MODES = [
    ('Normal', 'normal'),
    ('Multiply', 'multiply'),
    ('Screen', 'screen'),
    ('Overlay', 'overlay'),
]


class LayerItemWidget(QFrame):
    """Widget for a single layer with composition controls."""

    moved_up = pyqtSignal()
    moved_down = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, layer_config: LayerConfig, parent=None):
        """Initialize layer item widget.

        Args:
            layer_config: Layer configuration
            parent: Parent widget
        """
        super().__init__(parent)
        self.layer_config = layer_config
        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Top row: checkbox, name, info button
        top_row = QHBoxLayout()

        self.enabled_checkbox = QCheckBox()
        self.enabled_checkbox.setChecked(False)
        self.enabled_checkbox.stateChanged.connect(self.changed.emit)
        top_row.addWidget(self.enabled_checkbox)

        name_label = QLabel(f"{self.layer_config.display_name}")
        name_label.setStyleSheet("font-weight: bold;")
        top_row.addWidget(name_label, 1)

        self.info_button = QPushButton("ℹ️")
        self.info_button.setFixedSize(24, 24)
        self.info_button.setToolTip("Show layer information")
        self.info_button.clicked.connect(self.show_info)
        top_row.addWidget(self.info_button)

        layout.addLayout(top_row)

        # Controls row: opacity, blend mode, up/down buttons
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(20, 0, 0, 0)  # Indent controls

        # Opacity slider
        opacity_label = QLabel("Opacity:")
        controls_layout.addWidget(opacity_label)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.opacity_slider.setTickInterval(25)
        self.opacity_slider.valueChanged.connect(self._update_opacity_label)
        self.opacity_slider.valueChanged.connect(self.changed.emit)
        controls_layout.addWidget(self.opacity_slider, 2)

        self.opacity_value_label = QLabel("100%")
        self.opacity_value_label.setMinimumWidth(40)
        controls_layout.addWidget(self.opacity_value_label)

        # Blend mode
        blend_label = QLabel("Blend:")
        controls_layout.addWidget(blend_label)

        self.blend_combo = QComboBox()
        for display_name, value in BLEND_MODES:
            self.blend_combo.addItem(display_name, value)
        self.blend_combo.currentIndexChanged.connect(self.changed.emit)
        controls_layout.addWidget(self.blend_combo)

        # Up/Down buttons
        self.up_button = QPushButton("↑")
        self.up_button.setFixedSize(24, 24)
        self.up_button.setToolTip("Move layer up")
        self.up_button.clicked.connect(self.moved_up.emit)
        controls_layout.addWidget(self.up_button)

        self.down_button = QPushButton("↓")
        self.down_button.setFixedSize(24, 24)
        self.down_button.setToolTip("Move layer down")
        self.down_button.clicked.connect(self.moved_down.emit)
        controls_layout.addWidget(self.down_button)

        layout.addLayout(controls_layout)

        self.setLayout(layout)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setStyleSheet("LayerItemWidget { border: 1px solid #ccc; border-radius: 4px; }")

    def _update_opacity_label(self, value: int):
        """Update opacity label with current value."""
        self.opacity_value_label.setText(f"{value}%")

    def show_info(self):
        """Show information dialog for this layer."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle(f"Layer Information - {self.layer_config.display_name}")
        dialog.setTextFormat(Qt.TextFormat.RichText)

        info_text = f"""
        <h3>{self.layer_config.display_name}</h3>
        <p><b>Japanese Name:</b> {self.layer_config.japanese_name}</p>
        <p><b>Format:</b> {self.layer_config.extension.upper()}</p>
        <p><b>Zoom Range:</b> {self.layer_config.min_zoom} - {self.layer_config.max_zoom}</p>
        <br>
        <p>{self.layer_config.full_description}</p>
        <br>
        <p><b>More information:</b><br>
        <a href="{self.layer_config.info_url}">{self.layer_config.info_url}</a></p>
        """

        dialog.setText(info_text)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.exec()

    def is_enabled(self) -> bool:
        """Check if layer is enabled."""
        return self.enabled_checkbox.isChecked()

    def get_opacity(self) -> int:
        """Get opacity value (0-100)."""
        return self.opacity_slider.value()

    def get_blend_mode(self) -> str:
        """Get selected blend mode value."""
        return self.blend_combo.currentData()


class SettingsPanel(QWidget):
    """Panel for configuring download settings."""

    generate_requested = pyqtSignal(list, int, object, str)  # List[LayerComposition], zoom, extent, output_path

    def __init__(self):
        """Initialize settings panel."""
        super().__init__()
        self.current_extent: Optional[Extent] = None
        self.layer_widgets: List[LayerItemWidget] = []
        self.init_ui()

    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout()

        # Layer composition
        layer_group = QGroupBox("Layer Composition")
        layer_layout = QVBoxLayout()

        # Scroll area for layer widgets
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        self.layers_container_layout = QVBoxLayout()
        self.layers_container_layout.setSpacing(5)

        # Create layer item widgets (connect signals later after UI is fully initialized)
        for layer_key, layer_config in LAYERS.items():
            layer_widget = LayerItemWidget(layer_config)
            self.layer_widgets.append(layer_widget)
            self.layers_container_layout.addWidget(layer_widget)

        self.layers_container_layout.addStretch()
        scroll_widget.setLayout(self.layers_container_layout)
        scroll_area.setWidget(scroll_widget)

        layer_layout.addWidget(scroll_area)
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

        # Connect layer widget signals after all UI elements are created
        for layer_widget in self.layer_widgets:
            layer_widget.moved_up.connect(lambda w=layer_widget: self._move_layer_up(w))
            layer_widget.moved_down.connect(lambda w=layer_widget: self._move_layer_down(w))
            layer_widget.changed.connect(self._on_layer_changed)

        # Enable first layer by default (after signals are connected)
        if self.layer_widgets:
            self.layer_widgets[0].enabled_checkbox.setChecked(True)

        self._update_zoom_range()

    def _on_layer_changed(self):
        """Handle layer composition change."""
        self._update_zoom_range()
        self._update_estimates()
        self._update_move_buttons()

    def _move_layer_up(self, widget: LayerItemWidget):
        """Move layer up in the composition order."""
        index = self.layer_widgets.index(widget)
        if index > 0:
            # Swap in list
            self.layer_widgets[index], self.layer_widgets[index - 1] = \
                self.layer_widgets[index - 1], self.layer_widgets[index]

            # Swap in layout
            self.layers_container_layout.removeWidget(widget)
            self.layers_container_layout.insertWidget(index - 1, widget)

            self._update_move_buttons()
            self.changed.emit()

    def _move_layer_down(self, widget: LayerItemWidget):
        """Move layer down in the composition order."""
        index = self.layer_widgets.index(widget)
        if index < len(self.layer_widgets) - 1:
            # Swap in list
            self.layer_widgets[index], self.layer_widgets[index + 1] = \
                self.layer_widgets[index + 1], self.layer_widgets[index]

            # Swap in layout
            self.layers_container_layout.removeWidget(widget)
            self.layers_container_layout.insertWidget(index + 1, widget)

            self._update_move_buttons()
            self.changed.emit()

    def _update_move_buttons(self):
        """Update enabled state of move up/down buttons."""
        for i, widget in enumerate(self.layer_widgets):
            widget.up_button.setEnabled(i > 0)
            widget.down_button.setEnabled(i < len(self.layer_widgets) - 1)

    def _on_zoom_changed(self):
        """Handle zoom level change."""
        self._update_estimates()

    def _update_zoom_range(self):
        """Update zoom range based on enabled layers."""
        enabled_layers = self.get_enabled_layers()
        if not enabled_layers:
            self.zoom_range_label.setText("Range: -")
            return

        # Find intersection of zoom ranges
        min_zoom = max(layer.min_zoom for layer in enabled_layers)
        max_zoom = min(layer.max_zoom for layer in enabled_layers)

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

        enabled_layers = self.get_enabled_layers()
        if not enabled_layers:
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

        # Multiply by number of enabled layers
        total_tiles = tile_count * len(enabled_layers)

        # Estimate size (sum across enabled layers)
        total_size_mb = 0
        for layer in enabled_layers:
            size_mb = TileCalculator.estimate_download_size(tile_count, layer.extension)
            total_size_mb += size_mb

        self.tile_count_label.setText(f"Tiles: {total_tiles:,}")
        self.size_estimate_label.setText(f"Size: ~{total_size_mb:.1f} MB")

    def _update_generate_button(self):
        """Update generate button enabled state."""
        has_extent = self.current_extent is not None
        has_output = bool(self.output_path_edit.text())
        has_layers = len(self.get_enabled_layers()) > 0

        self.generate_button.setEnabled(has_extent and has_output and has_layers)

    def _on_generate_clicked(self):
        """Handle generate button click."""
        layer_compositions = self.get_layer_compositions()
        zoom = self.zoom_spinner.value()
        output_path = self.output_path_edit.text()

        self.generate_requested.emit(
            layer_compositions,
            zoom,
            self.current_extent,
            output_path
        )

    def get_enabled_layers(self) -> List[LayerConfig]:
        """
        Get list of enabled layer configurations.

        Returns:
            List of enabled LayerConfig objects
        """
        return [widget.layer_config for widget in self.layer_widgets if widget.is_enabled()]

    def get_layer_compositions(self) -> List[LayerComposition]:
        """
        Get list of enabled layers with their composition settings.

        Returns:
            List of LayerComposition objects
        """
        compositions = []
        for widget in self.layer_widgets:
            if widget.is_enabled():
                compositions.append(LayerComposition(
                    layer_config=widget.layer_config,
                    opacity=widget.get_opacity(),
                    blend_mode=widget.get_blend_mode()
                ))
        return compositions
