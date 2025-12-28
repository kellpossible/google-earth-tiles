"""Widget for configuring a single output."""

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from src.gui.output_options import get_options_widget
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition
from src.models.outputs import GeoTIFFOutput, KMZOutput, MBTilesOutput, OutputUnion
from src.outputs import get_output_handler

if TYPE_CHECKING:
    from src.gui.output_options.geotiff_options_widget import GeoTIFFOptionsWidget
    from src.gui.output_options.kmz_options_widget import KMZOptionsWidget
    from src.gui.output_options.mbtiles_options_widget import MBTilesOptionsWidget


class OutputItemWidget(QFrame):
    """Widget for a single output configuration."""

    changed = pyqtSignal()  # Settings changed
    remove_requested = pyqtSignal()  # User wants to remove

    def __init__(self, output_config: OutputUnion, parent=None):
        """Initialize output item widget.

        Args:
            output_config: Output configuration (KMZ, MBTiles, or GeoTIFF)
            parent: Parent widget
        """
        super().__init__(parent)
        self.output_config = output_config

        # State for estimates calculation
        self.extent: Extent | None = None
        self.min_zoom = 2
        self.max_zoom = 18
        self.layer_compositions: list[LayerComposition] = []

        # Current options widget
        self.options_widget: KMZOptionsWidget | MBTilesOptionsWidget | GeoTIFFOptionsWidget | None = None

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
        self.type_combo.addItem("GeoTIFF", "geotiff")
        # Set to the actual output type from config
        index = self.type_combo.findData(self.output_config.type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
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
        path_str = str(self.output_config.path) if self.output_config.path else ""
        self.path_edit.setText(path_str)
        self.path_edit.setPlaceholderText("Select output file...")
        self.path_edit.textChanged.connect(self._on_path_changed)
        path_row.addWidget(self.path_edit, 1)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_output_path)
        path_row.addWidget(self.browse_button)

        layout.addLayout(path_row)

        # Container for format-specific options widget
        self.options_container = QVBoxLayout()
        layout.addLayout(self.options_container)

        self.setLayout(layout)

        # Create initial options widget
        self._create_options_widget(self.output_config.type)

    def _create_options_widget(self, output_type: str):
        """Create and add the options widget for the given output type.

        Args:
            output_type: Output type identifier
        """
        # Remove existing options widget if any
        if self.options_widget:
            self.options_container.removeWidget(self.options_widget)
            self.options_widget.deleteLater()
            self.options_widget = None

        # Create new options widget
        # Extract options from model (exclude type and path)
        options = self.output_config.model_dump(exclude={"type", "path"})
        widget_class = get_options_widget(output_type)
        self.options_widget = widget_class(options, parent=self)
        self.options_widget.changed.connect(self.changed.emit)

        # Add to container
        self.options_container.addWidget(self.options_widget)

        # Update estimates with current state
        self.options_widget.update_estimates(self.extent, self.min_zoom, self.max_zoom, self.layer_compositions)

    def _on_type_changed(self):
        """Handle output type change."""
        output_type = self.type_combo.currentData()

        # Auto-update file extension based on output type
        current_path = Path(self.path_edit.text()) if self.path_edit.text() else None
        if current_path and str(current_path) != ".":
            handler = get_output_handler(output_type)
            new_ext = handler.get_file_extension()

            # Replace extension only if it's a recognized output extension
            current_ext = current_path.suffix.lower().lstrip(".")
            recognized_extensions = ["kmz", "mbtiles", "tif", "tiff"]

            if current_ext in recognized_extensions or not current_ext:
                # Replace or add the correct extension
                new_path = current_path.with_suffix(f".{new_ext}")
                self.path_edit.setText(str(new_path))

        # Create new model instance for the new type
        current_path_str = self.path_edit.text() or ""
        if output_type == "kmz":
            self.output_config = KMZOutput(type="kmz", path=current_path_str)
        elif output_type == "mbtiles":
            self.output_config = MBTilesOutput(type="mbtiles", path=current_path_str)
        elif output_type == "geotiff":
            self.output_config = GeoTIFFOutput(type="geotiff", path=current_path_str)

        # Recreate options widget for new type
        self._create_options_widget(output_type)

        self.changed.emit()

    def _on_path_changed(self):
        """Handle path change."""
        # Update the path field on the model (can't assign to immutable Pydantic model)
        # Need to recreate the model - will be handled in get_config()
        self.changed.emit()

    def _browse_output_path(self):
        """Open file dialog to select output path."""
        # Get format-specific file filter and extension
        output_type = self.type_combo.currentData()
        handler = get_output_handler(output_type)
        file_filter = handler.get_file_filter()
        default_ext = handler.get_file_extension()

        # Default to current path or home directory with appropriate extension
        if self.output_config.path:
            default_path = str(self.output_config.path)
        else:
            default_path = str(Path.home() / f"tiles.{default_ext}")

        file_path, _ = QFileDialog.getSaveFileName(
            self, f"Save {handler.get_display_name()} File", default_path, file_filter
        )

        if file_path:
            self.path_edit.setText(file_path)
            # Note: _on_path_changed will be called automatically

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

        # Forward to options widget
        if self.options_widget:
            self.options_widget.update_estimates(extent, min_zoom, max_zoom, layer_compositions)

    def get_config(self) -> OutputUnion:
        """Get the current output configuration.

        Returns:
            Output model instance (KMZ, MBTiles, or GeoTIFF) with current settings
        """
        output_type = self.type_combo.currentData()
        path = self.path_edit.text()

        # Get options from the options widget
        options = {}
        if self.options_widget:
            options = self.options_widget.get_options()

        # Create the appropriate model type with current path and options
        if output_type == "kmz":
            return KMZOutput(type="kmz", path=path, **options)
        elif output_type == "mbtiles":
            return MBTilesOutput(type="mbtiles", path=path, **options)
        elif output_type == "geotiff":
            return GeoTIFFOutput(type="geotiff", path=path, **options)
        else:
            # Fallback (shouldn't happen)
            return KMZOutput(type="kmz", path=path)
