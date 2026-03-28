from .container import Container
from .struct import Struct
from .geometry import Geometry
from ..containers.header import Header
from struct import pack, unpack
import bpy

class GeometryList(Container):

    ID_STAMP = 0x0000001A

    def __init__(self, header):
        super().__init__(header)
        self.number_of_geometries = 0
        self.geometries = []

    def read(self, file):
        super().read(file)

        if not self.children[Struct.ID_STAMP]:
            return

        properties = self.children[Struct.ID_STAMP][0]
        self.number_of_geometries, = unpack("i", properties.content)

    def build(self, frame_list=None):
        # In a .dff file, the armature is included in the SkinPLG as well
        # We ignore that here and hand down the armature of the frame list instead
        armature = frame_list.armature if frame_list is not None else None

        for i in range(self.number_of_geometries):
            geometry = self.children[Geometry.ID_STAMP][i]
            geometry.build(armature)
            self.geometries.append(geometry)

    def fetch(self):

        objects = bpy.data.objects
        if bpy.context.collection is not None:
            objects = bpy.context.collection.objects
        
        for object in objects:
            if object.type == "MESH":
                geometry = Geometry(Header())
                geometry.fetch(object)
                self.geometries.append(geometry)

        self.number_of_geometries = len(self.geometries)

    def write(self):
        return b""