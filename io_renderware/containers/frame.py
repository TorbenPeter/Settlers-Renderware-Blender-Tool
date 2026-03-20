from mathutils import Matrix

class Frame:

    def __init__(self, matrix : Matrix = None):
        self.matrix = matrix
        self.parent = None
        self.user_data = {}
        self.bone = None

    def get_world_matrix(self):
        if self.matrix is None:
            return
        frame = self
        matrix = self.matrix.copy()
        while frame.parent is not None:
            matrix = frame.parent.matrix @ matrix
            frame = frame.parent
        return matrix
    
    def get_local_matrix(self):
        if self.bone is None:
            return Matrix.Identity(4)
        
        if self.parent is not None and self.parent.bone is not None:
            return self.parent.bone.matrix.inverted() @ self.bone.matrix
        else:
            return self.bone.matrix
