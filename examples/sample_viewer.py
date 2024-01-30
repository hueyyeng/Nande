import os
import sys

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from nande.widgets import NandeViewer


class PopupItem(QGraphicsRectItem):
    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setRect(0, 0, 100, 50)
        self.setBrush(Qt.yellow)

        self.text_item = QGraphicsTextItem(message, self)
        # Adjust the position of the text within the popup
        self.text_item.setPos(5, 5)

        self.timer = QTimer()
        self.timer.timeout.connect(self.hide_popup)

        self.show()
        self.timer.start(2000)  # Timeout after 2 seconds

    def hide_popup(self):
        self.hide()
        self.timer.stop()


class Window(QWidget):
    def __init__(self):
        super(Window, self).__init__()
        self.viewer = NandeViewer(self)
        self.viewer.img_clicked.connect(self.show_popup_info)

        self.load_img_btn = QToolButton(self)
        self.load_img_btn.setText('Load image')
        self.load_img_btn.clicked.connect(self.load_image)

        self.fit_view_btn = QPushButton("Fit to View")
        self.fit_view_btn.clicked.connect(self.fit_image)

        self.zoom_actual_btn = QPushButton("Zoom Actual")
        self.zoom_actual_btn.clicked.connect(self.reset_zoom)
        self.zoom_half_btn = QPushButton("Zoom 50%")
        self.zoom_half_btn.clicked.connect(lambda: self.set_zoom(1))

        self.grid_spacing_spinbox = QSpinBox()
        self.grid_spacing_spinbox.valueChanged.connect(self.set_viewer_grid_size)
        self.grid_spacing_spinbox.setValue(32)
        self.grid_spacing_spinbox.setMinimum(1)
        self.grid_spacing_spinbox.setMaximum(1024)

        self.grid_divider_spinbox = QSpinBox()
        self.grid_divider_spinbox.valueChanged.connect(self.set_viewer_grid_divider)
        self.grid_divider_spinbox.setValue(1)
        self.grid_divider_spinbox.setMinimum(1)
        self.grid_divider_spinbox.setMaximum(50)

        self.grid_linewidth_spinbox = QSpinBox()
        self.grid_linewidth_spinbox.valueChanged.connect(self.set_viewer_grid_linewidth)
        self.grid_linewidth_spinbox.setValue(1)
        self.grid_linewidth_spinbox.setMinimum(1)
        self.grid_linewidth_spinbox.setMaximum(32)

        self.grid_mode_combobox = QComboBox()
        self.grid_mode_combobox.addItem("None", self.viewer._scene.GRID_DISPLAY_NONE)
        self.grid_mode_combobox.addItem("Dots", self.viewer._scene.GRID_DISPLAY_DOTS)
        self.grid_mode_combobox.addItem("Lines", self.viewer._scene.GRID_DISPLAY_LINES)
        self.grid_mode_combobox.setCurrentIndex(2)
        self.grid_mode_combobox.currentIndexChanged.connect(self.set_viewer_grid_mode)

        self.bg_color_toolbtn = QToolButton()
        self.bg_color_toolbtn.setFixedSize(20, 20)
        self.bg_color_toolbtn.setStyleSheet(
            f"background-color: {self.viewer.get_bg_color().name()}"
        )
        self.bg_color_toolbtn.clicked.connect(self.set_bg_color)

        self.grid_color_toolbtn = QToolButton()
        self.grid_color_toolbtn.setFixedSize(20, 20)
        self.grid_color_toolbtn.setStyleSheet(
            f"background-color: {self.viewer.get_grid_color().name()}"
        )
        self.grid_color_toolbtn.clicked.connect(self.set_grid_color)

        self.grid_divider_color_toolbtn = QToolButton()
        self.grid_divider_color_toolbtn.setFixedSize(20, 20)
        self.grid_divider_color_toolbtn.setStyleSheet(
            f"background-color: {self.viewer.get_grid_divider_color().name()}"
        )
        self.grid_divider_color_toolbtn.clicked.connect(self.set_grid_divider_color)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.viewer)
        settings_layout = QHBoxLayout()
        settings_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        settings_layout.addWidget(self.load_img_btn)
        settings_layout.addWidget(self.fit_view_btn)
        settings_layout.addWidget(self.zoom_actual_btn)
        settings_layout.addWidget(self.zoom_half_btn)
        settings_layout.addWidget(QLabel("BG Color:"))
        settings_layout.addWidget(self.bg_color_toolbtn)
        settings_layout.addWidget(QLabel("Grid Color:"))
        settings_layout.addWidget(self.grid_color_toolbtn)
        settings_layout.addWidget(QLabel("Grid Divider Color:"))
        settings_layout.addWidget(self.grid_divider_color_toolbtn)
        settings_layout.addWidget(QLabel("Grid Mode:"))
        settings_layout.addWidget(self.grid_mode_combobox)
        settings_layout.addWidget(QLabel("Grid Spacing:"))
        settings_layout.addWidget(self.grid_spacing_spinbox)
        settings_layout.addWidget(QLabel("Grid Divider:"))
        settings_layout.addWidget(self.grid_divider_spinbox)
        settings_layout.addWidget(QLabel("Grid Line Width:"))
        settings_layout.addWidget(self.grid_linewidth_spinbox)
        main_layout.addLayout(settings_layout)

        QTimer.singleShot(10, self.fit_image)

    def set_viewer_grid_mode(self, idx: int):
        self.viewer.set_grid_mode(idx)

    def set_viewer_grid_size(self, grid_size: int):
        self.viewer.set_grid_size(grid_size)

    def set_viewer_grid_divider(self, grid_divider: int):
        self.viewer.set_grid_divider(grid_divider)

    def set_viewer_grid_linewidth(self, grid_linewidth: int):
        self.viewer.set_grid_linewidth(grid_linewidth)

    def show_popup_info(self, pos: QPointF):
        if self.viewer.RMB_state:
            self.viewer.get_pixmap_info()
            msg = (
                f"Pixel X: {int(pos.x())}"
                f"\n"
                f"Pixel Y: {int(pos.y())}"
            )

            popup_item = PopupItem(msg, self.viewer.get_pixmap_item())
            popup_item.setPos(pos)

    def set_bg_color(self):
        color: QColor = QColorDialog.getColor(self.viewer.get_bg_color().rgba())
        if color.isValid():
            self.bg_color_toolbtn.setStyleSheet(f"background-color: {color.name()};")
            self.viewer.set_bg_color(color)

    def set_grid_color(self):
        color: QColor = QColorDialog.getColor(self.viewer.get_grid_color().rgba())
        if color.isValid():
            self.grid_color_toolbtn.setStyleSheet(f"background-color: {color.name()};")
            self.viewer.set_grid_color(color)

    def set_grid_divider_color(self):
        color: QColor = QColorDialog.getColor(self.viewer.get_grid_divider_color().rgba())
        if color.isValid():
            self.grid_divider_color_toolbtn.setStyleSheet(f"background-color: {color.name()};")
            self.viewer.set_grid_divider_color(color)

    def set_zoom(self, zoom_level: int):
        zoom_mapping = {
            0: 1.0,
            1: 0.75,
            2: 0.5,
        }
        zoom: float = zoom_mapping.get(zoom_level) or 1.0
        self.viewer.set_zoom(zoom)

    def reset_zoom(self):
        self.viewer.reset_scene_zoom()

    def fit_image(self):
        self.viewer.fit_scene_to_image()

    def load_image(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(file_dialog.FileMode.ExistingFile)

        if not file_dialog.exec():
            return

        selected_files = file_dialog.selectedFiles()
        if not selected_files:
            return

        file_path = os.path.normpath(selected_files[0])
        self.setWindowTitle(file_path)
        self.viewer.set_pixmap(QPixmap(file_path))
        self.fit_image()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.setGeometry(500, 300, 800, 600)
    window.show()
    sys.exit(app.exec())
