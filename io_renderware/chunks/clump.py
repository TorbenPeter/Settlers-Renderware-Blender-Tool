from .container import Container
from .framelist import FrameList
from .geometrylist import GeometryList
from .atomic import Atomic
from .struct import Struct
from ..containers.header import Header
from struct import pack, unpack
import bpy

class Clump(Container):

    """
    DFF Clumps are structured as follows:
    
    1. A Struct that contains:
        a. The number of atomics
        b. The number of lights
        c. The number of cameras
    as int32
    
    2. A Frame List
    
    3. A Geometry List
    
    4. Several Atomics, as specified by the leading struct
    
    5. Several Lights, as specified by the leading struct
    
    6. Several Cameras, as specified by the leading struct
    
    Note: Lights and Cameras are not handled in this version, don't import scenes
    """

    ID_STAMP = 0x00000010

    def __init__(self, header):
        super().__init__(header)
        self.number_of_atomics = 0
        self.number_of_lights = 0
        self.number_of_cameras = 0
        self.frame_list = None
        self.geometry_list = None
        self.atomics = []

    def read(self, file):
        super().read(file)
        properties = self.children[Struct.ID_STAMP][0]
        properties = unpack("III", properties.content)
        self.number_of_atomics = properties[0]
        self.number_of_lights = properties[1]
        self.number_of_cameras = properties[2]
        if self.children[FrameList.ID_STAMP]:
            self.frame_list = self.children[FrameList.ID_STAMP][0]
        if self.children[GeometryList.ID_STAMP]:
            self.geometry_list = self.children[GeometryList.ID_STAMP][0]
        if self.children[Atomic.ID_STAMP]:
            self.atomics = self.children[Atomic.ID_STAMP]

    def build(self, import_geometries=True, import_frames=True):
    
        if import_frames and self.frame_list is not None:
            self.frame_list.build()
        else:
            self.frame_list = None
            import_frames = False

        if import_geometries and self.geometry_list is not None:
            self.geometry_list.build(self.frame_list)
        else:
            import_geometries = False

        if not import_frames or not import_geometries:
            return
        
        for atomic in self.atomics:
            atomic.build(self.frame_list, self.geometry_list)

    def fetch(self):
        self.frame_list = FrameList(Header())
        self.frame_list.fetch()

        self.geometry_list = GeometryList(Header())
        self.geometry_list.fetch()

        self.number_of_atomics = self.geometry_list.number_of_geometries

    def write(self):
        content = b""
        struct = Struct(Header())
        struct.content += pack("III", self.number_of_atomics, self.number_of_lights, self.number_of_cameras)
        content += struct.write()
        content += self.frame_list.write()
        content += self.geometry_list.write()
        self.header.chunk_size = len(content)
        return self.header.write() + content