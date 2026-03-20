from .vector3d import Vector3d
from mathutils import Matrix

class Rotation3d:
    """
    Generic 3d rotation container
    """
    def __init__(self, right : Vector3d = None, up : Vector3d = None, at : Vector3d = None):
        self.right = right
        self.up = up
        self.at = at

    def read(self, bin):
        self.right = Vector3d()
        self.right.read(bin[:Vector3d.BYTE_SIZE])
        self.up = Vector3d()
        self.up.read(bin[Vector3d.BYTE_SIZE:Vector3d.BYTE_SIZE*2])
        self.at = Vector3d()
        self.at.read(bin[Vector3d.BYTE_SIZE*2:])

    def as_tuple(self):
        return (self.right.as_tuple(), self.up.as_tuple(), self.at.as_tuple())
    
    def from_matrix(self, matrix : Matrix):
        self.right = Vector3d(*matrix.row[0])
        self.up = Vector3d(*matrix.row[1])
        self.at = Vector3d(*matrix.row[2])
