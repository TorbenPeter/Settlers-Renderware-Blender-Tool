from .content import Content
from ..containers.triangle import Triangle
from ..tristrip import stripify
from struct import pack, unpack

class BinMeshPLG(Content):

    ID_STAMP = 0x0000050E

    def __init__(self, header):
        super().__init__(header)
        self.is_triangle_strip = False
        self.number_of_splits = 0
        self.number_of_indices = 0
        self.triangles = []
        self.material_ids = []
        self.tristrips = []

    # This is only read as a fallback for cases in which no faces are stored in the Geometry Struct
    def read(self, file):
        super().read(file)

        self.is_triangle_strip, self.number_of_splits, self.number_of_indices = unpack("III", self.content[:12])
        self.is_triangle_strip = bool(self.is_triangle_strip)

        pointer = 12

        if self.is_triangle_strip:
            for i in range(self.number_of_splits):
                number_of_indices, material = unpack("II", self.content[pointer:pointer+8])
                pointer += 8
                vertex_array = unpack("{}I".format(number_of_indices), self.content[pointer:pointer+number_of_indices*4])
                pointer += number_of_indices*4

                for vertex_index in range(len(vertex_array)-2):
                    if vertex_index & 1:
                        a, b, c = vertex_array[vertex_index:vertex_index+3][::-1]
                    else:
                        a, b, c = vertex_array[vertex_index:vertex_index+3]
                    if a != b and b != c and c != a:
                        self.triangles.append(Triangle(a, b, c, material))
                        # self.triangles.append(Triangle(a, b, c, i))
        else:
            for _ in range(self.number_of_splits):
                number_of_indices, material = unpack("II", self.content[pointer:pointer+8])
                pointer += 8
                for _ in range(number_of_indices//3):
                    a, b, c = unpack("III", self.content[pointer:pointer+12])
                    self.triangles.append(Triangle(a, b, c, material))
                    pointer += 12


    def fetch(self, face_splits):
        self.is_triangle_strip = True

        for material_id in range(len(face_splits)):
            for split in face_splits[material_id]:
                tristrip = stripify(split)
                self.tristrips.append(tristrip)
                self.material_ids.append(material_id)
                self.number_of_indices += len(tristrip)
                self.number_of_splits += 1

    def write(self):
        content = pack("III", 1, self.number_of_splits, self.number_of_indices)

        for i in range(self.number_of_splits):
            tristrip = self.tristrips[i]
            content += pack("II", len(tristrip), self.material_ids[i])
            content += pack("{}I".format(len(tristrip)), *tristrip)
        
        self.header.chunk_size = len(content)
        return self.header.write() + content