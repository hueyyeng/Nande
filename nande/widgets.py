from __future__ import annotations

import os
from functools import partial

import cv2
import numpy
import numpy as np
import qimage2ndarray
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import *

from nande import BIT_DEPTH, BitDepth, OCIO_CONFIG
from nande.utils import (
    ChannelEnum,
    get_channel,
    get_invert_color,
    get_invert_linear_color,
    get_luminance,
    get_pixmap_from_ndarray,
    measure_time,
    ocio_transform,
)

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


class OCIOViewsComboBox(QComboBox):
    def __init__(self, parent: NandeViewToolbar):
        super().__init__(parent)
        self.parent_ = parent
        try:
            self.populate()
        except Exception as e:
            print(f"Woops unhandled exception! {e}")

    def populate(self):
        config = OCIO_CONFIG
        default_display = config.getDefaultDisplay()
        default_view = config.getDefaultView(default_display)
        views = config.getActiveViews().split(",")
        for view in views:
            self.addItem(view.strip())

        dv_idx: int = self.findText(default_view)
        self.setCurrentIndex(dv_idx)


class OCIODisplaysComboBox(QComboBox):
    def __init__(self, parent: NandeViewToolbar):
        super().__init__(parent)
        self.parent_ = parent
        try:
            self.populate()
        except Exception as e:
            print(f"Woops unhandled exception! {e}")

    def populate(self):
        config = OCIO_CONFIG
        displays = config.getDisplays()
        default_display = config.getDefaultDisplay()
        for display in displays:
            display: str
            self.addItem(display)

        dd_idx: int = self.findText(default_display)
        self.setCurrentIndex(dd_idx)


class NandeButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAutoDefault(False)


class NandeImageSlider(QSlider):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOrientation(Qt.Orientation.Horizontal)
        self.setMinimum(-100)
        self.setMaximum(100)
        self.setValue(0)
        self.setTickInterval(20)
        self.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.setSingleStep(20)


class NandeImageAdjustmentToolbar(QWidget):
    def __init__(self, parent: NandeViewer):
        super().__init__(parent)
        self.parent_ = parent
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.channels_combobox = QComboBox()
        self.channels_combobox.addItem("Color (RGB)", None)
        self.channels_combobox.addItem("Red", ChannelEnum.RED)
        self.channels_combobox.addItem("Green", ChannelEnum.GREEN)
        self.channels_combobox.addItem("Blue", ChannelEnum.BLUE)
        self.channels_combobox.addItem("Alpha", ChannelEnum.ALPHA)
        self.channels_combobox.addItem("Luminance", ChannelEnum.LUMINANCE)
        self.channels_combobox.currentIndexChanged.connect(self._channel_changed)

        self.invert_color_btn = NandeButton("Invert Color")
        self.invert_color_btn.clicked.connect(self.parent_.view_invert_color)

        self.invert_linear_color_btn = NandeButton("Invert Linear Color")
        self.invert_linear_color_btn.clicked.connect(self.parent_.view_invert_linear_color)

        self.brightness_slider = NandeImageSlider(self)
        self.contrast_slider = NandeImageSlider(self)

        layout.addWidget(self.channels_combobox)
        layout.addWidget(self.invert_color_btn)
        layout.addWidget(self.invert_linear_color_btn)
        layout.addWidget(QLabel("Brightness:"))
        layout.addWidget(self.brightness_slider)
        layout.addWidget(QLabel("Contrast:"))
        layout.addWidget(self.contrast_slider)

    def _channel_changed(self):
        channel_idx = self.channels_combobox.currentData()
        self.parent_.view_channel(channel_idx)


