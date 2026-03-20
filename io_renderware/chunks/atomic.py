from .container import Container
from .struct import Struct
from .geometry import Geometry
from .extension import Extension
from .particlestandardplg import ParticleStandardPLG
from struct import pack, unpack
from mathutils import Matrix

class Atomic(Container):

    ID_STAMP = 0x00000014

    def __init__(self, header):
        super().__init__(header)
        self.frame_index = 0
        self.geometry_index = 0
        self.collision_test = False
        self.render = False

    def read(self, file):
        super().read(file)
        properties = self.children[Struct.ID_STAMP][0]
        self.frame_index, self.geometry_index, flags, _ = unpack("iiii", properties.content)
        self.collision_test = bool(flags & 0x01)
        self.render = bool(flags & 0x04)

    def build(self, frame_list, geometry_list):

        armature = frame_list.armature
        object = geometry_list.children[Geometry.ID_STAMP][self.geometry_index].object
        parent_frame = frame_list.frames[self.frame_index]
        
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

        extensions = self.children[Extension.ID_STAMP]
        for extension in extensions:
            for child_type, children in extension.children.items():
                if child_type == ParticleStandardPLG.ID_STAMP:
                    for child in children:
                        child.build(object)