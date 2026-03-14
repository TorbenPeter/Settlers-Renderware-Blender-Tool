from .container import Container
from .framelist import FrameList
from .geometrylist import GeometryList
from .geometry import Geometry
from .atomic import Atomic
from .struct import Struct
from struct import pack, unpack
from mathutils import Matrix

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
            for geometry_list in self.children[GeometryList.ID_STAMP]:
                if frame_list is not None:
                    geometry_list.build(frame_list.armature)
                else:
                    geometry_list.build()

        if not import_frames or not import_geometries:
            return
        
        armature = frame_list.armature

        for index, geometry in enumerate(geometry_list.children[Geometry.ID_STAMP]):
        
            object = geometry.object
            parent_frame = frame_list.frames[self.frame_map[index]]
            
            # Set object parent frame
            constraint = object.constraints.new(type="CHILD_OF")
            constraint.use_scale_x = False
            constraint.use_scale_y = False
            constraint.use_scale_z = False
            constraint.target = armature

            if parent_frame.bone is not None:
                bone_id = str(parent_frame.bone.id)
                constraint.subtarget = bone_id
                if len(armature.pose.bones[bone_id].children) == 0:
                    armature.pose.bones[bone_id].custom_shape = object
                    armature.pose.bones[bone_id].use_custom_shape_bone_size = False

            # Reset inverse matrix
            constraint.inverse_matrix = Matrix.Identity(4)

        # TODO: Build atomics (i.e. particles, etc.)