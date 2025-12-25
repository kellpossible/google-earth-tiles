"""Custom zoom range selection widget."""

from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QMouseEvent
from PyQt6.QtWidgets import QWidget


class ZoomRangeWidget(QWidget):
    """
    Custom widget for selecting a zoom range.

    Zoom levels are represented as zones/gaps between tick marks.
    Users drag handles to select a range of zoom levels.
    """

    valueChanged = pyqtSignal(tuple)  # Emits (min_zoom, max_zoom)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_zoom = 2
        self._max_zoom = 18
        self._selected_min = 14
        self._selected_max = 14

        self._dragging_handle = None  # 'min', 'max', or None
        self._handle_radius = 8
        self._zone_height = 30
        self._label_height = 20
        self._margin = 20  # Left/right margins

        self.setMinimumHeight(self._zone_height + self._label_height + 20)
        self.setMinimumWidth(200)  # Reduced to allow flexibility

    def set_range(self, min_zoom: int, max_zoom: int):
        """Set the valid zoom range (based on available layers)."""
        if min_zoom > max_zoom:
            raise ValueError(f"min_zoom ({min_zoom}) > max_zoom ({max_zoom})")

        old_min, old_max = self._min_zoom, self._max_zoom
        self._min_zoom = min_zoom
        self._max_zoom = max_zoom

        # Clamp current selection to new range
        self._selected_min = max(min_zoom, min(self._selected_min, max_zoom))
        self._selected_max = max(min_zoom, min(self._selected_max, max_zoom))

        if old_min != min_zoom or old_max != max_zoom:
            self.update()
            self.valueChanged.emit((self._selected_min, self._selected_max))

    def set_value(self, min_zoom: int, max_zoom: int):
        """Set the selected zoom range."""
        if min_zoom < self._min_zoom or min_zoom > self._max_zoom:
            raise ValueError(f"min_zoom {min_zoom} out of range [{self._min_zoom}, {self._max_zoom}]")
        if max_zoom < self._min_zoom or max_zoom > self._max_zoom:
            raise ValueError(f"max_zoom {max_zoom} out of range [{self._min_zoom}, {self._max_zoom}]")
        if min_zoom > max_zoom:
            raise ValueError(f"min_zoom ({min_zoom}) > max_zoom ({max_zoom})")

        if self._selected_min != min_zoom or self._selected_max != max_zoom:
            self._selected_min = min_zoom
            self._selected_max = max_zoom
            self.update()
            self.valueChanged.emit((min_zoom, max_zoom))

    def value(self) -> tuple:
        """Get the selected zoom range."""
        return (self._selected_min, self._selected_max)

    def _get_zone_width(self) -> float:
        """Calculate the width of each zoom level zone."""
        available_width = self.width() - 2 * self._margin
        num_zones = self._max_zoom - self._min_zoom + 1
        return available_width / num_zones if num_zones > 0 else 0

    def _zoom_to_x(self, zoom: int) -> float:
        """Convert zoom level to x coordinate (left edge of zone)."""
        zone_width = self._get_zone_width()
        return self._margin + (zoom - self._min_zoom) * zone_width

    def _x_to_zoom(self, x: float) -> int:
        """Convert x coordinate to zoom level."""
        zone_width = self._get_zone_width()
        relative_x = x - self._margin

        # Find which zone boundary we're closest to
        zoom_float = self._min_zoom + (relative_x / zone_width)
        zoom = round(zoom_float)

        # Clamp to valid range
        return max(self._min_zoom, min(self._max_zoom, zoom))

    def paintEvent(self, event):
        """Paint the widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get palette for theme-aware colors
        palette = self.palette()
        base_color = palette.color(palette.ColorRole.Base)
        window_color = palette.color(palette.ColorRole.Window)
        text_color = palette.color(palette.ColorRole.Text)
        mid_color = palette.color(palette.ColorRole.Mid)
        dark_color = palette.color(palette.ColorRole.Dark)

        # Determine if we're in dark mode
        is_dark = base_color.lightness() < 128

        zone_width = self._get_zone_width()
        num_zones = self._max_zoom - self._min_zoom + 1

        # Draw zones
        for i in range(num_zones):
            zoom = self._min_zoom + i
            x = self._margin + i * zone_width

            # Determine if this zone is selected
            is_selected = self._selected_min <= zoom <= self._selected_max

            # Draw zone rectangle
            zone_rect = QRect(int(x), 10, int(zone_width), self._zone_height)

            if is_selected:
                # Selected: more visible highlight using theme colors
                if is_dark:
                    # Dark mode: use lighter shade
                    selected_color = window_color.lighter(150)
                    painter.fillRect(zone_rect, selected_color)
                    painter.setPen(QPen(text_color.lighter(120), 2))
                else:
                    # Light mode: use darker shade
                    selected_color = window_color.darker(115)
                    painter.fillRect(zone_rect, selected_color)
                    painter.setPen(QPen(text_color, 2))
            else:
                # Unselected: base/window color
                painter.fillRect(zone_rect, window_color)
                painter.setPen(QPen(mid_color, 1))

            painter.drawRect(zone_rect)

            # Draw zone label (zoom level)
            painter.setPen(text_color)
            font = QFont()
            font.setPointSize(9)
            painter.setFont(font)

            label_rect = QRect(int(x), 10 + self._zone_height + 5, int(zone_width), self._label_height)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, str(zoom))

        # Draw handles at boundaries
        handle_y = 10 + self._zone_height // 2

        # Min handle (left edge of min zone)
        min_x = self._zoom_to_x(self._selected_min)
        self._draw_handle(painter, min_x, handle_y, is_left=True, text_color=text_color, base_color=base_color)

        # Max handle (right edge of max zone)
        max_x = self._zoom_to_x(self._selected_max + 1)
        self._draw_handle(painter, max_x, handle_y, is_left=False, text_color=text_color, base_color=base_color)

    def _draw_handle(self, painter: QPainter, x: float, y: int, is_left: bool, text_color: QColor, base_color: QColor):
        """Draw a handle at the given position."""
        # Use theme colors for handles
        painter.setPen(QPen(text_color, 2))
        painter.setBrush(base_color)

        # Triangle pointing towards the center from the boundary
        if is_left:
            # Left handle - triangle points right
            points = [
                QPoint(int(x - 8), y - 8),
                QPoint(int(x - 8), y + 8),
                QPoint(int(x), y)
            ]
        else:
            # Right handle - triangle points left
            points = [
                QPoint(int(x + 8), y - 8),
                QPoint(int(x + 8), y + 8),
                QPoint(int(x), y)
            ]

        painter.drawPolygon(*points)

    def _get_handle_at_pos(self, pos: QPoint) -> str:
        """Determine which handle (if any) is at the given position."""
        handle_y = 10 + self._zone_height // 2

        # Check min handle
        min_x = self._zoom_to_x(self._selected_min)
        if abs(pos.x() - min_x) < 15 and abs(pos.y() - handle_y) < 15:
            return 'min'

        # Check max handle
        max_x = self._zoom_to_x(self._selected_max + 1)
        if abs(pos.x() - max_x) < 15 and abs(pos.y() - handle_y) < 15:
            return 'max'

        return None

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_handle = self._get_handle_at_pos(event.pos())
            if self._dragging_handle:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move."""
        if self._dragging_handle:
            new_zoom = self._x_to_zoom(event.pos().x())

            if self._dragging_handle == 'min':
                # Min handle can't go past max
                new_min = min(new_zoom, self._selected_max)
                if new_min != self._selected_min:
                    self._selected_min = new_min
                    self.update()
                    self.valueChanged.emit((self._selected_min, self._selected_max))

            elif self._dragging_handle == 'max':
                # Max handle can't go before min
                new_max = max(new_zoom, self._selected_min)
                if new_max != self._selected_max:
                    self._selected_max = new_max
                    self.update()
                    self.valueChanged.emit((self._selected_min, self._selected_max))
        else:
            # Update cursor based on hover
            if self._get_handle_at_pos(event.pos()):
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_handle = None

            # Update cursor based on position
            if self._get_handle_at_pos(event.pos()):
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
