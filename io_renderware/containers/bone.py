from .vector3d import Vector3d
from mathutils import Matrix

class Bone:

    def __init__(self, id : int, matrix : Matrix):
        self.id = id
        self.matrix = matrix