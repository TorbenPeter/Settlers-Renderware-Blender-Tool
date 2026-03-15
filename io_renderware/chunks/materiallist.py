from .container import Container
from .struct import Struct
from .material import Material
from struct import pack, unpack

class MaterialList(Container):

    ID_STAMP = 0x00000008

    def __init__(self, header):
        super().__init__(header)
        self.number_of_materials = 0
        self.materials = []

    def read(self, file):
        super().read(file)

        properties = self.children[Struct.ID_STAMP][0]
        self.number_of_materials, = unpack("I", properties.content[:4])
        material_ids = unpack("{}i".format(self.number_of_materials), properties.content[4:4+self.number_of_materials*4])

        # TODO: Gather all materials from children into list. Merge, if applicable
        # TODO: How?
        for material in self.children[Material.ID_STAMP]:
            pass

    def build(self, mesh):
        for material in self.children[Material.ID_STAMP]:
            material.build(mesh)