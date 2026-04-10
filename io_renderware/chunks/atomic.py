from .container import Container
from .struct import Struct
from .extension import Extension
from .particlestandardplg import ParticleStandardPLG
from ..containers.header import Header
from .materiallist import MaterialList
from .material import Material
from .materialeffectsplg import MaterialEffectsPLG
from .righttorender import RightToRender
from .skinplg import SkinPLG
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
        object = geometry_list.geometries[self.geometry_index].object
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
            if armature.pose.bones[bone_id].parent is not None and len(armature.pose.bones[bone_id].children) == 0:
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


    def fetch(self, geometry, frame_list, geometry_index):
        self.collision_test = True
        self.render = True
        self.geometry_index = geometry_index

        for constraint in geometry.object.constraints:
            if constraint.type == "CHILD_OF":
                if constraint.subtarget:
                    for index, frame in enumerate(frame_list.frames):
                        if frame.bone is not None and str(frame.bone.id) == constraint.subtarget:
                            self.frame_index = index
                            break
                    else:
                        self.frame_index = 0
                else:
                    self.frame_index = 0
                break
        else:
            self.frame_index = 0

        extension = Extension(Header())
        self.children[Extension.ID_STAMP] = [extension]

        # Attach Particles
        if "Particles" in geometry.object:
            particles = ParticleStandardPLG(Header())
            particles.fetch(geometry.object)
            extension.children[ParticleStandardPLG.ID_STAMP] = [particles]

        # Attach Material Effects
        if MaterialList.ID_STAMP in geometry.children:
            for material_list in geometry.children[MaterialList.ID_STAMP]:
                if Material.ID_STAMP in material_list.children:
                    for material in material_list.children[Material.ID_STAMP]:
                        if Extension.ID_STAMP in material.children:
                            for material_extension in material.children[Extension.ID_STAMP]:
                                if MaterialEffectsPLG.ID_STAMP in material_extension.children:
                                    # Create a "fake" MaterialEffectsPLG
                                    header = Header()
                                    struct = Struct(header)
                                    header.chunk_id_stamp = MaterialEffectsPLG.ID_STAMP
                                    header.chunk_size = 4
                                    struct.content = pack("I", 1)
                                    extension.children[MaterialEffectsPLG.ID_STAMP] = [struct]
                                    break

        # Attach Skin
        for modifier in geometry.object.modifiers:
            if modifier.type == "ARMATURE":
                right_to_render = RightToRender(Header())
                right_to_render.content += pack("II", SkinPLG.ID_STAMP, len(extension.children) + 1)
                extension.children[RightToRender.ID_STAMP] = [right_to_render]


    def write(self):
        content = b""

        struct = Struct(Header())
        flags = int(self.collision_test) | (int(self.render) << 2)
        struct.content += pack("4I", self.frame_index, self.geometry_index, flags, 0)
        content += struct.write()

        for extension in self.children[Extension.ID_STAMP]:
            content += extension.write()

        self.header.chunk_size = len(content)
        return self.header.write() + content