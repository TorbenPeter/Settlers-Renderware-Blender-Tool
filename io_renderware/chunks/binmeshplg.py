from .content import Content
from ..containers.triangle import Triangle
from ..tristrip import stripify
from struct import pack, unpack

class BinMeshPLG(Content):

    ID_STAMP = 0x0000050E

    def __init__(self, header):
        super().__init__(header)
        self.is_triangle_strip = False
        self.number_of_meshes = 0
        self.number_of_indices = 0
        self.triangles = []

    # This is only read as a fallback for cases in which no faces are stored in the Geometry Struct
    def read(self, file):
        super().read(file)

        self.is_triangle_strip, self.number_of_meshes, self.number_of_indices = unpack("III", self.content[:12])
        self.is_triangle_strip = bool(self.is_triangle_strip)

        # I ain't parsin' no triangle strips
        if self.is_triangle_strip:
            return
        
        pointer = 12
        for _ in range(self.number_of_meshes):
            number_of_indices, material = unpack("II", self.content[pointer:pointer+8])
            pointer += 8
            for _ in range(number_of_indices//3):
                a, b, c = unpack("III", self.content[pointer:pointer+12])
                self.triangles.append(Triangle(a, b, c, material))
                pointer += 12


    def fetch(self):
        # TODO: Braucht die Triangles schon fertig gruppiert
        tristrip = stripify(self.triangles)