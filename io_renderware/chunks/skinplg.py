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


    def fetch(self, object, vertex_remap, face_splits, number_of_vertices):

        # In order to create a valid bone remapping, we compute a graph coloring on all used bones with
        # their membership to a specific group as constraint
        # Since a group cannot be larger than MAX_NUMBER_OF_BONES_PER_GROUP, the constraint graph cannot
        # have a max degree that exceeds MAX_NUMBER_OF_BONES_PER_GROUP - 1, which means that we can always
        # find a coloring with at most MAX_NUMBER_OF_BONES_PER_GROUP colors
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
            # Very old school programming style with those short variable names
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

        if self.number_of_used_bones <= SkinPLG.MAX_NUMBER_OF_BONES_PER_GROUP:
            return

        groups = [set()]
        for face_split in face_splits.values():
            triangles = face_split[0]

            # Each vertex in a triangle can be affected by up to 4 bones
            # Group triangle bone sets by their size
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

        for face_split in face_splits.values():
            face_split.extend([[] for _ in range(len(groups) - 1)])
            triangles = face_split[0]
            for i in reversed(range(len(triangles))):
                triangle = triangles[i]
                triangle_group = set(bone for vertex in triangle for bone, weight in zip(self.vertex_bone_map[vertex], self.vertex_weights[vertex]) if weight > 0.0)
                for j, group in enumerate(groups):
                    if group.intersection(triangle_group) == triangle_group:
                        face_split[j].append(triangles.pop(i))
                        break

            for i in reversed(range(len(face_split))):
                if len(face_split[i]) == 0:
                    face_split.pop(i)

        # Add groups to self.bone_groups
        self.bone_groups.extend(groups)
        self.number_of_groups = len(self.bone_groups)

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