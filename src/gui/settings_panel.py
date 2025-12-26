"""Settings panel for the application."""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.config import CATEGORIES, DEFAULT_ZOOM, LAYERS, LayerConfig
from src.gui.output_item_widget import OutputItemWidget
from src.gui.zoom_range_widget import ZoomRangeWidget
from src.models.extent import Extent
from src.models.generation_request import GenerationRequest
from src.models.layer_composition import LayerComposition
from src.models.output_config import OutputConfig

# Blend modes supported by KML (Google Earth)
BLEND_MODES = [
    ("Normal", "normal"),
    ("Multiply", "multiply"),
    ("Screen", "screen"),
    ("Overlay", "overlay"),
]


class LayerItemWidget(QFrame):
    """Widget for a single layer with composition controls."""

    moved_up = pyqtSignal()
    moved_down = pyqtSignal()
    changed = pyqtSignal()
    remove_requested = pyqtSignal()  # Emitted when user clicks remove button

    def __init__(self, composition: LayerComposition, parent=None):
        """Initialize layer item widget.

        Args:
            composition: Layer composition configuration
            parent: Parent widget
        """
        super().__init__(parent)
        self.composition = composition
        self.output_min_zoom = 2  # Will be updated by parent
        self.output_max_zoom = 18
        self.zoom_checkboxes = {}  # Store zoom checkboxes for updates
        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Top row: checkbox, name, info button, remove button
        top_row = QHBoxLayout()

        # Enable/disable checkbox
        self.enabled_checkbox = QCheckBox()
        self.enabled_checkbox.setChecked(self.composition.enabled)
        self.enabled_checkbox.setToolTip("Enable/disable this layer")
        self.enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        top_row.addWidget(self.enabled_checkbox)

        self.name_label = QLabel(f"{self.composition.layer_config.display_name}")
        self.name_label.setStyleSheet("font-weight: bold;")
        top_row.addWidget(self.name_label, 1)

        self.info_button = QPushButton("ℹ️")
        self.info_button.setFixedSize(24, 24)
        self.info_button.setToolTip("Show layer information")
        self.info_button.clicked.connect(self.show_info)
        top_row.addWidget(self.info_button)

        self.remove_button = QPushButton("✕")
        self.remove_button.setFixedSize(24, 24)
        self.remove_button.setToolTip("Remove layer")
        self.remove_button.clicked.connect(self.remove_requested.emit)
        top_row.addWidget(self.remove_button)

        layout.addLayout(top_row)

        # Opacity row
        opacity_layout = QHBoxLayout()
        opacity_layout.setContentsMargins(20, 0, 0, 0)  # Indent controls

        self.opacity_label = QLabel("Opacity:")
        opacity_layout.addWidget(self.opacity_label)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(self.composition.opacity)
        self.opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.opacity_slider.setTickInterval(25)
        self.opacity_slider.valueChanged.connect(self._sync_opacity_spinbox)
        opacity_layout.addWidget(self.opacity_slider, 1)

        self.opacity_spinbox = QSpinBox()
        self.opacity_spinbox.setMinimum(0)
        self.opacity_spinbox.setMaximum(100)
        self.opacity_spinbox.setValue(self.composition.opacity)
        self.opacity_spinbox.setSuffix("%")
        self.opacity_spinbox.setFixedWidth(70)
        self.opacity_spinbox.valueChanged.connect(self._sync_opacity_slider)
        opacity_layout.addWidget(self.opacity_spinbox)

        layout.addLayout(opacity_layout)

        # Blend mode and move buttons row
        blend_layout = QHBoxLayout()
        blend_layout.setContentsMargins(20, 0, 0, 0)  # Indent controls

        self.blend_label = QLabel("Blend:")
        blend_layout.addWidget(self.blend_label)

        self.blend_combo = QComboBox()
        for display_name, value in BLEND_MODES:
            self.blend_combo.addItem(display_name, value)
        # Set initial value from composition
        blend_index = self.blend_combo.findData(self.composition.blend_mode)
        if blend_index >= 0:
            self.blend_combo.setCurrentIndex(blend_index)
        self.blend_combo.currentIndexChanged.connect(self.changed.emit)
        blend_layout.addWidget(self.blend_combo, 1)

        # Up/Down buttons
        self.up_button = QPushButton("↑")
        self.up_button.setFixedSize(24, 24)
        self.up_button.setToolTip("Move layer up")
        self.up_button.clicked.connect(self.moved_up.emit)
        blend_layout.addWidget(self.up_button)

        self.down_button = QPushButton("↓")
        self.down_button.setFixedSize(24, 24)
        self.down_button.setToolTip("Move layer down")
        self.down_button.clicked.connect(self.moved_down.emit)
        blend_layout.addWidget(self.down_button)

        layout.addLayout(blend_layout)

        # Export mode dropdown
        export_layout = QHBoxLayout()
        export_layout.setContentsMargins(20, 0, 0, 0)  # Indent

        self.export_label = QLabel("Export:")
        export_layout.addWidget(self.export_label)

        self.export_combo = QComboBox()
        self.export_combo.addItem("Composite with others", "composite")
        self.export_combo.addItem("Export separately", "separate")
        # Set initial value from composition
        export_index = self.export_combo.findData(self.composition.export_mode)
        if export_index >= 0:
            self.export_combo.setCurrentIndex(export_index)
        self.export_combo.currentIndexChanged.connect(self._on_export_mode_changed)
        export_layout.addWidget(self.export_combo, 1)

        layout.addLayout(export_layout)

        # LOD mode dropdown
        lod_layout = QHBoxLayout()
        lod_layout.setContentsMargins(20, 0, 0, 0)  # Indent

        self.lod_label = QLabel("LOD:")
        lod_layout.addWidget(self.lod_label)

        self.lod_combo = QComboBox()
        self.lod_combo.addItems(["Use All Zooms", "Select Zooms"])
        # Set initial value from composition
        if self.composition.lod_mode == "all_zooms":
            self.lod_combo.setCurrentIndex(0)
        else:
            self.lod_combo.setCurrentIndex(1)
        self.lod_combo.currentIndexChanged.connect(self._on_lod_mode_changed)
        lod_layout.addWidget(self.lod_combo, 1)

        layout.addLayout(lod_layout)

        # Zoom selection checkboxes (hidden by default)
        self.zoom_selection_container = QWidget()
        zoom_selection_layout = QVBoxLayout(self.zoom_selection_container)
        zoom_selection_layout.setContentsMargins(20, 0, 0, 0)  # Indent

        zoom_label = QLabel("Select zoom levels:")
        zoom_selection_layout.addWidget(zoom_label)

        self.zoom_checkboxes_widget = QWidget()
        from PyQt6.QtWidgets import QGridLayout

        self.zoom_checkboxes_layout = QGridLayout(self.zoom_checkboxes_widget)
        self.zoom_checkboxes_layout.setSpacing(5)
        zoom_selection_layout.addWidget(self.zoom_checkboxes_widget)

        self.zoom_selection_container.setVisible(self.composition.lod_mode == "select_zooms")
        layout.addWidget(self.zoom_selection_container)

        # Build initial zoom checkboxes
        self._update_zoom_checkboxes()

        self.setLayout(layout)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setStyleSheet("LayerItemWidget { border: 1px solid #ccc; border-radius: 4px; }")

        # Set initial enabled state
        self._update_enabled_state()

    def _sync_opacity_spinbox(self, value: int):
        """Sync spinbox when slider changes."""
        self.opacity_spinbox.blockSignals(True)
        self.opacity_spinbox.setValue(value)
        self.opacity_spinbox.blockSignals(False)
        self.composition.opacity = value
        self.changed.emit()

    def _sync_opacity_slider(self, value: int):
        """Sync slider when spinbox changes."""
        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(value)
        self.opacity_slider.blockSignals(False)
        self.composition.opacity = value
        self.changed.emit()

    def _on_lod_mode_changed(self, index):
        """Handle LOD mode dropdown change."""
        if index == 0:  # Use All Zooms
            self.composition.lod_mode = "all_zooms"
            self.zoom_selection_container.setVisible(False)
        else:  # Select Zooms
            self.composition.lod_mode = "select_zooms"
            self.zoom_selection_container.setVisible(True)
            self._update_zoom_checkboxes()

        self.changed.emit()

    def _on_export_mode_changed(self, index):
        """Handle export mode dropdown change."""
        self.composition.export_mode = self.export_combo.currentData()
        self.changed.emit()

    def _on_enabled_changed(self, state):
        """Handle enabled checkbox state change."""
        # Use isChecked() to reliably get the checkbox state
        self.composition.enabled = self.enabled_checkbox.isChecked()
        self._update_enabled_state()
        self.changed.emit()

    def _update_enabled_state(self):
        """Update widget appearance and control states based on enabled status."""
        enabled = self.composition.enabled

        # Enable/disable all controls except the checkbox itself
        # Qt will automatically grey out disabled controls
        self.name_label.setEnabled(enabled)
        self.info_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
        self.opacity_label.setEnabled(enabled)
        self.opacity_slider.setEnabled(enabled)
        self.opacity_spinbox.setEnabled(enabled)
        self.blend_label.setEnabled(enabled)
        self.blend_combo.setEnabled(enabled)
        self.export_label.setEnabled(enabled)
        self.export_combo.setEnabled(enabled)
        self.up_button.setEnabled(enabled)
        self.down_button.setEnabled(enabled)
        self.lod_label.setEnabled(enabled)
        self.lod_combo.setEnabled(enabled)
        self.zoom_selection_container.setEnabled(enabled)

        # Checkbox always stays enabled so user can re-enable the layer
        self.enabled_checkbox.setEnabled(True)

    def _update_multi_layer_controls(self, total_enabled_layers: int):
        """
        Enable/disable blend mode and export mode based on layer count.

        When only one layer is enabled, disable blend and export controls since
        a single layer is always treated as separate with KML-level opacity.

        Args:
            total_enabled_layers: Total number of enabled layers in the composition
        """
        # When only one layer is enabled, disable blend and export controls
        # (single layer is always treated as separate with KML-level opacity)
        multi_layer_mode = total_enabled_layers > 1

        self.blend_label.setEnabled(multi_layer_mode and self.composition.enabled)
        self.blend_combo.setEnabled(multi_layer_mode and self.composition.enabled)
        self.export_label.setEnabled(multi_layer_mode and self.composition.enabled)
        self.export_combo.setEnabled(multi_layer_mode and self.composition.enabled)

    def set_output_zoom_range(self, min_zoom: int, max_zoom: int):
        """Update available zoom range from main settings.

        Args:
            min_zoom: Minimum zoom level in output range
            max_zoom: Maximum zoom level in output range
        """
        self.output_min_zoom = min_zoom
        self.output_max_zoom = max_zoom

        if self.composition.lod_mode == "select_zooms":
            self._update_zoom_checkboxes()

    def _update_zoom_checkboxes(self):
        """Rebuild zoom level checkboxes based on output range."""
        # Clear existing checkboxes
        while self.zoom_checkboxes_layout.count():
            item = self.zoom_checkboxes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.zoom_checkboxes = {}

        # Create checkboxes for each zoom in output range
        row = 0
        col = 0
        max_cols = 6

        for zoom in range(self.output_min_zoom, self.output_max_zoom + 1):
            checkbox = QCheckBox(str(zoom))

            # Disable if outside layer's capability
            if zoom < self.composition.layer_config.min_zoom or zoom > self.composition.layer_config.max_zoom:
                checkbox.setEnabled(False)
                checkbox.setToolTip(
                    f"Layer only supports zoom {self.composition.layer_config.min_zoom}-{self.composition.layer_config.max_zoom}"
                )
            else:
                checkbox.setChecked(zoom in self.composition.selected_zooms)
                checkbox.stateChanged.connect(lambda state, z=zoom: self._on_zoom_checkbox_changed(z, state))

            self.zoom_checkboxes[zoom] = checkbox
            self.zoom_checkboxes_layout.addWidget(checkbox, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _on_zoom_checkbox_changed(self, zoom: int, state):
        """Handle zoom checkbox state change.

        Args:
            zoom: Zoom level
            state: Checkbox state (Qt.CheckState value)
        """
        if state == Qt.CheckState.Checked.value:
            self.composition.selected_zooms.add(zoom)
        else:
            self.composition.selected_zooms.discard(zoom)

        self.changed.emit()

    def show_info(self):
        """Show information dialog for this layer."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle(f"Layer Information - {self.composition.layer_config.display_name}")
        dialog.setTextFormat(Qt.TextFormat.RichText)

        info_text = f"""
        <h3>{self.composition.layer_config.display_name}</h3>
        <p><b>Japanese Name:</b> {self.composition.layer_config.japanese_name}</p>
        <p><b>Format:</b> {self.composition.layer_config.extension.upper()}</p>
        <p><b>Zoom Range:</b> {self.composition.layer_config.min_zoom} - {self.composition.layer_config.max_zoom}</p>
        <br>
        <p>{self.composition.layer_config.full_description}</p>
        <br>
        <p><b>More information:</b><br>
        <a href="{self.composition.layer_config.info_url}">{self.composition.layer_config.info_url}</a></p>
        """

        dialog.setText(info_text)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.exec()

    def get_composition(self) -> LayerComposition:
        """Get the layer composition with current settings.

        Returns:
            LayerComposition with current UI values
        """
        # Update composition with current UI values
        self.composition.opacity = self.opacity_spinbox.value()
        self.composition.blend_mode = self.blend_combo.currentData()
        self.composition.export_mode = self.export_combo.currentData()
        return self.composition


class LayerListItemWidget(QWidget):
    """Custom widget for layer items in the selection dialog."""

    def __init__(self, layer_config: LayerConfig, preview_path: Path, parent=None):
        """Initialize layer list item widget.

        Args:
            layer_config: Layer configuration
            preview_path: Path to preview image
            parent: Parent widget
        """
        super().__init__(parent)
        self.layer_config = layer_config

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Preview image
        preview_label = QLabel()
        if preview_path.exists():
            pixmap = QPixmap(str(preview_path))
            scaled_pixmap = pixmap.scaled(
                80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            preview_label.setPixmap(scaled_pixmap)
        preview_label.setFixedSize(80, 80)
        layout.addWidget(preview_label)

        # Layer name
        name_label = QLabel(f"{layer_config.display_name}\n{layer_config.japanese_name}")
        name_label.setWordWrap(True)
        layout.addWidget(name_label, 1)

        # Info button
        info_button = QPushButton("ℹ️")
        info_button.setFixedSize(30, 30)
        info_button.setToolTip("Show layer information")
        info_button.clicked.connect(self.show_info)
        layout.addWidget(info_button)

        self.setLayout(layout)

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


class AddLayerDialog(QDialog):
    """Dialog for selecting a layer to add."""

    def __init__(self, available_layers: list[LayerConfig], parent=None):
        """
        Initialize the add layer dialog.

        Args:
            available_layers: List of layer configs that can be added
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Add Layer")
        self.selected_layer: LayerConfig | None = None
        self.all_available_layers = available_layers

        # Get preview images directory
        self.preview_dir = Path(__file__).parent.parent.parent / "resources" / "previews"

        layout = QVBoxLayout()

        # Instructions
        label = QLabel("Select a layer to add:")
        layout.addWidget(label)

        # Category filter
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Category:")
        filter_layout.addWidget(filter_label)

        self.category_combo = QComboBox()
        self.category_combo.addItem("All Categories", "all")
        for cat_id, category in sorted(CATEGORIES.items(), key=lambda x: x[1].name_en):
            self.category_combo.addItem(f"{category.name_en} ({category.name_ja})", cat_id)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        filter_layout.addWidget(self.category_combo, 1)

        layout.addLayout(filter_layout)

        # List of available layers
        self.layer_list = QListWidget()
        self.layer_list.setSpacing(5)

        # Populate with all layers initially
        self._populate_layer_list(available_layers)

        self.layer_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.layer_list)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self.resize(500, 500)  # Larger size to accommodate preview images

    def _populate_layer_list(self, layers: list[LayerConfig]):
        """Populate the layer list with given layers."""
        self.layer_list.clear()

        for layer_config in layers:
            # Create list item
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, layer_config)

            # Load preview image path
            preview_path = self.preview_dir / f"{layer_config.name}.{layer_config.extension}"

            # Create custom widget for this item
            item_widget = LayerListItemWidget(layer_config, preview_path)
            item.setSizeHint(item_widget.sizeHint())

            self.layer_list.addItem(item)
            self.layer_list.setItemWidget(item, item_widget)

    def _on_category_changed(self, index: int):
        """Handle category filter change."""
        category_id = self.category_combo.currentData()

        if category_id == "all":
            # Show all layers
            filtered_layers = self.all_available_layers
        else:
            # Filter by category
            filtered_layers = [layer for layer in self.all_available_layers if layer.category == category_id]

        self._populate_layer_list(filtered_layers)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on item - accept dialog."""
        self.accept()

    def accept(self):
        """Accept dialog and store selected layer."""
        current_item = self.layer_list.currentItem()
        if current_item:
            self.selected_layer = current_item.data(Qt.ItemDataRole.UserRole)
            super().accept()

    def get_selected_layer(self) -> LayerConfig | None:
        """Get the selected layer config."""
        return self.selected_layer


class SettingsPanel(QWidget):
    """Panel for configuring download settings."""

    generate_requested = pyqtSignal(object)  # GenerationRequest
    changed = pyqtSignal()  # Emitted when layer list changes (add/remove/reorder) - updates zoom limits
    settings_changed_no_zoom = pyqtSignal()  # Emitted when layer settings change (opacity/blend) - no zoom update
    sync_preview_zoom_requested = pyqtSignal(int)  # Emitted when user wants to sync preview zoom to output zoom
    state_changed = pyqtSignal()  # Emitted when ANY state changes (for dirty tracking)
    extent_loaded = pyqtSignal(object)  # Emitted when extent is loaded from file (for setting on map)

    def __init__(self):
        """Initialize settings panel."""
        super().__init__()
        self.current_extent: Extent | None = None
        self.layer_widgets: list[LayerItemWidget] = []
        self.output_widgets: list[OutputItemWidget] = []
        self.current_preview_zoom: int | None = None
        self._suppress_state_changes = False
        self.custom_layer_registry: dict = {}  # Custom layers from layer_sources in config
        self.current_name: str = ""
        self.current_description: str = ""
        self.current_attribution: str = ""
        self.init_ui()

    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout()

        # Layer composition
        layer_group = QGroupBox("Layer Composition")
        layer_layout = QVBoxLayout()

        # Add Layer button
        add_layer_button = QPushButton("Add Layer")
        add_layer_button.clicked.connect(self._on_add_layer_clicked)
        layer_layout.addWidget(add_layer_button)

        # Container for layer widgets (no scroll area - entire panel will scroll)
        self.layers_container_layout = QVBoxLayout()
        self.layers_container_layout.setSpacing(5)
        layer_layout.addLayout(self.layers_container_layout)

        layer_group.setLayout(layer_layout)
        layout.addWidget(layer_group)

        # Metadata (applies to all outputs)
        metadata_group = QGroupBox("Metadata (applies to all outputs)")
        metadata_layout = QVBoxLayout()

        # Name field
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Tile Export")
        self.name_edit.textChanged.connect(self._on_metadata_changed)
        name_layout.addWidget(self.name_edit, 1)
        metadata_layout.addLayout(name_layout)

        # Description field
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Optional description...")
        self.description_edit.textChanged.connect(self._on_metadata_changed)
        desc_layout.addWidget(self.description_edit, 1)
        metadata_layout.addLayout(desc_layout)

        # Attribution field (multiline)
        attr_label = QLabel("Attribution:")
        metadata_layout.addWidget(attr_label)
        self.attribution_edit = QPlainTextEdit()
        self.attribution_edit.setPlaceholderText("Leave empty for auto-generated attribution from layer sources...")
        self.attribution_edit.setMaximumHeight(80)  # ~3 lines
        self.attribution_edit.textChanged.connect(self._on_metadata_changed)
        metadata_layout.addWidget(self.attribution_edit)

        # Info label
        info_label = QLabel("This metadata will be included in all output formats (MBTiles metadata, KMZ description)")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 10px;")
        metadata_layout.addWidget(info_label)

        metadata_group.setLayout(metadata_layout)
        layout.addWidget(metadata_group)

        # Zoom level
        zoom_group = QGroupBox("Zoom Range")
        zoom_layout = QVBoxLayout()

        # Zoom range widget
        self.zoom_range_widget = ZoomRangeWidget()
        self.zoom_range_widget.set_range(2, 18)  # Will be updated when layers change
        self.zoom_range_widget.set_value(DEFAULT_ZOOM, DEFAULT_ZOOM)  # Start with single zoom
        self.zoom_range_widget.valueChanged.connect(self._on_zoom_range_changed)
        zoom_layout.addWidget(self.zoom_range_widget)

        # Zoom display label
        self.zoom_display_label = QLabel(f"Zoom: {DEFAULT_ZOOM}")
        self.zoom_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zoom_layout.addWidget(self.zoom_display_label)

        # Additional info layout
        info_layout = QFormLayout()

        # Zoom range info
        self.zoom_range_label = QLabel("Range: 2-18")
        info_layout.addRow("Valid Range:", self.zoom_range_label)

        # Preview zoom display
        preview_zoom_row = QHBoxLayout()
        self.preview_zoom_label = QLabel("-")
        preview_zoom_row.addWidget(self.preview_zoom_label)

        self.sync_zoom_button = QPushButton("↻ Sync to Max Zoom")
        self.sync_zoom_button.setVisible(False)
        self.sync_zoom_button.setToolTip("Set preview zoom to match maximum output zoom")
        self.sync_zoom_button.clicked.connect(self._on_sync_zoom_clicked)
        preview_zoom_row.addWidget(self.sync_zoom_button)
        preview_zoom_row.addStretch()

        info_layout.addRow("Preview Zoom:", preview_zoom_row)

        zoom_layout.addLayout(info_layout)

        zoom_group.setLayout(zoom_layout)
        layout.addWidget(zoom_group)

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

        # Output section (supports multiple outputs)
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout()

        # Add Output button
        self.add_output_button = QPushButton("Add Output")
        self.add_output_button.clicked.connect(self._on_add_output_clicked)
        output_layout.addWidget(self.add_output_button)

        # Container for output widgets
        self.outputs_container = QWidget()
        self.outputs_layout = QVBoxLayout()
        self.outputs_layout.setContentsMargins(0, 0, 0, 0)
        self.outputs_container.setLayout(self.outputs_layout)
        output_layout.addWidget(self.outputs_container)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # Export button (renamed from Generate KMZ)
        self.generate_button = QPushButton("Export")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self._on_generate_clicked)
        self.generate_button.setMinimumHeight(40)

        layout.addWidget(self.generate_button)

        # Wrap entire panel in scroll area
        content_widget = QWidget()
        content_widget.setLayout(layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(content_widget)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)

        self.setLayout(main_layout)

        # Start with standard layer by default
        self.add_layer(LAYERS["std"])
        self._update_zoom_range()

        # Start with one empty output pre-added
        default_output = OutputConfig(
            output_type="kmz",
            output_path=Path(""),
            options={"web_compatible": False}
        )
        self._add_output_widget(default_output)

    def _on_layer_changed(self):
        """Handle layer list change (add/remove/reorder) - updates zoom limits and attribution placeholder."""
        self._update_zoom_range()
        self._update_attribution_placeholder()
        self.changed.emit()  # Trigger map preview update WITH zoom limit update
        self._update_estimates()
        self._update_move_buttons()
        self._emit_state_changed()

    def _on_layer_settings_changed(self):
        """Handle layer settings change (opacity/blend/enabled) - no zoom limit update needed."""
        self._update_estimates()
        self._update_all_layer_multi_mode()  # Update blend/export controls based on enabled layer count
        self.settings_changed_no_zoom.emit()

    def _on_metadata_changed(self):
        """Handle metadata field changes (name, description, attribution)."""
        self.current_name = self.name_edit.text().strip()
        self.current_description = self.description_edit.text().strip()
        self.current_attribution = self.attribution_edit.toPlainText().strip()
        self._emit_state_changed()

    def _update_attribution_placeholder(self):
        """Update attribution placeholder with auto-calculated value from layers."""
        layer_compositions = self.get_layer_compositions()
        if not layer_compositions:
            self.attribution_edit.setPlaceholderText(
                "Leave empty for auto-generated attribution from layer sources..."
            )
            return

        from src.utils.attribution import build_attribution_from_layers
        auto_attribution = build_attribution_from_layers(layer_compositions)

        if auto_attribution:
            self.attribution_edit.setPlaceholderText(f"Leave empty to use: {auto_attribution}")
        else:
            self.attribution_edit.setPlaceholderText(
                "Leave empty for auto-generated attribution from layer sources..."
            )

    def _move_layer_up(self, widget: LayerItemWidget):
        """Move layer up in the composition order."""
        index = self.layer_widgets.index(widget)
        if index > 0:
            # Swap in list
            self.layer_widgets[index], self.layer_widgets[index - 1] = (
                self.layer_widgets[index - 1],
                self.layer_widgets[index],
            )

            # Swap in layout
            self.layers_container_layout.removeWidget(widget)
            self.layers_container_layout.insertWidget(index - 1, widget)

            self._update_move_buttons()
            self.changed.emit()
            self._emit_state_changed()

    def _move_layer_down(self, widget: LayerItemWidget):
        """Move layer down in the composition order."""
        index = self.layer_widgets.index(widget)
        if index < len(self.layer_widgets) - 1:
            # Swap in list
            self.layer_widgets[index], self.layer_widgets[index + 1] = (
                self.layer_widgets[index + 1],
                self.layer_widgets[index],
            )

            # Swap in layout
            self.layers_container_layout.removeWidget(widget)
            self.layers_container_layout.insertWidget(index + 1, widget)

            self._update_move_buttons()
            self.changed.emit()
            self._emit_state_changed()

    def _update_move_buttons(self):
        """Update enabled state of move up/down buttons."""
        for i, widget in enumerate(self.layer_widgets):
            widget.up_button.setEnabled(i > 0)
            widget.down_button.setEnabled(i < len(self.layer_widgets) - 1)

    def _update_all_layer_multi_mode(self):
        """
        Update multi-layer controls for all layer widgets.

        Counts enabled layers and updates blend/export mode controls accordingly.
        When only one layer is enabled, blend and export modes are disabled.
        """
        # Count enabled layers
        enabled_count = 0
        for widget in self.layer_widgets:
            if widget.composition.enabled:
                enabled_count += 1

        # Update all widgets
        for widget in self.layer_widgets:
            widget._update_multi_layer_controls(enabled_count)

    def _on_add_layer_clicked(self):
        """Handle Add Layer button click."""
        # Merge default LAYERS with custom layers
        merged_registry = LAYERS.copy()
        merged_registry.update(self.custom_layer_registry)

        # Get list of layers not currently added
        added_layer_names = {w.composition.layer_config.name for w in self.layer_widgets}
        available_layers = [config for name, config in merged_registry.items() if name not in added_layer_names]

        if not available_layers:
            QMessageBox.information(self, "No Layers Available", "All available layers have already been added.")
            return

        # Show dialog to select layer
        dialog = AddLayerDialog(available_layers, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_layer = dialog.get_selected_layer()
            if selected_layer:
                self.add_layer(selected_layer)

    def add_layer(self, layer_config: LayerConfig):
        """
        Add a new layer to the composition.

        Args:
            layer_config: Layer configuration to add
        """
        # Create layer composition with default settings
        composition = LayerComposition(
            layer_config=layer_config,
            opacity=100,
            blend_mode="normal",
            export_mode="composite",
            lod_mode="all_zooms",
            selected_zooms=set(),
            enabled=True,
        )

        # Create layer widget
        layer_widget = LayerItemWidget(composition)

        # Set current zoom range
        min_zoom, max_zoom = self.zoom_range_widget.value()
        layer_widget.set_output_zoom_range(min_zoom, max_zoom)

        # Connect signals
        layer_widget.moved_up.connect(lambda w=layer_widget: self._move_layer_up(w))
        layer_widget.moved_down.connect(lambda w=layer_widget: self._move_layer_down(w))
        layer_widget.changed.connect(self._on_layer_settings_changed)
        layer_widget.changed.connect(self._emit_state_changed)
        layer_widget.remove_requested.connect(lambda w=layer_widget: self.remove_layer(w))

        # Add to list and layout at the top (position 0)
        self.layer_widgets.insert(0, layer_widget)
        self.layers_container_layout.insertWidget(0, layer_widget)

        # Update UI state
        self._update_move_buttons()
        self._update_all_layer_multi_mode()
        self._on_layer_changed()
        self.changed.emit()

    def remove_layer(self, layer_widget: LayerItemWidget):
        """
        Remove a layer from the composition.

        Args:
            layer_widget: Layer widget to remove
        """
        # Remove from layout and list
        self.layers_container_layout.removeWidget(layer_widget)
        self.layer_widgets.remove(layer_widget)

        # Delete widget
        layer_widget.deleteLater()

        # Update UI state
        self._update_move_buttons()
        self._update_all_layer_multi_mode()
        self._on_layer_changed()
        self.changed.emit()

    def _on_zoom_range_changed(self, value):
        """Handle zoom range slider change."""
        # Don't modify values during config loading
        if self._suppress_state_changes:
            return

        min_zoom, max_zoom = value

        # Update display label
        if min_zoom == max_zoom:
            self.zoom_display_label.setText(f"Zoom: {max_zoom}")
        else:
            self.zoom_display_label.setText(f"Zoom: {min_zoom}-{max_zoom} ({max_zoom - min_zoom + 1} levels)")

        # Update all layer widgets with new zoom range
        for widget in self.layer_widgets:
            widget.set_output_zoom_range(min_zoom, max_zoom)

        self._update_estimates()
        self._update_sync_button_visibility()
        self._emit_state_changed()

    def update_preview_zoom(self, zoom: int):
        """
        Update the displayed preview zoom level.

        Args:
            zoom: Current preview zoom level
        """
        self.current_preview_zoom = zoom
        self.preview_zoom_label.setText(str(zoom))
        self._update_sync_button_visibility()

    def _update_sync_button_visibility(self):
        """Show/hide sync button based on whether preview zoom differs from max zoom."""
        if self.current_preview_zoom is None:
            self.sync_zoom_button.setVisible(False)
        else:
            _, max_zoom = self.zoom_range_widget.value()
            self.sync_zoom_button.setVisible(self.current_preview_zoom != max_zoom)

    def _on_sync_zoom_clicked(self):
        """Handle sync zoom button click."""
        _, max_zoom = self.zoom_range_widget.value()
        self.sync_preview_zoom_requested.emit(max_zoom)

    # Note: Web compatible mode is now handled per-output in OutputItemWidget

    def _update_zoom_range(self):
        """Update zoom range based on enabled layers."""
        enabled_layers = self.get_enabled_layers()
        if not enabled_layers:
            self.zoom_range_label.setText("-")
            return

        # Find union of zoom ranges (allow resampling to any zoom level)
        # Minimum: Always 2 (absolute minimum, allows maximum downsampling)
        # Maximum: The highest max_zoom from any enabled layer
        layer_min_zoom = 2
        layer_max_zoom = max(layer.max_zoom for layer in enabled_layers)

        if layer_min_zoom > layer_max_zoom:
            self.zoom_range_label.setText("<font color='red'>No compatible zoom range!</font>")
            self.zoom_range_widget.setEnabled(False)
        else:
            self.zoom_range_label.setText(f"{layer_min_zoom}-{layer_max_zoom}")

            # Update widget range (this will clamp current selection)
            self.zoom_range_widget.set_range(layer_min_zoom, layer_max_zoom)
            self.zoom_range_widget.setEnabled(True)

    def _on_add_output_clicked(self):
        """Add new output widget."""
        default_output = OutputConfig(
            output_type="kmz",
            output_path=Path(""),
            options={"web_compatible": False}
        )
        self._add_output_widget(default_output)
        self._emit_state_changed()

    def _add_output_widget(self, output_config: OutputConfig):
        """Add an output widget to the UI.

        Args:
            output_config: Output configuration
        """
        widget = OutputItemWidget(output_config, self)
        widget.changed.connect(self._on_output_changed)
        widget.remove_requested.connect(lambda: self._remove_output(widget))

        # Add to layout and list
        self.outputs_layout.addWidget(widget)
        self.output_widgets.append(widget)

        # Update estimates with current state
        if self.current_extent:
            min_zoom, max_zoom = self.zoom_range_widget.value()
            layer_compositions = self.get_layer_compositions()
            widget.update_estimates(self.current_extent, min_zoom, max_zoom, layer_compositions)

        # Update export button state
        self._update_generate_button()

    def _remove_output(self, widget: OutputItemWidget):
        """Remove output widget.

        Args:
            widget: Output widget to remove
        """
        # Remove from layout
        self.outputs_layout.removeWidget(widget)

        # Remove from list
        self.output_widgets.remove(widget)

        # Delete widget
        widget.deleteLater()

        # Update export button state
        self._update_generate_button()

        # Emit state changed
        self._emit_state_changed()

    def _on_output_changed(self):
        """Handle output settings change."""
        self._update_generate_button()
        self._emit_state_changed()

    def _update_output_estimates(self):
        """Update estimates for all output widgets."""
        if not self.current_extent:
            return

        min_zoom, max_zoom = self.zoom_range_widget.value()
        layer_compositions = self.get_layer_compositions()

        for widget in self.output_widgets:
            widget.update_estimates(self.current_extent, min_zoom, max_zoom, layer_compositions)

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

        # Only emit if not during load
        if not self._suppress_state_changes:
            self.state_changed.emit()

    def _emit_state_changed(self):
        """Emit state_changed signal if not suppressed."""
        if not self._suppress_state_changes:
            self.state_changed.emit()

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
        """Update tile count and size estimates for all outputs."""
        # Estimates are now per-output, update all output widgets
        self._update_output_estimates()

    def _update_generate_button(self):
        """Update generate button enabled state."""
        has_extent = self.current_extent is not None
        has_outputs = len(self.output_widgets) > 0
        has_layers = len(self.get_enabled_layers()) > 0

        self.generate_button.setEnabled(has_extent and has_outputs and has_layers)

    def _on_generate_clicked(self):
        """Handle generate button click."""
        # Validate extent is set (button should be disabled if not, but check anyway)
        if self.current_extent is None:
            return

        layer_compositions = self.get_layer_compositions()
        min_zoom, max_zoom = self.zoom_range_widget.value()

        # Collect outputs from all output widgets
        outputs = [widget.get_config() for widget in self.output_widgets]

        # Validate that all outputs have paths specified
        empty_outputs = []
        for idx, output in enumerate(outputs, 1):
            if str(output.output_path) in ("", "."):
                empty_outputs.append(idx)

        if empty_outputs:
            if len(empty_outputs) == 1:
                message = f"Output {empty_outputs[0]} has no path specified. Please select an output file path."
            else:
                outputs_list = ", ".join(str(i) for i in empty_outputs)
                message = f"Outputs {outputs_list} have no paths specified. Please select output file paths."

            QMessageBox.warning(self, "Missing Output Paths", message)
            return

        # Create generation request
        request = GenerationRequest(
            layer_compositions=layer_compositions,
            min_zoom=min_zoom,
            max_zoom=max_zoom,
            extent=self.current_extent,
            outputs=outputs,
            name=self.current_name if self.current_name else None,
            description=self.current_description if self.current_description else None,
            attribution=self.current_attribution if self.current_attribution else None,
        )

        self.generate_requested.emit(request)

    def get_enabled_layers(self) -> list[LayerConfig]:
        """
        Get list of added layer configurations.

        Returns:
            List of LayerConfig objects
        """
        return [widget.composition.layer_config for widget in self.layer_widgets]

    def get_layer_compositions(self) -> list[LayerComposition]:
        """
        Get list of added layers with their composition settings.

        Returns:
            List of LayerComposition objects (in bottom-to-top order for compositing)
        """
        # Reverse order: top layer in UI should be composited last (on top)
        return [widget.get_composition() for widget in reversed(self.layer_widgets)]

    def get_state_dict(self):
        """
        Get complete UI state as dictionary (for YAML serialization).

        Returns:
            Dictionary with extent, min_zoom, max_zoom, outputs, and layers keys

        Raises:
            ValueError: If extent is not set
        """
        if self.current_extent is None:
            raise ValueError("Cannot save: No extent selected")

        # Get layers in compositing order (same as used for rendering)
        # This is bottom-to-top, which is what the CLI expects
        layer_compositions = self.get_layer_compositions()
        min_zoom, max_zoom = self.zoom_range_widget.value()

        # Collect outputs from all output widgets
        outputs = [widget.get_config().to_dict() for widget in self.output_widgets]

        state = {
            "extent": self.current_extent.to_dict(),
            "min_zoom": min_zoom,
            "max_zoom": max_zoom,
            "name": self.current_name if self.current_name else None,
            "description": self.current_description if self.current_description else None,
            "attribution": self.current_attribution if self.current_attribution else None,
            "outputs": outputs,
            "layers": [comp.to_dict() for comp in layer_compositions],
        }

        # Include layer_sources if we have custom layers
        if self.custom_layer_registry:
            from src.core.config import LAYERS

            layer_sources = {}
            for name, config in self.custom_layer_registry.items():
                # Only save custom layers that aren't in default LAYERS
                if name not in LAYERS:
                    layer_sources[name] = {
                        "url_template": config.custom_url_template,
                        "extension": config.extension,
                        "min_zoom": config.min_zoom,
                        "max_zoom": config.max_zoom,
                        "display_name": config.display_name,
                        "description": config.description,
                        "japanese_name": config.japanese_name,
                        "full_description": config.full_description,
                        "info_url": config.info_url,
                        "category": config.category,
                    }
            if layer_sources:
                state["layer_sources"] = layer_sources

        return state

    def load_state_dict(self, state: dict) -> None:
        """
        Load complete UI state from dictionary (loaded from YAML).

        Args:
            state: Dictionary with extent, min_zoom, max_zoom, output, and layers keys

        Raises:
            ValueError: If state is invalid
        """
        from src.cli import validate_config
        from src.core.config import build_layer_registry

        # Build layer registry (includes default LAYERS + custom layer_sources)
        layer_registry = build_layer_registry(state)

        # Store custom layers for use in Add Layer dialog
        from src.core.config import LAYERS

        self.custom_layer_registry = {
            name: config for name, config in layer_registry.items() if name not in LAYERS
        }

        validate_config(state, layer_registry)

        # Suppress state changes during load
        self._suppress_state_changes = True

        try:
            # 1. Clear existing layers
            self._clear_all_layers()

            # 2. Load layers (YAML has compositing order, reverse for UI display)
            for layer_spec in reversed(state["layers"]):
                comp = LayerComposition.from_dict(layer_spec, layer_registry)
                self._add_layer_with_composition(comp)

            # 3. Set zoom range
            min_zoom = state["min_zoom"]
            max_zoom = state["max_zoom"]
            self.zoom_range_widget.set_value(min_zoom, max_zoom)

            # 4. Clear existing outputs
            for widget in list(self.output_widgets):
                self.outputs_layout.removeWidget(widget)
                widget.deleteLater()
            self.output_widgets.clear()

            # 5. Load outputs
            for output_dict in state["outputs"]:
                output_config = OutputConfig.from_dict(output_dict)
                self._add_output_widget(output_config)

            # 6. Set extent
            extent = Extent.from_dict(state["extent"])
            self.current_extent = extent
            self.north_edit.setText(f"{extent.max_lat:.6f}")
            self.south_edit.setText(f"{extent.min_lat:.6f}")
            self.east_edit.setText(f"{extent.max_lon:.6f}")
            self.west_edit.setText(f"{extent.min_lon:.6f}")

            # 7. Load metadata (name, description, attribution)
            name = state.get("name", "")
            self.current_name = name
            self.name_edit.setText(name)

            description = state.get("description", "")
            self.current_description = description
            self.description_edit.setText(description)

            attribution = state.get("attribution", "")
            self.current_attribution = attribution
            self.attribution_edit.setPlainText(attribution)

        finally:
            self._suppress_state_changes = False

            # Trigger updates
            self._update_zoom_range()
            self._update_estimates()
            self._update_generate_button()
            self.changed.emit()  # Update map preview

            # Emit signal to set extent on map
            self.extent_loaded.emit(extent)

    def _clear_all_layers(self) -> None:
        """Clear all layers from the composition."""
        for widget in list(self.layer_widgets):
            self.layers_container_layout.removeWidget(widget)
            widget.deleteLater()
        self.layer_widgets.clear()

    def _add_layer_with_composition(self, composition: LayerComposition) -> None:
        """
        Add a layer with a full composition (for loading saved state).

        Args:
            composition: Layer composition with all settings including LOD
        """
        # Create layer widget with composition
        layer_widget = LayerItemWidget(composition)

        # Set current zoom range
        min_zoom, max_zoom = self.zoom_range_widget.value()
        layer_widget.set_output_zoom_range(min_zoom, max_zoom)

        # Connect signals
        layer_widget.moved_up.connect(lambda w=layer_widget: self._move_layer_up(w))
        layer_widget.moved_down.connect(lambda w=layer_widget: self._move_layer_down(w))
        layer_widget.changed.connect(self._on_layer_settings_changed)
        layer_widget.changed.connect(self._emit_state_changed)
        layer_widget.remove_requested.connect(lambda w=layer_widget: self.remove_layer(w))

        self.layer_widgets.append(layer_widget)
        self.layers_container_layout.insertWidget(len(self.layer_widgets) - 1, layer_widget)

        self._update_move_buttons()
