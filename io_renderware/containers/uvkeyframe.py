from mathutils import Vector
from struct import pack, unpack

class UVKeyframe:

    KEYFRAME_SIZE = 32
    LARGE_CONST = 0xBADC0DED

    def __init__(self, linear : bool, node_index : int = -1,  time : float = 0.0, scale : Vector = None, position : Vector = None, keyframe_index : int = 0):
        self.linear = linear
        self.node_index = node_index
        self.time = time
        self.scale = scale
        self.position = position
        self.keyframe_index = keyframe_index

    def read(self, bin):
        
        if self.linear:
            return
        
        self.time, = unpack("f", bin[:4])
        self.scale = Vector(unpack("3f", bin[4:16]))
        self.position = Vector(unpack("3f", bin[16:28]))
        self.keyframe_index, = unpack("i", bin[28:])

    def write(self):
        keyframe_index = self.keyframe_index if self.keyframe_index >= 0 else UVKeyframe.LARGE_CONST
        return pack("7fI", self.time, *self.scale, *self.position, keyframe_index)