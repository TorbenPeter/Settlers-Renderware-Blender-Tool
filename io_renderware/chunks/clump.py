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

    def read(self, file):
        super().read(file)
        properties = self.children[Struct.ID_STAMP][0]
        properties = unpack("iii", properties.content)
        self.number_of_atomics = properties[0]
        self.number_of_lights = properties[1]
        self.number_of_cameras = properties[2]
        self.frame_list = self.children[FrameList.ID_STAMP][0]
        self.geometry_list = self.children[GeometryList.ID_STAMP][0]

    def build(self, import_geometries=True, import_frames=True):
    
        if import_frames:
            self.frame_list.build()
        else:
            self.frame_list = None

        if import_geometries:
            self.geometry_list.build(self.frame_list)

        if not import_frames or not import_geometries:
            return
        
        for atomic in self.children[Atomic.ID_STAMP]:
            atomic.build(self.frame_list, self.geometry_list)

    def load(self):
        self.frame_list = FrameList(Header())
        self.frame_list.load()

        self.geometry_list = GeometryList(Header())
        self.geometry_list.load()

        self.number_of_atomics = self.geometry_list.number_of_geometries