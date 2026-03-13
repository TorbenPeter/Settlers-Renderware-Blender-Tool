from .container import Container
from .struct import Struct
from .geometry import Geometry
from struct import pack, unpack

class GeometryList(Container):

    ID_STAMP = 0x0000001A

    def __init__(self, header):
        super().__init__(header)
        self.number_of_geometries = 0

    def read(self, file):
        super().read(file)
        properties = self.children[Struct.ID_STAMP][0]
        self.number_of_geometries, = unpack("i", properties.content)

    def build(self, armature, frame_list, frame_map):
        # TODO: Handle the case where no frame was given
        for index, geometry in enumerate(self.children[Geometry.ID_STAMP]):
            geometry.build(armature, frame_list[frame_map[index]])