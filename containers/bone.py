from .vector3d import Vector3d

class Bone:

    def __init__(self, id : int, head : Vector3d, tail : Vector3d):
        self.id = id
        self.head = head
        self.matrix = tail
        self.object = None