from .vector3d import Vector3d
from .rotation3d import Rotation3d
from mathutils import Vector, Matrix

class Frame:

    def __init__(self, rotation : Rotation3d, position : Vector3d):
        self.rotation = rotation
        self.position = position
        self.parent = None
        self.user_data = {}
        self.bone = None

    def get_canonical_position(self):
        frame = self
        position = Vector(self.position.as_tuple())
        while frame.parent is not None:
            position = position @ Matrix(frame.parent.rotation.as_tuple()) + Vector(frame.parent.position.as_tuple())
            frame = frame.parent
        return position
    
    def get_canonical_rotation(self):
        frame = self
        rotation = Matrix(self.rotation.as_tuple())
        while frame.parent is not None:
            rotation = rotation @ Matrix(frame.parent.rotation.as_tuple())
            frame = frame.parent
        return rotation