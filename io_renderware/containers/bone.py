from mathutils import Matrix

class Bone:

    def __init__(self, id : int):
        self.id : int = id
        self.parent : int = None
        self.matrix : Matrix = None