from .container import Container
from .framelist import FrameList
from .geometrylist import GeometryList
from .atomic import Atomic
from .struct import Struct
from struct import pack, unpack

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
        self.frame_map = {}

    def read(self, file):
        super().read(file)
        properties = self.children[Struct.ID_STAMP][0]
        properties = unpack("iii", properties.content)
        self.number_of_atomics = properties[0]
        self.number_of_lights = properties[1]
        self.number_of_cameras = properties[2]

        # Fetch all atomics and assign all frames to their geometries
        for atomic in self.children[Atomic.ID_STAMP]:
            self.frame_map[atomic.geometry_index] = atomic.frame_index

    def build(self, import_geometries=True, import_frames=True):
        frame_list = None
        if import_frames:
            for frame_list in self.children[FrameList.ID_STAMP]:
                frame_list.build()

        if import_geometries:   
            # Create the geometry with a pointer towards its respective frame. Parent information should be kept
            for geometry_list in self.children[GeometryList.ID_STAMP]:
                if frame_list is not None:
                    geometry_list.build(frame_list.armature, frame_list.frames, self.frame_map)

        # TODO: Build atomics (i.e. patricles)