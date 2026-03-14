from .container import Container
from .struct import Struct
from .extension import Extension
from .hanimplg import HAnimPLG
from .userdataplg import UserDataPLG
from ..containers.vector3d import Vector3d
from ..containers.rotation3d import Rotation3d
from ..containers.frame import Frame
from ..containers.bone import Bone
from struct import pack, unpack
import bpy
from mathutils import Vector, Matrix

class FrameList(Container):

    ID_STAMP = 0x0000000E

    # Basis change dependent on whether or not rotation is in local space (True) or not (False)
    LOCAL_MATRIX = {
        False: Matrix.Identity(3),
        True: Matrix(((0, -1, 0), (1, 0, 0), (0, 0, 1))) # Axis swap
    }

    def __init__(self, header):
        super().__init__(header)
        self.number_of_frames = 0
        self.frames = []
        self.bone_ids = []
        self.armature = None
        self.local_space = False
        self.update_locals = False

    def read(self, file):
        super().read(file)
        properties = self.children[Struct.ID_STAMP][0]
        self.number_of_frames, = unpack("i", properties.content[:4])
        for byte in range(4, properties.header.chunk_size, 56):
            rotation = Rotation3d()
            rotation.read(properties.content[byte:(byte+36)])
            position = Vector3d()
            position.read(properties.content[(byte+36):(byte+48)])
            frame = Frame(rotation, position)
            self.frames.append(frame)
            parent_index, = unpack("i", properties.content[(byte+48):(byte+52)])
            if parent_index >= 0:
                frame.parent = self.frames[parent_index]
            # TODO: What to do with those flags?
            # matrix_flags, = unpack("i", properties.content[(byte+52):(byte+56)])
            # property1 = bool(matrix_flags & 0x000001) and bool(matrix_flags & 0x000002)
            # property2 = bool(matrix_flags & 0x020000)

        # Get all bones
        for frame_id, extension in enumerate(self.children[Extension.ID_STAMP]):
            frame = self.frames[frame_id]
            for userdata in extension.children[UserDataPLG.ID_STAMP]:
                if userdata.data:
                    frame.user_data = {**userdata.data}

            for hanimplg in extension.children[HAnimPLG.ID_STAMP]:
                if hanimplg.bone_info:
                    for bone_info in hanimplg.bone_info:
                        self.bone_ids.append(bone_info[0])
                    self.local_space = hanimplg.local_space_matrices
                    self.update_locals = hanimplg.update_modelling_matrices and hanimplg.update_ltms

                bone_id = hanimplg.id

                permutation = FrameList.LOCAL_MATRIX[self.local_space]

                # Inverse by transposing
                frame_space = (permutation @ frame.get_canonical_rotation()).transposed()

                canonical_position = frame.get_canonical_position()
                head = Vector3d(*canonical_position)
                matrix = Matrix.LocRotScale(canonical_position, frame_space, (1, 1, 1))
                frame.bone = Bone(bone_id, head, matrix)

    def build(self):
        armature = bpy.data.armatures.new(name="Armature")
        self.armature = bpy.data.objects.new("Armature", armature)
        bpy.context.collection.objects.link(self.armature)
        bpy.context.view_layer.objects.active = self.armature
        self.armature["Local Space"] = self.local_space
        self.armature["Update Locals"] = self.update_locals
        bpy.ops.object.mode_set(mode='EDIT')
        for bone_id in self.bone_ids:
            for frame in self.frames:
                if frame.bone is not None and frame.bone.id == bone_id:
                    break
            bone_object = armature.edit_bones.new(str(frame.bone.id))
            if frame.parent is not None and frame.parent.bone is not None:
                parent_bone = armature.edit_bones[str(frame.parent.bone.id)]
                bone_object.parent = parent_bone
            bone_object.head = Vector(frame.bone.head.as_tuple())
            bone_object.matrix = frame.bone.matrix
            # Blender will insert a small Z length by default, which is wrong when the RenderWare
            # Up direction is Y
            if bone_object.head.length <= 0:
                # Adjust for local space
                if self.local_space:
                    bone_object.head[0] = -1e-8
                    bone_object.matrix[0][3] = -1e-8
                else:
                    bone_object.head[1] = -1e-8
                    bone_object.matrix[1][3] = -1e-8
            bone_object.length = 10

            bone_object.use_connect = False
            bone_object.inherit_scale = 'NONE'
            bone_object.use_relative_parent = False
            bone_object.use_local_location = True
            bone_object.use_inherit_rotation = True

            frame.bone.object = bone_object
        for bone in armature.edit_bones:
            bone.select = False
            bone.select_head = False
            bone.select_tail = False
        bpy.ops.object.mode_set(mode='OBJECT')

        frame = self.frames[0]
        for key, value in frame.user_data.items():
            self.armature[key] = value

        # Can't be in edit mode for this
        for bone_id in self.bone_ids:
            for frame in self.frames:
                if (frame.bone is not None and frame.bone.id == bone_id):
                    break
            
            for key, value in frame.user_data.items():
                self.armature.pose.bones[str(bone_id)][key] = value

    def load(self):
        # TODO: If bone names are in certain number ranges for effects etc. and no tag is set, apply one automatically
        # (Don't do this for animation bones, since not all of them are tagged)
        return super().load()