class NandeViewToolbar(QWidget):
    def __init__(self, parent: NandeViewer):
        super().__init__(parent)
        self.parent_ = parent
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.use_ocio_checkbox = QCheckBox("Use OCIO")
        self.use_ocio_checkbox.toggled.connect(self._toggled_use_ocio)

        self.ocio_views_combobox = OCIOViewsComboBox(self)
        self.ocio_views_combobox.currentIndexChanged.connect(self._ocio_view_changed)

        self.ocio_displays_combobox = OCIODisplaysComboBox(self)
        self.ocio_displays_combobox.currentIndexChanged.connect(self._ocio_display_changed)

        self.set_linear_filter_checkbox = QCheckBox("Linear Filter")
        self.set_linear_filter_checkbox.toggled.connect(self._toggled_linear_filter)

        self.fit_view_btn = NandeButton("Fit to View")
        self.fit_view_btn.clicked.connect(self.parent_.fit_scene_to_image)

        self.zoom_actual_btn = NandeButton("Zoom Actual")
        self.zoom_actual_btn.clicked.connect(self.parent_.reset_scene_zoom)

        self.rotate_90cw_btn = NandeButton("Rotate 90 Clockwise")
        self.rotate_90cw_btn.clicked.connect(lambda: self.parent_.rotate(90))
        self.rotate_90ccw_btn = NandeButton("Rotate 90 Counter Clockwise")
        self.rotate_90ccw_btn.clicked.connect(lambda: self.parent_.rotate(-90))
        self.rotate_180_btn = NandeButton("Rotate 180")
        self.rotate_180_btn.clicked.connect(lambda: self.parent_.rotate(180))

        self.flip_btn = NandeButton("Flip")
        self.flip_btn.clicked.connect(self.parent_.flip_image)
        self.flop_btn = NandeButton("Flop")
        self.flop_btn.clicked.connect(self.parent_.flop_image)

        layout.addWidget(self.use_ocio_checkbox)
        layout.addWidget(self.ocio_displays_combobox)
        layout.addWidget(self.ocio_views_combobox)
        layout.addWidget(self.set_linear_filter_checkbox)
        layout.addWidget(self.fit_view_btn)
        layout.addWidget(self.zoom_actual_btn)
        layout.addWidget(self.rotate_90cw_btn)
        layout.addWidget(self.rotate_90ccw_btn)
        layout.addWidget(self.rotate_180_btn)
        layout.addWidget(self.flip_btn)
        layout.addWidget(self.flop_btn)

        self._post_init()

    def _post_init(self):
        self._ocio_display_changed()
        self._ocio_view_changed()

    def _ocio_display_changed(self):
        self.parent_.ocio_display = self.ocio_displays_combobox.currentText()

    def _ocio_view_changed(self):
        self.parent_.ocio_view = self.ocio_views_combobox.currentText()

    def _toggled_use_ocio(self):
        self.parent_._use_ocio = self.use_ocio_checkbox.isChecked()

    def _toggled_linear_filter(self):
        self.parent_.use_linear_filter(self.set_linear_filter_checkbox.isChecked())


