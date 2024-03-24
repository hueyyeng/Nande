import time
from typing import Callable

import cv2
import numpy as np
import PyOpenColorIO as OCIO
from PySide6.QtGui import QImage, QPixmap

from nande import BIT_DEPTH, BitDepth, OCIO_CONFIG


def measure_time(func: Callable, *args, **kwargs):
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    print(
        f"{func.__name__} took {end_time - start_time:0.4f} secs"
    )
    return result


class ChannelEnum:
    RED = 0
    GREEN = 1
    BLUE = 2
    ALPHA = 3
    LUMINANCE = 100


def get_pixmap_from_ndarray(
        image: np.ndarray,
        is_mono: bool = False,
        image_format: QImage.Format = None,
) -> QPixmap:
    if len(image.shape) > 2:
        height, width, channel = image.shape
    else:
        channel = 1
        height, width = image.shape

    bytes_per_line = channel * width

    # TODO: Hmm need to write a helper to figure out the
    #  correct image format
    format_ = QImage.Format.Format_RGBA8888
    if image_format:
        format_ = image_format
    elif is_mono:
        format_ = QImage.Format.Format_Grayscale8
    elif channel == 3:
        format_ = QImage.Format.Format_RGB888

    img: QImage = QImage(
        image.data,
        width,
        height,
        bytes_per_line,
        format_,
    ).rgbSwapped()

    return QPixmap.fromImage(img)


def get_channel(image: np.ndarray, channel: int) -> np.ndarray:
    image = image.astype(BitDepth.STD)
    h, w, channels = image.shape[:3]

    has_alpha = False
    if channels > 3:
        b, g, r, a = cv2.split(image)
        has_alpha = True
    else:
        b, g, r = cv2.split(image)
        a = np.ones((h, w), dtype=BitDepth.STD) * 255

    match channel:
        case ChannelEnum.RED:
            ll = r

        case ChannelEnum.GREEN:
            ll = g

        case ChannelEnum.BLUE:
            ll = b

        case ChannelEnum.ALPHA:
            ll = a
            if has_alpha:
                a = np.ones((h, w), dtype=BitDepth.STD) * 255

    channel_ = cv2.merge([ll, ll, ll, a])

    return channel_


def get_luminance(image: np.ndarray) -> np.ndarray:
    h, w, channels = image.shape[:3]
    image = image / 255.0

    if channels == 4:
        b, g, r, aa = cv2.split(image)
    else:
        b, g, r = cv2.split(image)
        aa: np.ndarray = np.ones((h, w), dtype=BIT_DEPTH)
        if BIT_DEPTH == BitDepth.STD:
            aa = aa * 255
        else:
            aa = aa * 1.0

    r: np.ndarray
    g: np.ndarray
    b: np.ndarray
    a: np.ndarray

    bb = b ** 2.2 * 0.0722
    gg = g ** 2.2 * 0.7152
    rr = r ** 2.2 * 0.2126

    ll = bb + gg + rr
    ll = adjust_gamma(ll, 2.2)

    img = cv2.merge([ll, ll, ll, aa])
    img = (img * 255).astype(BitDepth.STD)

    return img


def adjust_gamma(image: np.ndarray, gamma: float = 1.0):
    img = np.power(image, 1.0 / gamma)
    return img


def get_invert_color(image: np.ndarray) -> np.ndarray:
    img = 1.0 - image / 255.0
    img = (img * 255).astype(BitDepth.STD)
    return img


def get_invert_linear_color(image: np.ndarray) -> np.ndarray:
    img = image / 255.0
    img = 1 - np.power(img, 2.2)  # Invert the values of sRGB gamma removed
    img = np.power(img, 1.0 / 2.2)  # Apply back the inverse sRGB gamma
    img = (img * 255).astype(BitDepth.STD)
    return img


def ocio_transform(
        image: np.ndarray,
        view: str | None = None,
        display: str | None = None,
) -> np.ndarray:
    # TODO: This will get complicated real quick but consider digesting this code 
    #  to figure out a way to implement OpenGL LUT from here: 
    #  https://github.com/AcademySoftwareFoundation/OpenColorIO/tree/main/src/apps/pyociodisplay

    config = OCIO_CONFIG

    if display is None:
        display = config.getDefaultDisplay()

    if view is None:
        view = config.getDefaultView(display)

    # TODO: Implement optional roles for setSrc?
    # FIXME: Another hardcode for src color space. Maybe leaving it linear works??
    transform = OCIO.DisplayViewTransform()
    transform.setSrc(OCIO.ROLE_SCENE_LINEAR)
    transform.setDisplay(display)
    transform.setView(view)

    processor: OCIO.Processor = config.getProcessor(transform)
    cpu = processor.getDefaultCPUProcessor()

    # TODO: Currently average 0.2-0.4 secs on Intel i5 13th Gen CPU... which is very slow
    image = image.astype(BitDepth.FLOAT)
    img = image / 255.0

    # FIXME: For whatever reason, inverted image alpha is gray instead of white...
    cpu.applyRGB(img)

    # Potential out of range values after applyRGB so better clamp I mean clip the values
    # before displaying to the viewer 
    img = np.clip(img * 255.0, 0, 255).astype(BitDepth.STD)
    return img
