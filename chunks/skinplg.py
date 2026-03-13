from .content import Content
from struct import pack, unpack

class SkinPLG(Content):

    ID_STAMP = 0x00000116

    def __init__(self, header):
        super().__init__(header)
        self.number_of_vertices = 0
        self.number_of_bones = 0
        self.number_of_used_bones = 0
        self.max_number_of_vertex_weights = 0
        self.used_bones = ()
        self.vertex_bone_map = []
        self.vertex_weights = []
        
    def read(self, file, number_of_vertices = None):

        if number_of_vertices is None:
            super().read(file)
            return
        
        self.number_of_vertices = number_of_vertices
        self.number_of_bones, self.number_of_used_bones, self.max_number_of_vertex_weights, _ = unpack("4B", self.content[:4])

        self.used_bones = unpack("{}B".format(self.number_of_used_bones), self.content[4:4+self.number_of_used_bones])

        pointer = 4+self.number_of_used_bones
        for _ in range(self.number_of_vertices):
            self.vertex_bone_map.append(unpack("4B", self.content[pointer:pointer+4]))
            pointer += 4

        # NOTE: used bones are in the order of appearence from a vertex point of view
        # print(self.used_bones)
        # print(test_bone_order_list)

        for _ in range(self.number_of_vertices):
            self.vertex_weights.append(unpack("4f", self.content[pointer:pointer+16]))
            pointer += 16

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
                    object.vertex_groups[bone.name].add([vertex_id], weight, 'ADD')