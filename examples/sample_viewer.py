import sys

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from nande.widgets import (
    NandeSettingsToolbar,
    NandeViewer,
    NandeViewToolbar, NandeImageAdjustmentToolbar,
)


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
        super().__init__()
        self.viewer = NandeViewer(self)
        self.viewer.use_opengl(True)
        self.viewer.img_clicked.connect(self.show_popup_info)

        view_toolbar = NandeViewToolbar(self.viewer)
        settings_toolbar = NandeSettingsToolbar(self.viewer)
        img_adjustment_toolbar = NandeImageAdjustmentToolbar(self.viewer)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(view_toolbar)
        main_layout.addWidget(img_adjustment_toolbar)
        main_layout.addWidget(self.viewer)
        main_layout.addWidget(settings_toolbar)

        QTimer.singleShot(10, self.viewer.fit_scene_to_image)

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

    def set_zoom_in(self, zoom_level: int):
        zoom_mapping = {
            0: 1.0,
            1: 1.5,
            2: 2.0,
            3: 3.0,
            4: 4.0,
        }
        zoom: float = zoom_mapping.get(zoom_level) or 1.0
        self.viewer.set_zoom(zoom)

    def set_zoom_out(self, zoom_level: int):
        zoom_mapping = {
            0: 1.0,
            1: 0.75,
            2: 0.5,
            3: 0.25,
            4: 0.1,
        }
        zoom: float = zoom_mapping.get(zoom_level) or 1.0
        self.viewer.set_zoom(zoom)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.setGeometry(500, 300, 800, 600)
    window.show()
    sys.exit(app.exec())
