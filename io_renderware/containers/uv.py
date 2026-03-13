from struct import pack, unpack

class UV:
    """
    Texture coordinate container
    """

    BYTE_SIZE = 8

    def __init__(self, u : int = None, v : int = None):
        self.u = u
        self.v = v

    def read(self, bin):
        self.u, self.v = unpack("ff", bin)