class NandeSettingsToolbar(QWidget):
    def __init__(self, parent: NandeViewer):
        super().__init__(parent)
        self.parent_ = parent
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.load_img_btn = QToolButton(self)
        self.load_img_btn.setText('Load image')
        self.load_img_btn.clicked.connect(self.load_image)

        self.toggle_fps_checkbox = QCheckBox("Show FPS")
        self.toggle_fps_checkbox.toggled.connect(
            lambda: self.parent_.show_fps_counter(self.toggle_fps_checkbox.isChecked())
        )

        self.toggle_use_tiles = QCheckBox("Use Tiles (requires image reload)")
        self.toggle_use_tiles.toggled.connect(
            lambda: self.parent_.use_tiles_mode(self.toggle_use_tiles.isChecked())
        )

        self.grid_spacing_spinbox = QSpinBox()
        self.grid_spacing_spinbox.valueChanged.connect(self.parent_.set_grid_size)
        self.grid_spacing_spinbox.setValue(32)
        self.grid_spacing_spinbox.setMinimum(1)
        self.grid_spacing_spinbox.setMaximum(1024)

        self.grid_divider_spinbox = QSpinBox()
        self.grid_divider_spinbox.valueChanged.connect(self.parent_.set_grid_divider)
        self.grid_divider_spinbox.setValue(1)
        self.grid_divider_spinbox.setMinimum(1)
        self.grid_divider_spinbox.setMaximum(50)

        self.grid_linewidth_spinbox = QSpinBox()
        self.grid_linewidth_spinbox.valueChanged.connect(self.parent_.set_grid_linewidth)
        self.grid_linewidth_spinbox.setValue(1)
        self.grid_linewidth_spinbox.setMinimum(1)
        self.grid_linewidth_spinbox.setMaximum(32)

        self.grid_mode_combobox = QComboBox()
        self.grid_mode_combobox.addItem("None", self.parent_._scene.GRID_DISPLAY_NONE)
        self.grid_mode_combobox.addItem("Dots", self.parent_._scene.GRID_DISPLAY_DOTS)
        self.grid_mode_combobox.addItem("Lines", self.parent_._scene.GRID_DISPLAY_LINES)
        self.grid_mode_combobox.setCurrentIndex(0)
        self.grid_mode_combobox.currentIndexChanged.connect(self.parent_.set_grid_mode)

        self.bg_color_toolbtn = QToolButton()
        self.bg_color_toolbtn.setFixedSize(20, 20)
        self.bg_color_toolbtn.setStyleSheet(
            f"background-color: {self.parent_.get_bg_color().name()}"
        )
        self.bg_color_toolbtn.clicked.connect(self.set_bg_color)

        self.grid_color_toolbtn = QToolButton()
        self.grid_color_toolbtn.setFixedSize(20, 20)
        self.grid_color_toolbtn.setStyleSheet(
            f"background-color: {self.parent_.get_grid_color().name()}"
        )
        self.grid_color_toolbtn.clicked.connect(self.set_grid_color)

        self.grid_divider_color_toolbtn = QToolButton()
        self.grid_divider_color_toolbtn.setFixedSize(20, 20)
        self.grid_divider_color_toolbtn.setStyleSheet(
            f"background-color: {self.parent_.get_grid_divider_color().name()}"
        )
        self.grid_divider_color_toolbtn.clicked.connect(self.set_grid_divider_color)

        layout.addWidget(self.load_img_btn)
        layout.addWidget(self.toggle_use_tiles)
        layout.addWidget(self.toggle_fps_checkbox)
        layout.addWidget(QLabel("BG Color:"))
        layout.addWidget(self.bg_color_toolbtn)
        layout.addWidget(QLabel("Grid Color:"))
        layout.addWidget(self.grid_color_toolbtn)
        layout.addWidget(QLabel("Grid Divider Color:"))
        layout.addWidget(self.grid_divider_color_toolbtn)
        layout.addWidget(QLabel("Grid Mode:"))
        layout.addWidget(self.grid_mode_combobox)
        layout.addWidget(QLabel("Grid Spacing:"))
        layout.addWidget(self.grid_spacing_spinbox)
        layout.addWidget(QLabel("Grid Divider:"))
        layout.addWidget(self.grid_divider_spinbox)
        layout.addWidget(QLabel("Grid Line Width:"))
        layout.addWidget(self.grid_linewidth_spinbox)

    def set_bg_color(self):
        color: QColor = QColorDialog.getColor(self.parent_.get_bg_color().rgba())
        if color.isValid():
            self.bg_color_toolbtn.setStyleSheet(f"background-color: {color.name()};")
            self.parent_.set_bg_color(color)

    def set_grid_color(self):
        color: QColor = QColorDialog.getColor(self.parent_.get_grid_color().rgba())
        if color.isValid():
            self.grid_color_toolbtn.setStyleSheet(f"background-color: {color.name()};")
            self.parent_.set_grid_color(color)

    def set_grid_divider_color(self):
        color: QColor = QColorDialog.getColor(self.parent_.get_grid_divider_color().rgba())
        if color.isValid():
            self.grid_divider_color_toolbtn.setStyleSheet(f"background-color: {color.name()};")
            self.parent_.set_grid_divider_color(color)

    def load_image(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(file_dialog.FileMode.ExistingFile)

        if not file_dialog.exec():
            return

        selected_files = file_dialog.selectedFiles()
        if not selected_files:
            return

        file_path = os.path.normpath(selected_files[0])
        self.parent_.load_image(file_path)


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


class NandePixmapItem(QGraphicsPixmapItem):
    def __init__(self, use_linear_filter=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_linear_filter(use_linear_filter)

    def set_linear_filter(self, use_linear: bool):
        mode = (
            Qt.TransformationMode.SmoothTransformation
            if use_linear else
            Qt.TransformationMode.FastTransformation
        )
        self.setTransformationMode(mode)


class NandeViewer(QGraphicsView):
    img_clicked = Signal(QPointF)
    window_title_changed = Signal(str)

    HUD_FPS_FONT_SIZE = 20
    HUD_TEXT_FONT_SIZE = 16

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.parent_ = parent

        self.LMB_state: bool = False
        self.RMB_state: bool = False
        self.MMB_state: bool = False

        self.current_file_path: str = ""
        self.no_image_text: str = "No Image"
        self.zoom_level: float | None = None
        self._zoom_factor: float | None = None

        self.ocio_display: str | None = None
        self.ocio_view: str | None = None
        self._use_ocio: bool = False
        self._is_inverted: bool = False
        self._is_flip: bool = False
        self._is_flop: bool = False
        self._is_panning: bool = False
        self._is_opengl: bool = False
        self._show_fps: bool = False
        self._use_linear_filter: bool = False
        self._use_tiles: bool = False
        self._drag_drop_image_enabled: bool = True

        self._framebuffer_item = NandePixmapItem(self._use_linear_filter)
        self._framebuffer_tiles: QGraphicsItemGroup | None = None
        self._original_framebuffer: QPixmap = QPixmap()
        self._original_image: numpy.ndarray = np.zeros((1, 1), dtype=BIT_DEPTH)

        self._scene = NandeScene(self)
        self._scene.addItem(self._framebuffer_item)
        self._scene.addItem(self._framebuffer_tiles)
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

        self._install_shortcuts()

        # TODO: Need to study the docs on the update/cache/optimization blah
        # self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        # self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        # self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing)

        # FPS counter
        self._fps: int = 0
        self._framerate: int = 0
        timer = QTimer(
            self,
            timeout=self._fps_timeout,
            interval=1000,
        )
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        timer.start()

    def _install_shortcuts(self):
        """
        Setup supported keyboard shortcuts.
        """
        # R,G,B,A = view channel
        # C = view color
        # TODO: Need to rewrite this as quick copy paste code and tweak from
        #  https://github.com/AcademySoftwareFoundation/OpenColorIO/tree/main/src/apps/pyociodisplay
        for i, key in enumerate(("R", "G", "B", "A")):
            channel_shortcut = QShortcut(
                QKeySequence(key),
                self
            )
            channel_shortcut.activated.connect(
                partial(self.view_channel, idx=i)
            )

        channel_shortcut = QShortcut(
            QKeySequence("C"),
            self
        )
        channel_shortcut.activated.connect(
            partial(self.view_channel, idx=None)
        )

        channel_shortcut = QShortcut(
            QKeySequence("L"),
            self
        )
        channel_shortcut.activated.connect(
            partial(self.view_channel, idx=100)
        )

        channel_shortcut = QShortcut(
            QKeySequence("Shift+I"),
            self
        )
        channel_shortcut.activated.connect(
            self.view_invert_linear_color,
        )

        channel_shortcut = QShortcut(
            QKeySequence("F"),
            self
        )
        channel_shortcut.activated.connect(
            self.fit_scene_to_image,
        )

        channel_shortcut = QShortcut(
            QKeySequence("N"),
            self
        )
        channel_shortcut.activated.connect(
            self._toggle_linear_filter,
        )

    def _fps_timeout(self):
        if not self._show_fps:
            return

        self._framerate = self._fps
        self._fps = 0
        if not self._is_panning and self._framerate:
            self._framerate = 0
            self._update_scene()

    def paintEvent(self, event: QPaintEvent):
        self._fps += 1

        valid_tiles = self._use_tiles and self._framebuffer_tiles
        if not self._framebuffer_item.pixmap() and not valid_tiles:
            text = self.no_image_text
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
        else:
            super().paintEvent(event)

    def drawForeground(self, painter: QPainter, rect: QRect | QRectF, *args, **kwargs):
        super().drawForeground(painter, rect, *args, **kwargs)

        if not self._show_fps:
            return

        painter.save()
        painter.setPen("white")
        painter.setWorldMatrixEnabled(False)

        font = painter.font()
        font.setPixelSize(self.HUD_FPS_FONT_SIZE)
        painter.setFont(font)
        painter.drawText(0, self.HUD_FPS_FONT_SIZE - (self.HUD_FPS_FONT_SIZE / 10), f"{self._framerate} FPS")

        viewport_mode = "OpenGL" if self._is_opengl else "Raster"
        font.setPixelSize(self.HUD_TEXT_FONT_SIZE)
        painter.setFont(font)
        painter.drawText(0, self.HUD_TEXT_FONT_SIZE * 2.5, viewport_mode)
        painter.restore()

    def use_linear_filter(self, use_linear: bool):
        self._use_linear_filter = use_linear
        self._framebuffer_item.set_linear_filter(use_linear)

    def _toggle_linear_filter(self):
        self._use_linear_filter = not self._use_linear_filter
        self._framebuffer_item.set_linear_filter(self._use_linear_filter)

    def use_opengl(self, confirm=True):
        if confirm:
            widget = QOpenGLWidget()
        else:
            widget = QWidget()

        self._is_opengl = confirm
        self.setViewport(widget)

    def use_tiles_mode(self, toggle: bool):
        self._use_tiles = toggle

    def show_fps_counter(self, toggle: bool):
        self._show_fps = toggle
        self._update_scene()

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
        return self._framebuffer_item

    def get_pixmap_info(self) -> dict:
        if self._use_tiles and self._framebuffer_tiles:
            _: QGraphicsPixmapItem = self._framebuffer_tiles.childItems()[0]
            data = {
                "width": self._framebuffer_tiles.boundingRect().width(),
                "height": self._framebuffer_tiles.boundingRect().height(),
                "depth": _.pixmap().depth(),
            }
        else:
            pixmap: QPixmap = self._framebuffer_item.pixmap()
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
                self.current_file_path = file_path
                self._is_flip = False
                self._is_flop = False
                self.load_image(file_path)

    def wheelEvent(self, event: QWheelEvent):
        delta_y = event.angleDelta().y()
        delta_x = event.angleDelta().x()
        delta = delta_x if not delta_y else delta_y
        self._set_viewer_zoom(delta, pos=event.scenePosition().toPoint())

    def _clear_tiles(self):
        if not self._framebuffer_tiles:
            return

        for item in self._framebuffer_tiles.childItems():
            self._scene.removeItem(item)

    def _read_convert_image(self, file_path: str, depth: BIT_DEPTH | None = None):
        if depth is None:
            depth = BitDepth.FLOAT

        raw = cv2.imread(file_path, flags=cv2.IMREAD_UNCHANGED)
        channels = cv2.split(raw)
        channels = [
            channel.astype(depth) for channel in channels
        ]
        return cv2.merge(channels)

    def load_image(self, file_path: str):
        # TODO: Use QImageReader to construct pixmap tiles from very high res image
        # image = QImageReader(file_path)
        self._original_image = self._read_convert_image(file_path)
        self._original_framebuffer = QPixmap(file_path)

        img = self._original_image.astype(BitDepth.STD)
        pixmap = self._get_pixmap_from_ndarray(img)

        self._clear_tiles()
        if self._use_tiles:
            tile_size = QSize(512, 512)
            tiles = []
            for y in range(0, pixmap.height(), tile_size.height()):
                for x in range(0, pixmap.width(), tile_size.width()):
                    w = min(tile_size.width(), pixmap.width() - x)
                    h = min(tile_size.height(), pixmap.height() - y)

                    tile = self._scene.addPixmap(pixmap.copy(x, y, w, h))
                    tile.setPos(x, y)
                    tiles.append(tile)

            self._framebuffer_tiles = self._scene.createItemGroup(tiles)

        else:
            self._framebuffer_item.setPixmap(pixmap)

        self.fit_scene_to_image()

    def set_pixmap(self, pixmap: QPixmap):
        img: QImage = pixmap.toImage()
        # TODO: Hmm need to handle alpha channel? For now happy flow with rgb_view...
        raw: np.ndarray = qimage2ndarray.rgb_view(img)
        raw = cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)
        channels = cv2.split(raw)
        channels = [
            channel.astype(BitDepth.FLOAT) for channel in channels
        ]
        self._original_image = cv2.merge(channels)

        self._original_framebuffer = pixmap
        self._framebuffer_item.setPixmap(pixmap)

    def _get_pixmap_from_ndarray(self,image: np.ndarray, disable_ocio=False, *args, **kwargs):
        if not disable_ocio and self._use_ocio:
            image = measure_time(
                ocio_transform,
                image,
                view=self.ocio_view,
                display=self.ocio_display,
            )

        return get_pixmap_from_ndarray(image, *args, **kwargs)

    def view_channel(self, idx: int | None):
        if idx is None:
            pixmap = self._original_framebuffer
            if self._use_ocio:
                pixmap = self._get_pixmap_from_ndarray(self._original_image)

            self._framebuffer_item.setPixmap(pixmap)
            return

        if idx == ChannelEnum.LUMINANCE:
            measure_time(self.view_luminance)
            return

        ch = measure_time(get_channel, self._original_image, idx)
        if ch is None:
            return

        pixmap = self._get_pixmap_from_ndarray(ch, disable_ocio=True)
        self._framebuffer_item.setPixmap(pixmap)

    def view_luminance(self):
        lu = get_luminance(self._original_image)
        pixmap = self._get_pixmap_from_ndarray(lu, disable_ocio=True)
        self._framebuffer_item.setPixmap(pixmap)

    def view_invert_color(self):
        self._is_inverted = not self._is_inverted
        if not self._is_inverted:
            self.view_channel(None)
            return

        ic = measure_time(get_invert_color, self._original_image)
        image_format = QImage.Format.Format_RGB888
        if len(self._original_image.shape) > 2:
            _, _, channels = self._original_image.shape
            if channels > 3:
                image_format = QImage.Format.Format_RGBA8888_Premultiplied

        pixmap = self._get_pixmap_from_ndarray(ic, image_format=image_format)
        self._framebuffer_item.setPixmap(pixmap)

    def view_invert_linear_color(self):
        self._is_inverted = not self._is_inverted
        if not self._is_inverted:
            self.view_channel(None)
            return

        ic = measure_time(get_invert_linear_color, self._original_image)
        image_format = QImage.Format.Format_RGB888
        if len(self._original_image.shape) > 2:
            _, _, channels = self._original_image.shape
            if channels > 3:
                image_format = QImage.Format.Format_RGBA8888_Premultiplied

        pixmap = self._get_pixmap_from_ndarray(ic, image_format=image_format)
        self._framebuffer_item.setPixmap(pixmap)

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

    def get_zoom_factor(self) -> float:
        transform: QTransform = self.transform()
        current_scale = transform.m11()

        return current_scale

    def _update_window_title(self):
        self._zoom_factor = self.get_zoom_factor()

        if not self.current_file_path:
            title = "NandeViewer"
        else:
            zoom_factor = round(self._zoom_factor, 2)
            zoom_percentage = f"{zoom_factor:.0%}"
            title = (
                f"{self.current_file_path} - {zoom_percentage}"
            )

        self.window_title_changed.emit(title)

    def _toggle_hand_display(self):
        mode = QGraphicsView.DragMode.NoDrag
        self._is_panning = False
        if self.LMB_state:
            self._is_panning = True
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
        self._update_window_title()

    def force_update(self):
        self._update_scene()

    def fit_scene_to_image(self):
        self.zoom_level = None

        self._scene_range.setX(0.0)
        self._scene_range.setY(0.0)
        if self._use_tiles and self._framebuffer_tiles:
            rect: QRectF = self._framebuffer_tiles.boundingRect()
            self._scene_range.setWidth(rect.width())
            self._scene_range.setHeight(rect.height())
        else:
            self._scene_range.setWidth(self._framebuffer_item.pixmap().width())
            self._scene_range.setHeight(self._framebuffer_item.pixmap().height())

        self._fit_scene_in_view()

    @staticmethod
    def _flip_transform(rect: QRectF) -> QTransform:
        center: QPointF = rect.center()
        pivot_x = center.x()
        pivot_y = center.y()
        transform = QTransform()
        transform.translate(pivot_x, pivot_y)
        transform.scale(1, -1)
        transform.translate(-pivot_x, -pivot_y)

        return transform

    def flip_image(self):
        self._is_flip = not self._is_flip

        if self._use_tiles and self._framebuffer_tiles:
            rect: QRectF = self._framebuffer_tiles.boundingRect()
            transform = self._flip_transform(rect)

            self._framebuffer_tiles.setTransform(transform, combine=True)
        else:
            rect: QRectF = self._framebuffer_item.boundingRect()
            transform = self._flip_transform(rect)
            self._framebuffer_item.setTransform(transform, combine=True)

    @staticmethod
    def _flop_transform(rect: QRectF) -> QTransform:
        center: QPointF = rect.center()
        pivot_x = center.x()
        pivot_y = center.y()
        transform = QTransform()
        transform.translate(pivot_x, pivot_y)
        transform.scale(-1, 1)
        transform.translate(-pivot_x, -pivot_y)

        return transform

    def flop_image(self):
        self._is_flop = not self._is_flop

        if self._use_tiles and self._framebuffer_tiles:
            rect: QRectF = self._framebuffer_tiles.boundingRect()
            transform = self._flop_transform(rect)
            self._framebuffer_tiles.setTransform(transform, combine=True)
        else:
            rect: QRectF = self._framebuffer_item.boundingRect()
            transform = self._flop_transform(rect)
            self._framebuffer_item.setTransform(transform, combine=True)

    def _recalculate_scene_zoom(self):
        if self._use_tiles and self._framebuffer_tiles:
            pix_width = self._framebuffer_tiles.boundingRect().width()
            pix_height = self._framebuffer_tiles.boundingRect().width()
        else:
            pix_width = self._framebuffer_item.pixmap().width()
            pix_height = self._framebuffer_item.pixmap().height()

        x = - self.size().width() / 2 + (pix_width / 2)
        y = - self.size().height() / 2 + (pix_height / 2)
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

    def reset_scene_zoom(self):
        self.zoom_level = None
        # FIXME: Figure out wrong offset when panning right after reset_scene_zoom
        #  and resize the window
        self._recalculate_scene_zoom()
        self._update_window_title()

    def set_zoom(self, zoom_level: float):
        if not zoom_level == self._zoom_factor:
            self.zoom_level = zoom_level
            self._recalculate_scene_zoom()
            self.scale_scene(zoom_level, zoom_level)
