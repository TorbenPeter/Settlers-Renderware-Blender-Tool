from .vector3d import Vector3d
from struct import pack, unpack

class Sphere:
    """
    Bounding sphere container
    """

    BYTE_SIZE = 16

    def __init__(self, position : Vector3d = None, radius : float = None):
        self.position = position
        self.radius = radius

    def read(self, bin):
        self.position = Vector3d()
        self.position.read(bin[:Vector3d.BYTE_SIZE])
        self.radius = unpack("f", bin[Vector3d.BYTE_SIZE:])