from mathutils import Vector
from struct import pack, unpack

class Sphere:
    """
    Bounding sphere container
    """

    BYTE_SIZE = 16

    def __init__(self, position : Vector = None, radius : float = None):
        self.position = position
        self.radius = radius

    def read(self, bin):
        self.position = Vector((unpack("3f", bin[:12])))
        self.radius, = unpack("f", bin[12:])

    def write(self):
        return pack("4f", self.position[0], self.position[1], self.position[2], self.radius)