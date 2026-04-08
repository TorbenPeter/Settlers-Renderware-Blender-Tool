from struct import pack, unpack

class Triangle:
    """
    Triangle container
    """

    BYTE_SIZE = 8

    def __init__(self, vertex_a : int = None, vertex_b : int = None, vertex_c : int = None, material : int = None):
        self.vertex_a = vertex_a
        self.vertex_b = vertex_b
        self.vertex_c = vertex_c
        self.material = material

    def read(self, bin):
        self.vertex_b, self.vertex_a, self.material, self.vertex_c = unpack("HHHH", bin)

    def as_tuple(self):
        return (self.vertex_a, self.vertex_b, self.vertex_c)
    
    def write(self):
        return pack("HHHH", self.vertex_b, self.vertex_a, self.material, self.vertex_c)