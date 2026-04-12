from struct import pack, unpack

class RGBA:
    """
    RGBA color container
    """

    BYTE_SIZE = 4

    def __init__(self, r : int = None, g : int = None, b : int = None, a : int = None):
        self.r = r
        self.g = g
        self.b = b
        self.a = a

    def read(self, bin):
        self.r, self.g, self.b, self.a = unpack("4B", bin)

    def write(self):
        return pack("4B", int(self.r), int(self.g), int(self.b), int(self.a))