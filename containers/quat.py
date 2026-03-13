class Quat:
    """
    Quaternion container
    """

    def __init__(self, x : float = 0, y : float = 0, z : float = 0, w : float = 1):
        if abs(w) < 1e-6:
            self.w = 0
        else:
            self.w = w

        if abs(x) < 1e-6:
            self.x = 0
        else:
            self.x = x

        if abs(y) < 1e-6:
            self.y = 0
        else: 
            self.y = y

        if abs(z) < 1e-6:
            self.z = 0
        else:
            self.z = z

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.x == other.x and self.y == other.y and self.z == other.z and self.w == other.w

    def as_tuple(self):
        return (self.w, self.x, self.y, self.z)