from .vector3d import Vector3d
from .quat import Quat
from struct import pack, unpack
from math import log2, floor

class Keyframe:
    """
    Keyframe container
    """

    KEYFRAME_SIZE_NORMAL = 36
    KEYFRAME_SIZE_COMPRESSED = 22
    LARGE_CONST = 0xBADC0DED

    @staticmethod
    def uncompress(x):
        if type(x) != int:
            return x
        sign = -2* ((x & 0x8000) >> 15) + 1
        if x & 0x78ff == 0:
            return sign*0
        exponent = ((x & 0x7800) >> 11) - 15
        mantissa = 1 + (x & 0x07ff) / 0x800
        return sign * mantissa * 2**exponent

    @staticmethod
    def compress(x):
        sign = 1 if x < 0 else 0
        x = abs(x)
        if x == 0:
            return sign*0
        exponent = int(floor(log2(x)))
        x = (x / 2**exponent) - 1
        exponent = (exponent + 15) & 0xf
        mantissa = int(x * 0x800) & 0x07ff
        return (sign << 15) ^ (exponent << 11) ^ mantissa

    def __init__(self, bone_index : int = 0, time : float = 0.0, location : Vector3d = None, rotation : Quat = None, prev_keyframe_index : int = 0):
        self.bone_index = bone_index
        self.time = time
        self.location = location
        self.rotation = rotation
        self.prev_keyframe_index = prev_keyframe_index

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.bone_index == other.bone_index and self.location == other.location and self.rotation == other.rotation

    def read(self, bin, compressed=False):
        self.location = Vector3d()
        self.rotation = Quat()
        if compressed:
            self.time, self.rotation.x, self.rotation.y, self.rotation.z, self.rotation.w, self.location.x, self.location.y, self.location.z, self.prev_keyframe_index = unpack("<f7HI", bin)
            self.rotation.x, self.rotation.y, self.rotation.z, self.rotation.w, self.location.x, self.location.y, self.location.z = Keyframe.uncompress(self.rotation.x), Keyframe.uncompress(self.rotation.y), Keyframe.uncompress(self.rotation.z), Keyframe.uncompress(self.rotation.w), Keyframe.uncompress(self.location.x), Keyframe.uncompress(self.location.y), Keyframe.uncompress(self.location.z)
            self.prev_keyframe_index //= (Keyframe.KEYFRAME_SIZE_COMPRESSED + 2)
        else:
            self.time, self.rotation.x, self.rotation.y, self.rotation.z, self.rotation.w, self.location.x, self.location.y, self.location.z, self.prev_keyframe_index = unpack("8fI", bin)
            self.prev_keyframe_index //= Keyframe.KEYFRAME_SIZE_NORMAL

    def write(self, compression_range=None):
        keyframe_size = Keyframe.KEYFRAME_SIZE_NORMAL if compression_range is None else (Keyframe.KEYFRAME_SIZE_COMPRESSED + 2)
        prev_keyframe_index = self.prev_keyframe_index*keyframe_size if (self.prev_keyframe_index >= 0) else Keyframe.LARGE_CONST
        if compression_range is None:
            return pack("8fI",
                        self.time,
                        self.rotation.x,
                        self.rotation.y,
                        self.rotation.z,
                        self.rotation.w,
                        self.location.x,
                        self.location.y,
                        self.location.z,
                        prev_keyframe_index)
        else:
            self.location.x = (self.location.x - compression_range["Base"][0])/compression_range["Offset"][0]
            self.location.y = (self.location.y - compression_range["Base"][1])/compression_range["Offset"][1]
            self.location.z = (self.location.z - compression_range["Base"][2])/compression_range["Offset"][2]
            return pack("<f7HI",
                        self.time,
                        Keyframe.compress(self.rotation.x),
                        Keyframe.compress(self.rotation.y),
                        Keyframe.compress(self.rotation.z),
                        Keyframe.compress(self.rotation.w),
                        Keyframe.compress(self.location.x),
                        Keyframe.compress(self.location.y),
                        Keyframe.compress(self.location.z),
                        prev_keyframe_index)