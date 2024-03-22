import cv2
import numpy
import numpy as np
from PySide6.QtGui import QImage, QPixmap


class ChannelEnum:
    RED = 0
    GREEN = 1
    BLUE = 2
    ALPHA = 3
    LUMINANCE = 100


def get_pixmap_from_arrays(
        image: numpy.ndarray,
        is_mono: bool = False,
        image_format: QImage.Format = None,
) -> QPixmap:
    if len(image.shape) > 2:
        height, width, channel = image.shape
    else:
        channel = 1
        height, width = image.shape

    bytes_per_line = channel * width
    format_ = QImage.Format.Format_ARGB32
    if image_format:
        format_ = image_format
    elif is_mono:
        format_ = QImage.Format.Format_Grayscale8

    img: QImage = QImage(
        image.data,
        width,
        height,
        bytes_per_line,
        format_,
    ).rgbSwapped()

    return QPixmap.fromImage(img)


def get_channel(image: numpy.ndarray, channel: int) -> numpy.ndarray | None:
    h, w = image.shape[:2]
    r = g = b = a = None

    channels = cv2.split(image)
    if len(channels) == 3:
        b, g, r = cv2.split(image)
        a = np.ones((h, w), dtype=np.uint8) * 255

    if len(channels) == 4:
        b, g, r, a = cv2.split(image)

    channel_: numpy.ndarray | None = None
    match channel:
        case ChannelEnum.RED:
            channel_ = r
        case ChannelEnum.GREEN:
            channel_ = g
        case ChannelEnum.BLUE:
            channel_ = b
        case ChannelEnum.ALPHA:
            channel_ = a

    return channel_


def get_luminance(image: numpy.ndarray) -> numpy.ndarray:
    img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return img


def get_invert_color(image: numpy.ndarray) -> numpy.ndarray:
    img = cv2.bitwise_not(image)
    return img
