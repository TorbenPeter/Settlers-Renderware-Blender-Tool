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
        False: Matrix.Identity(4),
        True: Matrix(((0, 1, 0), (-1, 0, 0), (0, 0, 1))).to_4x4() # Axis swap
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
            rotation = Matrix((unpack("fff", properties.content[(byte):(byte+12)]),
                              unpack("fff", properties.content[(byte+12):(byte+24)]),
                              unpack("fff", properties.content[(byte+24):(byte+36)])))
            position = Vector(unpack("fff", properties.content[(byte+36):(byte+48)]))

            matrix = rotation.transposed().to_4x4()
            matrix.translation = position

            frame = Frame(matrix)

            self.frames.append(frame)
            parent_index, = unpack("i", properties.content[(byte+48):(byte+52)])
            if parent_index >= 0:
                frame.parent = self.frames[parent_index]

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
                matrix = frame.get_world_matrix() @ permutation

                frame.bone = Bone(bone_id, matrix)

    def build(self):
        armature = bpy.data.armatures.new(name="Armature")
        self.armature = bpy.data.objects.new("Armature", armature)
        # TODO: Sometimes there might not be an active collection
        bpy.context.collection.objects.link(self.armature)
        bpy.context.view_layer.objects.active = self.armature
        self.armature["Local Space"] = self.local_space
        self.armature["Update Locals"] = self.update_locals
        bpy.ops.object.mode_set(mode="EDIT")
        for bone_id in self.bone_ids:
            for frame in self.frames:
                if frame.bone is not None and frame.bone.id == bone_id:
                    break
            bone_object = armature.edit_bones.new(str(frame.bone.id))
            if frame.parent is not None and frame.parent.bone is not None:
                parent_bone = armature.edit_bones[str(frame.parent.bone.id)]
                bone_object.parent = parent_bone

            bone_object.head = frame.bone.matrix.translation
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
            # bone_object.inherit_scale = 'NONE'
            bone_object.use_relative_parent = False
            bone_object.use_local_location = True
            bone_object.use_inherit_rotation = True
        for bone in armature.edit_bones:
            bone.select = False
            bone.select_head = False
            bone.select_tail = False
        bpy.ops.object.mode_set(mode="OBJECT")

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

        # There always has to be a base frame
        self.frames = [Frame(Matrix.Identity(4))]

        if len(bpy.data.armatures) == 0:
            self.number_of_frames = 1
            return
        
        # If a context is given, use that
        if bpy.context.object is not None and bpy.context.object.type == "ARMATURE":
            armature = bpy.context.object
        else:
            for armature in bpy.data.objects:
                if armature.data == bpy.data.armatures[0]:
                    break
            
        if "Local Space" in armature:
            self.local_space = armature["Local Space"]

        if "Update Locals" in armature:
            self.update_locals = armature["Update Locals"]

        for bone in armature.pose.bones:
            frame = Frame()

            bone_name = bone.name
            frame.bone = Bone(int(bone_name), bone.bone.matrix_local)
            frame.user_data = {**bone}

            # If bone names are in certain number ranges for effects etc. and no tag is set, apply one automatically
            # (Not done for animation bones "6..", since not all of them are tagged)
            if "tag" not in frame.user_data and len(bone_name) == 3 and bone_name.isdigit() and bone_name.startswith(("2", "3", "4")):
                frame.user_data["tag"] = bone_name

            if bone.parent is not None:
                frame.parent = self.frames[1 + armature.pose.bones.find(bone.parent.name)]
            
            self.frames.append(frame)
            self.bone_ids.append(bone.name)

        permutation = FrameList.LOCAL_MATRIX[self.local_space]
        for frame in self.frames:
            matrix = permutation @ frame.get_local_matrix() @ permutation.inverted()
            rotation = matrix.to_3x3().transposed()
            frame.matrix = Matrix.LocRotScale(matrix.translation, rotation, None)

        # Reorder frames according to DFS in bones