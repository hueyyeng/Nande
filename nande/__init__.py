import numpy as np

__version__ = "0.1.0"


class BitDepth:
    STD = np.uint8
    HALF = np.float16
    FLOAT = np.float32


BIT_DEPTH = BitDepth.FLOAT
