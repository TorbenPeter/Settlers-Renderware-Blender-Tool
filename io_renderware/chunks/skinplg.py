from .content import Content
from struct import pack, unpack

class SkinPLG(Content):

    ID_STAMP = 0x00000116
    MAX_NUMBER_OF_BONES_PER_GROUP = 58

    def __init__(self, header):
        super().__init__(header)
        self.number_of_vertices = 0
        self.number_of_bones = 0
        self.number_of_used_bones = 0
        self.max_number_of_vertex_weights = 0
        self.used_bones = ()
        self.vertex_bone_map = []
        self.vertex_weights = []
        self.number_of_groups = 0
        self.number_of_remaps = 0
        self.bone_remap_indices = []
        self.bone_groups = []
        self.bone_remaps = []
        
    def read(self, file, number_of_vertices = None):

        if number_of_vertices is None:
            super().read(file)
            return
        
        self.number_of_vertices = number_of_vertices
        self.number_of_bones, self.number_of_used_bones, self.max_number_of_vertex_weights, _ = unpack("4B", self.content[:4])

        self.used_bones = unpack("{}b".format(self.number_of_used_bones), self.content[4:4+self.number_of_used_bones])

        pointer = 4+self.number_of_used_bones
        for _ in range(self.number_of_vertices):
            self.vertex_bone_map.append(unpack("4b", self.content[pointer:pointer+4]))
            pointer += 4

        for _ in range(self.number_of_vertices):
            self.vertex_weights.append(unpack("4f", self.content[pointer:pointer+16]))
            pointer += 16

        # Ignore bone transformation matrices, as they are identical to HAnimPLG
        pointer += self.number_of_bones*4**3

        _, self.number_of_groups, self.number_of_remaps = unpack("3I", self.content[pointer:pointer+12])

        if self.number_of_groups == 0:
            return

        pointer += 12
        self.bone_remap_indices = unpack("{}b".format(self.number_of_bones), self.content[pointer:pointer+self.number_of_bones])
        pointer += self.number_of_bones
        # TODO: Read this stuff and see what it could mean and how it was constructed
        # TODO: Not needed for import, but for export

    def build(self, object, armature):
        modifier = object.modifiers.new(type='ARMATURE', name="Armature")
        modifier.object = armature

        for bone_index in self.used_bones:
            bone = armature.pose.bones[bone_index]
            object.vertex_groups.new(name=bone.name)

        for vertex_id, (vertex_bones, vertex_weights) in enumerate(zip(self.vertex_bone_map, self.vertex_weights)):
            for bone_index, weight in zip(vertex_bones, vertex_weights):
                if bone_index > 0:
                    bone = armature.pose.bones[bone_index]
                    object.vertex_groups[bone.name].add((vertex_id,), weight, 'ADD')

    def fetch(self):
        # TODO: self.used_bones are in the order of appearance when iterating the vertices in order
        # TODO: Maybe this order also determines the splits
        return super().fetch()