from __future__ import annotations

import os

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import *

VALID_FORMATS = (
    ".jpg",
    ".jpeg",
    ".jfif",
    ".tiff",
    ".tif",
    ".gif",
    ".png",
    ".ico",
    ".bmp",
    ".webp",
)
ZOOM_MIN = -0.95
ZOOM_MAX = 2.0


class NandeScene(QGraphicsScene):
    GRID_DISPLAY_NONE = 0
    GRID_DISPLAY_DOTS = 1
    GRID_DISPLAY_LINES = 2
    GRID_SIZE = 50
    BG_COLOR = (65, 65, 65)
    GRID_COLOR = (40, 40, 40)
    GRID_DIVIDER_COLOR = (90, 90, 90)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid_mode = self.GRID_DISPLAY_NONE
        self._bg_color: QColor = QColor(*self.BG_COLOR)
        self._grid_color: QColor = QColor(*self.GRID_COLOR)
        self._grid_divider_color: QColor = QColor(*self.GRID_DIVIDER_COLOR)
        self._grid_size: int = 50
        self._grid_divider: int = 1
        self._grid_linewidth: int = 1
        self.setBackgroundBrush(self._bg_color)

    def _draw_grid(self, painter: QPainter, rect: QRectF, pen: QPen, grid_size: int):
        """
        Draws the grid lines in the scene.

        """
        left = int(rect.left())
        right = int(rect.right())
        top = int(rect.top())
        bottom = int(rect.bottom())

        first_left = left - (left % grid_size)
        first_top = top - (top % grid_size)

        lines = []
        lines.extend([
            QLineF(x, top, x, bottom)
            for x in range(first_left, right, grid_size)
        ])
        lines.extend([
            QLineF(left, y, right, y)
            for y in range(first_top, bottom, grid_size)]
        )

        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawLines(lines)

    def _draw_dots(self, painter: QPainter, rect: QRectF, pen: QPen, grid_size: int):
        """
        Draws the grid dots in the scene.

        """
        zoom = self.viewer().get_zoom()
        if zoom < 0:
            grid_size = int(abs(zoom) / 0.3 + 1) * grid_size

        left = int(rect.left())
        right = int(rect.right())
        top = int(rect.top())
        bottom = int(rect.bottom())

        first_left = left - (left % grid_size)
        first_top = top - (top % grid_size)

        pen.setWidth(self._grid_linewidth)
        pen.setCosmetic(True)
        painter.setPen(pen)

        for x in range(first_left, right, grid_size):
            for y in range(first_top, bottom, grid_size):
                painter.drawPoint(int(x), int(y))

    def viewer(self) -> NandeViewer | None:
        return self.views()[0] if self.views() else None

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setBrush(self.backgroundBrush())

        if self._grid_mode == self.GRID_DISPLAY_DOTS:
            pen = QPen(self._grid_color, 1.0)
            self._draw_dots(painter, rect, pen, self._grid_size)

        if self._grid_mode == self.GRID_DISPLAY_LINES:
            zoom = self.viewer().get_zoom()

            # Draws divider between main grid
            if zoom > -0.5:
                pen = QPen(self._grid_divider_color, 0.5)
                # Probably a good idea to expose this for user to select their style
                pen.setStyle(Qt.PenStyle.DotLine)
                pen.setWidth(self._grid_linewidth - 1)
                self._draw_grid(
                    painter, rect, pen, self._grid_size
                )

            # Draws the main grid
            line_color = self._grid_color.darker(150)
            if zoom < -0.0:
                line_color = line_color.darker(100 - int(zoom * 110))

            pen = QPen(line_color, 0.65)
            pen.setWidth(self._grid_linewidth)
            self._draw_grid(
                painter, rect, pen, self._grid_size * self._grid_divider
            )

        painter.restore()


