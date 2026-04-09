from .container import Container
from .struct import Struct
from .material import Material
from ..containers.header import Header
from struct import pack, unpack

# We are living in a Material world and I am a Material List
class MaterialList(Container):

    ID_STAMP = 0x00000008

    def __init__(self, header):
        super().__init__(header)
        self.number_of_materials = 0


    def read(self, file):
        super().read(file)

        properties = self.children[Struct.ID_STAMP][0]
        self.number_of_materials, = unpack("I", properties.content[:4])
        material_ids = unpack("{}i".format(self.number_of_materials), properties.content[4:4+self.number_of_materials*4])

        # TODO: Gather all materials from children into list. Merge, if applicable (only relevant if Material ID != -1)
        for material in self.children[Material.ID_STAMP]:
            pass


    def build(self, mesh):
        for material in self.children[Material.ID_STAMP]:
            material.build(mesh)


    def fetch(self, mesh):
        self.number_of_materials = len(mesh.materials)
        self.children[Material.ID_STAMP] = []
        for mesh_material in mesh.materials:
            material = Material(Header())
            material.fetch(mesh_material)
            self.children[Material.ID_STAMP].append(material)


    def write(self):
        content = b""
        struct = Struct(Header())
        struct.content += pack("I", self.number_of_materials)
        struct.content += pack("{}i".format(self.number_of_materials), *[-1]*self.number_of_materials)
        content += struct.write()

        for child in self.children[Material.ID_STAMP]:
            content += child.write()

        self.header.chunk_size = len(content)
        return self.header.write() + content