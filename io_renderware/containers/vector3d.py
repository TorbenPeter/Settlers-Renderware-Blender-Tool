from struct import pack, unpack

class Vector3d:
    """
    Generic 3d vector container
    """

    BYTE_SIZE = 12

    @staticmethod
    def round_zeros(x):
        if abs(x) < 1e-6:
            return 0
        return x

    def __init__(self, x : float = 0, y : float = 0, z : float = 0):
        self.x = Vector3d.round_zeros(x)
        self.y = Vector3d.round_zeros(y)
        self.z = Vector3d.round_zeros(z)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.x == other.x and self.y == other.y and self.z == other.z

    def read(self, bin):
        self.x, self.y, self.z = unpack("fff", bin)

    def as_tuple(self):
        return (self.x, self.y, self.z)