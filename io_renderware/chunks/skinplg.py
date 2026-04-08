from .content import Content
from .framelist import FrameList
from struct import pack, unpack
from ..util import apply_vertex_remap
from itertools import combinations
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

        if True:
            return

        _, self.number_of_groups, self.number_of_remaps = unpack("3I", self.content[pointer:pointer+12])

        # if self.number_of_groups == 0:
        #     return

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
        # print(self.used_bones)
        # print()
        # self.bone_remap_indices = [-1] + list(range(self.number_of_used_bones))
        # self.bone_remap_indices = list(range(self.number_of_bones))

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

        for polygon in object.data.polygons:
            if polygon.material_index == 2:
                for i, vertex in enumerate(polygon.vertices):
                    print(self.vertex_bone_map[vertex], self.vertex_weights[vertex])
                print()

        for vertex_id, (vertex_bones, vertex_weights) in enumerate(zip(self.vertex_bone_map, self.vertex_weights)):
            for bone_index, weight in zip(vertex_bones, vertex_weights):
                if bone_index > 0:
                    bone = armature.pose.bones[bone_index]
                    object.vertex_groups[bone.name].add((vertex_id,), weight, 'ADD')


    def fetch(self, object, vertex_remap, face_splits, number_of_vertices):

        class Graph:
            def __init__(self, vertices : list[int]):
                self.vertices = vertices
                self.adjacency = {vertex: set() for vertex in vertices}

            def add_edge(self, u : int, v : int) -> None:
                # Undirected graph
                self.adjacency[u].add(v)
                self.adjacency[v].add(u)

        # Brown, J. Randall. “Chromatic Scheduling and the Chromatic Number Problem.” Management Science 19, no. 4 (1972)
        def graph_coloring(graph : Graph):
            n = len(graph.vertices) - 1
            vertices = sorted(graph.vertices, key=lambda x: len(graph.adjacency[x]), reverse=True)
            color = {vertex: -1 for vertex in vertices}
            color[vertices[0]] = 0
            i = 1
            k = n + 1
            q = 0
            U = set()
            L = {vertex: 0 for vertex in vertices}
            U = {vertex: set() for vertex in vertices}
            update_U = True
            # Solutions are generated while the root of the solution tree is not reached
            while i > 0:

                # Get all available colors
                if update_U:
                    U[i] = set(range(q+2)) - { c for c in range(k) if c in { color[vertex] for vertex in graph.adjacency[vertices[i]] } }
            
                # If there are no available colors, backtrack
                if len(U[i]) == 0:
                    i -= 1
                    q = L[i]
                    update_U = False

                else:
                    # Take the first available color
                    j = min(U[i])
                    color[vertices[i]] = j
                    U[i].remove(j)

                    # We need at most k colors
                    if j < k:
                        if j > q:
                            q += 1
                        
                        if i == n:
                            k = q
                            index = 0
                            while color[vertices[index]] != k:
                                index += 1
                            i = index - 1
                            q = k - 1
                            update_U = False
                        else:
                            L[i] = q
                            # A new vertex is selected to be colored
                            i += 1
                            update_U = True

                    # If there are more than the maximum number of colors, backtrack
                    else:
                        i -= 1
                        q = L[i]
                        update_U = False

            return color

        self.number_of_vertices = number_of_vertices

        armature = None
        for modifier in object.modifiers:
            if modifier.type == "ARMATURE":
                armature = modifier.object

        if armature is None:
            return
        
        self.number_of_bones = len(armature.pose.bones)

        # We use two indices here:
        # 0. is from the original material split
        # 1. is the split from the armature split. This is only relevant if the number of bones for a single material exceeds MAX_NUMBER_OF_BONES_PER_GROUP
        # Since vertices may be affected by multiple bones, they may be part of multiple splits
        vertex_split = { vertex: [material, frozenset()] for material, triangles_lists in face_splits.items() for triangles in triangles_lists for triangle in triangles for vertex in triangle }
        material_bones = { material: set() for material, _ in face_splits.items() }

        self.vertex_bone_map = [[] for _ in object.data.vertices]
        self.vertex_weights = [[] for _ in object.data.vertices]
        # used_bones are in the order of appearance when iterating the vertices in order
        for vertex in object.data.vertices:
            for group in vertex.groups:

                bone_name = object.vertex_groups[group.group].name
                bone_id = armature.pose.bones.find(bone_name)
                self.vertex_bone_map[vertex.index].append(bone_id)
                self.vertex_weights[vertex.index].append(group.weight)
                self.max_number_of_vertex_weights = max(self.max_number_of_vertex_weights, len(self.vertex_bone_map[vertex.index]))

                if bone_id not in self.used_bones:
                    self.used_bones.append(bone_id)

                # Count number of bones per material
                # If the number exceeds MAX_NUMBER_OF_BONES_PER_GROUP we need to split
                material_bones[vertex_split[vertex.index][0]].add(bone_id)

        self.number_of_used_bones = len(self.used_bones)

        for bone_list in self.vertex_bone_map:
            bone_list.extend([0]*(4-len(bone_list)))
        for weight_list in self.vertex_weights:
            weight_list.extend([0]*(4-len(weight_list)))

        apply_vertex_remap(self.vertex_bone_map, vertex_remap, number_of_vertices)
        apply_vertex_remap(self.vertex_weights, vertex_remap, number_of_vertices)

        local_space = False
        if "Local Space" in armature:
            local_space = armature["Local Space"]
        permutation = FrameList.LOCAL_MATRIX[local_space]
        for bone in armature.data.bones:
            self.transforms.append(permutation @ bone.matrix_local.inverted())

        if self.number_of_used_bones == 0:
            return

        for material, bones in material_bones.items():
            if len(bones) > SkinPLG.MAX_NUMBER_OF_BONES_PER_GROUP:

                groups = [set()]
                triangles = face_splits[material][0]

                # Each vertex in a triangle can be affected by up to 4 bones
                set_size_bins = [list() for _ in range(12)]
                for triangle in triangles:
                    triangle_group = set(bone for vertex in triangle for bone, weight in zip(self.vertex_bone_map[vertex], self.vertex_weights[vertex]) if weight > 0.0)
                    if len(triangle_group) > 0:
                        set_size_bins[len(triangle_group) - 1].append(triangle_group)

                # Cover all sets greedily
                while set_size_bins:
                    set_bin = set_size_bins.pop()
                    while set_bin:
                        bone_set = set_bin.pop()
                        for group in groups:
                            if group.intersection(bone_set) == bone_set:
                                break
                        else:
                            if len(groups[-1].union(bone_set)) <= SkinPLG.MAX_NUMBER_OF_BONES_PER_GROUP:
                                groups[-1].update(bone_set)
                            else:
                                groups.append(bone_set)

                face_splits[material] += [[] for _ in range(len(groups) - 1)]
                for i in reversed(range(len(triangles))):
                    triangle = triangles[i]
                    triangle_group = set(bone for vertex in triangle for bone, weight in zip(self.vertex_bone_map[vertex], self.vertex_weights[vertex]) if weight > 0.0)
                    for j in range(len(groups)):
                        group = groups[j]
                        if group.intersection(triangle_group) == triangle_group:
                            face_splits[material][j].append(triangles.pop(i))
                            break
        
                # Add groups to self.bone_groups
                self.bone_groups.extend(groups)
                self.number_of_groups = len(self.bone_groups)

        if self.number_of_groups == 0:
            return
        
        self.bone_remap_indices = []
        remap_index = 0
        for i in range(self.number_of_bones):
            if i in self.used_bones:
                self.bone_remap_indices.append(remap_index)
                remap_index = (remap_index + 1) % SkinPLG.MAX_NUMBER_OF_BONES_PER_GROUP
            else:
                self.bone_remap_indices.append(-1)

        # Solve bone remapping with graph coloring
        graph = Graph([bone for bone in range(self.number_of_bones)])
        for group in groups:
            for edge in combinations(group, 2):
                graph.add_edge(*edge)

        coloring = graph_coloring(graph)

        for bone, remap in coloring.items():
            if bone in self.used_bones:
                self.bone_remap_indices[bone] = remap

        # RLE for groups and remaps
        for group_index in range(len(self.bone_groups)):
            group = sorted(self.bone_groups[group_index])
            remap = [[group[0], 1]]
            for i in range(len(group) - 1):
                if group[i+1] == group[i] + 1:
                    remap[-1][1] += 1
                else:
                    remap.append([group[i+1], 1])

            self.bone_groups[group_index] = (len(self.bone_remaps), len(remap))
            self.bone_remaps.extend(remap)

        self.number_of_remaps = len(self.bone_remaps)

        # print(groups)
        # print(self.bone_remap_indices)
        # print(self.bone_groups)
        # print(self.bone_remaps)
        # print()

        # for group in self.bone_groups:
        #     mappings = self.bone_remaps[group[0]:group[0]+group[1]]
        #     bones = []
        #     for mapping in mappings:
        #         bones = bones + list(self.bone_remap_indices[mapping[0]:mapping[0]+mapping[1]])
        #     print(bones, len(bones))

    
    def write(self):
        content = b""

        content += pack("4B", self.number_of_bones, self.number_of_used_bones, self.max_number_of_vertex_weights, 0)
        content += pack("{}b".format(self.number_of_used_bones), *self.used_bones)

        for i in range(self.number_of_vertices):
            content += pack("4b", *self.vertex_bone_map[i])

        for i in range(self.number_of_vertices):
            content += pack("4f", *self.vertex_weights[i])

        for i in range(self.number_of_bones):
            transform = self.transforms[i].transposed()
            for row in transform:
                content += pack("4f", *row)

        content += pack("3I", SkinPLG.MAX_NUMBER_OF_BONES_PER_GROUP, self.number_of_groups, self.number_of_remaps)

        if self.number_of_groups > 0:
            content += pack("{}b".format(self.number_of_bones), *self.bone_remap_indices)
            for i in range(self.number_of_groups):
                content += pack("bb", *self.bone_groups[i])
            for i in range(self.number_of_remaps):
                content += pack("bb", *self.bone_remaps[i])

        self.header.chunk_size = len(content)
        return self.header.write() + content