class NandeViewer(QGraphicsView):
    img_clicked = Signal(QPointF)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.parent_ = parent

        self.LMB_state: bool = False
        self.RMB_state: bool = False
        self.MMB_state: bool = False

        self._is_flip: bool = False
        self._is_flop: bool = False
        self._drag_drop_image_enabled: bool = True
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene = NandeScene(self)
        self._scene.addItem(self._pixmap_item)
        self._scene_range = QRectF(
            0, 0,
            self.size().width(), self.size().height(),
        )
        self._previous_pos = QPoint(
            int(self.width() / 2),
            int(self.height() / 2),
        )

        self.setScene(self._scene)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAcceptDrops(True)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # TODO: Need to study the docs on the update/cache/optimization blah
        # self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        # self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        # self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing)

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)

        if not self._pixmap_item.pixmap():
            text = "No Image"
            font = QFont("SansSerif", 40, QFont.Weight.Bold)
            pen = QPen(QColor(255, 255, 255, 60), 0.65)

            fm = QFontMetrics(font)
            fm_width = fm.boundingRect(text).width()
            fm_height = fm.boundingRect(text).height()

            x = 10
            y = self.height() - fm_height - 5

            text_rect = QRect(
                x, y,
                fm_width + 10,
                fm_height,
            )
            view_rect = QRect(
                0, 0,
                self.viewport().width(), self.viewport().height(),
            )

            viewport_painter = QPainter(self.viewport())
            viewport_painter.fillRect(view_rect, self.get_bg_color())
            viewport_painter.setFont(font)
            viewport_painter.setPen(pen)
            viewport_painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignRight,
                text,
            )

    def use_opengl(self, confirm=True):
        if confirm:
            widget = QOpenGLWidget()
        else:
            widget = QWidget()

        self.setViewport(widget)

    def set_drag_drop_image_enabled(self, enable: bool):
        self._drag_drop_image_enabled = enable

    def set_grid_size(self, grid_size: int):
        self._scene._grid_size = grid_size
        self._update_scene()

    def set_grid_divider(self, grid_divider: int):
        self._scene._grid_divider = grid_divider
        self._update_scene()

    def set_grid_linewidth(self, grid_linewidth: int):
        self._scene._grid_linewidth = grid_linewidth
        self._update_scene()

    def set_grid_mode(self, grid_mode: int):
        self._scene._grid_mode = grid_mode
        self._update_scene()

    def get_bg_color(self) -> QColor:
        return self._scene._bg_color

    def set_bg_color(self, color: QColor):
        self._scene._bg_color = color
        self._scene.setBackgroundBrush(color)

    def get_grid_color(self) -> QColor:
        return self._scene._grid_color

    def set_grid_color(self, color: QColor):
        self._scene._grid_color = color
        self._update_scene()

    def get_grid_divider_color(self) -> QColor:
        return self._scene._grid_divider_color

    def set_grid_divider_color(self, color: QColor):
        self._scene._grid_divider_color = color
        self._update_scene()

    def get_pixmap_item(self) -> QGraphicsPixmapItem:
        return self._pixmap_item

    def get_pixmap_info(self) -> dict:
        pixmap: QPixmap = self._pixmap_item.pixmap()
        data = {
            "width": pixmap.width(),
            "height": pixmap.height(),
            "depth": pixmap.depth()
        }
        return data

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls()and self._drag_drop_image_enabled:
            urls = event.mimeData().urls()
            if len(urls) > 1:
                self.setCursor(Qt.CursorShape.ForbiddenCursor)
            else:
                event.acceptProposedAction()

        self.unsetCursor()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls() and self._drag_drop_image_enabled:
            urls = event.mimeData().urls()
            if len(urls) > 1:
                self.setCursor(Qt.CursorShape.ForbiddenCursor)
            else:
                event.acceptProposedAction()

        self.unsetCursor()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls() and self._drag_drop_image_enabled:
            urls = event.mimeData().urls()
            if len(urls) > 1:
                self.unsetCursor()
                return

            url = urls[0]
            file_path = os.path.normpath(url.toLocalFile())
            _, ext = os.path.splitext(file_path)
            if ext.lower() in VALID_FORMATS:
                self.parent_.setWindowTitle(file_path)
                self._is_flip = False
                self._is_flop = False
                self._pixmap_item.setPixmap(QPixmap(file_path))
                self.fit_scene_to_image()

    def wheelEvent(self, event: QWheelEvent):
        event.pixelDelta()
        delta_y = event.angleDelta().y()
        delta_x = event.angleDelta().x()
        delta = delta_x if not delta_y else delta_y
        self._set_viewer_zoom(delta, pos=event.scenePosition().toPoint())

    def set_pixmap(self, pixmap: QPixmap = None):
        self._pixmap_item.setPixmap(pixmap)

    def _set_viewer_zoom(self, value: float, sensitivity: float = None, pos: QPoint = None):
        """

        Parameters
        ----------
        value : float
            Zoom factor
        sensitivity : float | None
            Zoom sensitivity
        pos : QPoint | None
            Mapped position

        """
        mapped_pos: QPointF | None = pos
        if pos:
            mapped_pos = self.mapToScene(pos)

        if sensitivity is None:
            scale = 1.001 ** value
            self.scale_scene(scale, scale, mapped_pos)
            return

        if value == 0.0:
            return

        scale_min = 0.9
        scale_max = 1.1
        scale = (scale_min + sensitivity) if value < 0.0 else (scale_max - sensitivity)

        zoom = self.get_zoom()
        if ZOOM_MIN >= zoom and scale == scale_min:
            return

        if ZOOM_MAX <= zoom and scale == scale_max:
            return

        self.scale_scene(scale, scale, mapped_pos)

    def scale_scene(self, sx: float, sy: float, pos: QPointF = None):
        scales = [sx, sx]
        center = pos or self._scene_range.center()
        w = self._scene_range.width() / scales[0]
        h = self._scene_range.height() / scales[1]
        self._scene_range = QRectF(
            center.x() - (center.x() - self._scene_range.left()) / scales[0],
            center.y() - (center.y() - self._scene_range.top()) / scales[1],
            w, h
        )
        self._fit_scene_in_view()

    def get_zoom(self) -> float:
        """
        Returns the viewer zoom level.

        Returns
        -------
        float
            Zoom level

        """
        transform: QTransform = self.transform()
        current_scale = (transform.m11(), transform.m22())
        return float("{:0.2f}".format(current_scale[0] - 1.0))

    def set_zoom(self, zoom_level: float):
        self.resetTransform()
        self.scale(zoom_level, zoom_level)

    def _toggle_hand_display(self):
        mode = QGraphicsView.DragMode.NoDrag
        if self.LMB_state:
            mode = QGraphicsView.DragMode.ScrollHandDrag

        self.setDragMode(mode)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.LMB_state = True
        elif event.button() == Qt.MouseButton.RightButton:
            self.RMB_state = True
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.MMB_state = True

        self._previous_pos = event.scenePosition().toPoint()
        self.img_clicked.emit(self.mapToScene(event.scenePosition().toPoint()))

        self._toggle_hand_display()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.LMB_state:
            super().mouseMoveEvent(event)
            return

        previous_pos = self.mapToScene(self._previous_pos)
        current_pos = self.mapToScene(event.scenePosition().toPoint())

        delta = previous_pos - current_pos
        self._set_viewer_pan(
            pos_x=delta.x(),
            pos_y=delta.y(),
        )
        self._previous_pos = event.scenePosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.LMB_state = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.RMB_state = False
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.MMB_state = False

        self._toggle_hand_display()
        super().mouseReleaseEvent(event)

    def _set_viewer_pan(self, pos_x: float, pos_y: float):
        """
        Set the viewer in panning mode.

        """
        self._scene_range.adjust(pos_x, pos_y, pos_x, pos_y)
        self._update_scene()

    def _update_scene(self):
        self.setSceneRect(self._scene_range)
        self._scene.update()

    def _fit_scene_in_view(self):
        self._update_scene()
        self.fitInView(
            self._scene_range,
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def fit_scene_to_image(self):
        self._scene_range.setX(0.0)
        self._scene_range.setY(0.0)
        self._scene_range.setWidth(self._pixmap_item.pixmap().width())
        self._scene_range.setHeight(self._pixmap_item.pixmap().height())
        self._fit_scene_in_view()

    def flip_image(self):
        self._is_flip = not self._is_flip

        scale = (1, -1)
        pixmap_item = self.get_pixmap_item()
        pixmap = pixmap_item.pixmap()
        transform = QTransform.fromScale(*scale)
        pixmap_item.setPixmap(pixmap.transformed(transform))

    def flop_image(self):
        self._is_flop = not self._is_flop

        scale = (-1, 1)
        pixmap_item = self.get_pixmap_item()
        pixmap = pixmap_item.pixmap()
        transform = QTransform.fromScale(*scale)
        pixmap_item.setPixmap(pixmap.transformed(transform))

    def reset_scene_zoom(self):
        # FIXME: Figure out wrong offset when panning right after reset_scene_zoom
        #  and resize the window
        x = - self.size().width() / 2 + (self._pixmap_item.pixmap().width() / 2)
        y = - self.size().height() / 2 + (self._pixmap_item.pixmap().height() / 2)
        self._scene_range = QRectF(
            x, y,
            self.size().width(), self.size().height(),
        )
        self._previous_pos = QPoint(
            int(self.width() / 2),
            int(self.height() / 2),
        )
        self._update_scene()
        self.resetTransform()
