from .content import Content
from .framelist import FrameList
from struct import pack, unpack
from collections import defaultdict
from mathutils import Matrix
import bpy

class SkinPLG(Content):

    ID_STAMP = 0x00000116
    MAX_NUMBER_OF_BONES_PER_GROUP = 58

    def __init__(self, header):
        super().__init__(header)
        self.number_of_vertices = 0
        self.number_of_bones = 0
        self.number_of_used_bones = 0
        self.max_number_of_vertex_weights = 0
        self.used_bones = []
        self.vertex_bone_map = []
        self.vertex_weights = []
        self.transforms = []
        self.number_of_groups = 0
        self.number_of_remaps = 0
        self.bone_remap_indices = ()
        self.bone_groups = []
        self.bone_remaps = []
        
    def read(self, file, number_of_vertices = None):

        if number_of_vertices is None:
            super().read(file)
            return
        
        self.number_of_vertices = number_of_vertices
        self.number_of_bones, self.number_of_used_bones, self.max_number_of_vertex_weights, _ = unpack("4B", self.content[:4])

        self.used_bones = list(unpack("{}b".format(self.number_of_used_bones), self.content[4:4+self.number_of_used_bones]))

        pointer = 4+self.number_of_used_bones
        for _ in range(self.number_of_vertices):
            self.vertex_bone_map.append(unpack("4b", self.content[pointer:pointer+4]))
            pointer += 4

        for _ in range(self.number_of_vertices):
            self.vertex_weights.append(unpack("4f", self.content[pointer:pointer+16]))
            pointer += 16

        for _ in range(self.number_of_bones):
            transform = Matrix((unpack("ffff", self.content[pointer:pointer+16]),
                              unpack("ffff", self.content[pointer+16:pointer+32]),
                              unpack("ffff", self.content[pointer+32:pointer+48]),
                              unpack("ffff", self.content[pointer+48:pointer+64]))).transposed()
            # Noise values in last row?
            transform.row[3] = (0, 0, 0, 1)
            self.transforms.append(transform)
            pointer += 64

        # Hereafter comes the bone remapping which is irrelevant for the import

        _, self.number_of_groups, self.number_of_remaps = unpack("3I", self.content[pointer:pointer+12])

        if self.number_of_groups == 0:
            return

        pointer += 12
        self.bone_remap_indices = unpack("{}b".format(self.number_of_bones), self.content[pointer:pointer+self.number_of_bones])
        pointer += self.number_of_bones
        # TODO: Read this stuff and see what it could mean and how it was constructed
        # TODO: Not needed for import, but for export
        for _ in range(self.number_of_groups):
            self.bone_groups.append(unpack("bb", self.content[pointer:pointer+2]))
            pointer += 2

        for _ in range(self.number_of_remaps):
            self.bone_remaps.append(unpack("bb", self.content[pointer:pointer+2]))
            pointer += 2

        print(self.bone_remap_indices)
        print(self.bone_groups)
        print(self.bone_remaps)
        print(self.used_bones)
        print()

        for group in self.bone_groups:
            mappings = self.bone_remaps[group[0]:group[0]+group[1]]
            bones = []
            for mapping in mappings:
                bones = bones + list(self.bone_remap_indices[mapping[0]:mapping[0]+mapping[1]])
            print(bones, len(bones))

        # Indices are just the bone indices (-1 if unused)
        # Groups run-length define a group by the index and run of the bone remaps array
        # For example: Group (1, 2) and Remaps ((5, 3), (1, 4), (9, 11), (5, 2)) define a group bones[1:1+4] + bones[9:9+11]

    def build(self, object, armature):
        modifier = object.modifiers.new(type='ARMATURE', name="Armature")
        modifier.object = armature

        local_space = False
        if "Local Space" in armature:
            local_space = armature["Local Space"]
        permutation = FrameList.LOCAL_MATRIX[local_space]
        bpy.ops.object.mode_set(mode="EDIT")
        for i, transform in enumerate(self.transforms):
            armature.data.edit_bones[i].matrix = transform.inverted() @ permutation
        bpy.ops.object.mode_set(mode="OBJECT")

        # NOTE: Technically not correct, but helps import some scuffed models
        if not self.used_bones:
            for bone in armature.pose.bones:
                object.vertex_groups.new(name=bone.name)
        else:
            for bone_index in self.used_bones:
                bone = armature.pose.bones[bone_index]
                object.vertex_groups.new(name=bone.name)

        for vertex_id, (vertex_bones, vertex_weights) in enumerate(zip(self.vertex_bone_map, self.vertex_weights)):
            for bone_index, weight in zip(vertex_bones, vertex_weights):
                if bone_index > 0:
                    bone = armature.pose.bones[bone_index]
                    object.vertex_groups[bone.name].add((vertex_id,), weight, 'ADD')

    def fetch(self, object, vertex_remap : dict ={}):
        
        armature = None
        for modifier in object.modifiers:
            if modifier.type == "ARMATURE":
                armature = modifier.object

        if armature is None:
            return
        
        self.number_of_bones = len(armature.pose.bones)

        # used_bones are in the order of appearance when iterating the vertices in order
        # TODO: Also compute the bones each vertex is affected by
        for vertex in object.data.vertices:
            for group in vertex.groups:
                bone_name = object.vertex_groups[group.group].name
                bone_id = armature.pose.bones.find(bone_name)
                if bone_id not in self.used_bones:
                    self.used_bones.append(bone_id)

        self.number_of_used_bones = len(self.used_bones)

        # print(self.used_bones)