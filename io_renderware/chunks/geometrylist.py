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

    def build(self, frame_list=None):
        armature = frame_list.armature if frame_list is not None else None
        for geometry in self.children[Geometry.ID_STAMP]:
            # In a .dff file, the armature is included in the SkinPLG as well
            # We ignore that here and hand down the armature of the frame list instead
            geometry.build(armature)