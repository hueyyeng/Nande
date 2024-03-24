import numpy as np
import PyOpenColorIO as OCIO

__version__ = "0.1.0"


class BitDepth:
    STD = np.uint8
    HALF = np.float16
    FLOAT = np.float32


BIT_DEPTH = BitDepth.FLOAT

# FIXME: For now leave this hardcode. Need to allow user to specify their config
OCIO_CONFIG: OCIO.Config = OCIO.Config.CreateFromFile("ocio://default")
