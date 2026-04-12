from mathutils import Vector
from struct import pack, unpack

class UVKeyframe:

    KEYFRAME_SIZE = 32
    LARGE_CONST = 0xBADC0DED

    def __init__(self, linear : bool, node_index : int = -1,  time : float = 0.0, scale : Vector = None, position : Vector = None, prev_keyframe_index : int = 0):
        self.linear = linear
        self.node_index = node_index
        self.time = time
        self.scale = scale
        self.position = position
        self.prev_keyframe_index = prev_keyframe_index

    def read(self, bin):
        
        if self.linear:
            return
        
        self.time, = unpack("f", bin[:4])
        self.scale = Vector(unpack("3f", bin[4:16]))
        self.position = Vector(unpack("3f", bin[16:28]))
        self.prev_keyframe_index, = unpack("i", bin[28:])