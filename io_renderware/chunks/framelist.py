from .container import Container
from .struct import Struct
from .extension import Extension
from .hanimplg import HAnimPLG
from .userdataplg import UserDataPLG
from ..containers.header import Header
from ..containers.frame import Frame
from ..containers.bone import Bone
from ..util import get_current_armature
from struct import pack, unpack
import bpy
from mathutils import Vector, Matrix
from random import randint

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
                    frame.user_data = {**frame.user_data, **userdata.data}

            for hanimplg in extension.children[HAnimPLG.ID_STAMP]:
                if hanimplg.bone_info:
                    bones = {}
                    bone_parent_stack = []
                    for bone_info in hanimplg.bone_info:
                        bone_id, flags = bone_info[0], bone_info[2]
                        bone = Bone(bone_id)
                        if bone_parent_stack:
                            bone.parent = bone_parent_stack[-1]

                        push = flags & 0x02
                        pop = flags & 0x01
                        if not bone_parent_stack or push:
                            bone_parent_stack.append(bone_id)
                        else:
                            bone_parent_stack[-1] = bone_id
                        if pop:
                            bone_parent_stack.pop()

                        bones[bone_id] = bone
                        self.bone_ids.append(bone_id)
                    self.local_space = hanimplg.local_space_matrices
                    self.update_locals = hanimplg.update_modelling_matrices and hanimplg.update_ltms

                bone = bones[hanimplg.id]

                permutation = FrameList.LOCAL_MATRIX[self.local_space]
                matrix = frame.get_world_matrix() @ permutation

                bone.matrix = matrix

                frame.bone = bone

    def build(self):
        armature = bpy.data.armatures.new(name="Armature")
        self.armature = bpy.data.objects.new("Armature", armature)
        if bpy.context.collection is not None:
            bpy.context.collection.objects.link(self.armature)
        bpy.context.view_layer.objects.active = self.armature
        self.armature["Local Space"] = self.local_space
        self.armature["Update Locals"] = self.update_locals
        bpy.ops.object.mode_set(mode="EDIT")
        for bone_id in self.bone_ids:
            for frame in self.frames:
                if frame.bone is not None and frame.bone.id == bone_id:
                    break
            else:
                frame = None

            if frame is None:
                continue

            bone_object = armature.edit_bones.new(str(frame.bone.id))
            if frame.bone is not None and frame.bone.parent is not None:
                parent_bone = armature.edit_bones[str(frame.bone.parent)]
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
            else:
                frame = None

            if frame is None:
                continue

            for key, value in frame.user_data.items():
                self.armature.pose.bones[str(bone_id)][key] = value

    def fetch(self):

        # There always has to be a base frame
        self.frames = [Frame(Matrix.Identity(4))]
        self.number_of_frames = 1
        
        armature = get_current_armature()

        if armature is None:
            return

        self.armature = armature
        self.frames[0].user_data = {**armature}
            
        if "Local Space" in armature:
            self.local_space = armature["Local Space"]
            del self.frames[0].user_data["Local Space"]

        if "Update Locals" in armature:
            self.update_locals = armature["Update Locals"]
            del self.frames[0].user_data["Update Locals"]

        if len(armature.pose.bones) == 0:
            return
        
        # Find root bone. We assume that there is only one
        for root in armature.pose.bones:
            if root.parent is None:
                break
        
        permutation = FrameList.LOCAL_MATRIX[self.local_space]
        bone_list = [root] + [child for child in root.children_recursive if not child.hide]
        bone_names = {bone.name for bone in bone_list if bone.name.isdigit()}
        for bone in bone_list:
            frame = Frame()

            bone_name = bone.name

            # Rename all bones that don't have a qualifying name
            if not bone_name.isdigit():
                while True:
                    bone_name = str(randint(1000, 2999))
                    if bone_name not in bone_names:
                        break
                bone.name = bone_name
                bone_names.add(bone_name)

            frame.bone = Bone(int(bone_name))
            frame.bone.matrix = bone.bone.matrix_local @ permutation.inverted()
            frame.user_data = {**bone}

            # If bone names are in certain number ranges for effects etc. and no tag is set, apply one automatically
            # (Not done for animation bones "6..", since not all of them are tagged)
            if "tag" not in frame.user_data and len(bone_name) == 3 and bone_name.isdigit() and bone_name.startswith(("2", "3", "4")):
                frame.user_data["tag"] = bone_name

            if bone.parent is not None:
                frame.parent = self.frames[1 + bone_list.index(bone.parent)]
            else:
                frame.parent = self.frames[0]
            
            self.frames.append(frame)

        self.bone_ids = [int(bone.name) for bone in armature.pose.bones if not bone.hide]

        for frame in self.frames:
            matrix = frame.get_local_matrix()
            rotation = matrix.to_3x3().transposed()
            frame.matrix = Matrix.LocRotScale(matrix.translation, rotation, None)

        self.number_of_frames = len(self.frames)

    def write(self):

        content = b""
        
        struct = Struct(Header())
        extensions = []
        struct.content += pack("i", self.number_of_frames)
        for frame_index, frame in enumerate(self.frames):
            rotation = frame.matrix.to_3x3()
            position = frame.matrix.translation
            for row in rotation.row:
                struct.content += pack("fff", *row)
            struct.content += pack("fff", *position)
            if frame.parent is None:
                struct.content += pack("i", -1)
            else:
                struct.content += pack("i", self.frames.index(frame.parent))
            if self.update_locals:
                flags = 0x00003
            elif frame_index == 0:
                flags = 0x20003
            else:
                flags = 0x00000
            struct.content += pack("I", flags)

            extension = Extension(Header())
            if frame_index > 0:
                hanimplg = HAnimPLG(Header())
                hanimplg.id = frame.bone.id
                hanimplg.number_of_bones = 0

                if frame_index == 1:
                    hanimplg.number_of_bones = len(self.bone_ids)
                    hanimplg.update_modelling_matrices = self.update_locals
                    hanimplg.update_ltms = self.update_locals
                    hanimplg.local_space_matrices = self.local_space
                    for bone_index, bone_id in enumerate(self.bone_ids):
                        bone = self.armature.pose.bones[str(bone_id)]
                        push = bone.parent is not None and bone != bone.parent.children[-1]
                        pop = len(bone.children) == 0
                        flags = int(push) << 1 | int(pop)
                        hanimplg.bone_info.append((bone_id, bone_index, flags))

                extension.children[HAnimPLG.ID_STAMP] = [hanimplg]

            if frame.user_data:
                userdataplg = UserDataPLG(Header())
                userdataplg.data = {**frame.user_data}
                extension.children[UserDataPLG.ID_STAMP] = [userdataplg]

            extensions.append(extension)

        content += struct.write()
        for extension in extensions:
            content += extension.write()

        self.header.chunk_size = len(content)
        return self.header.write() + content