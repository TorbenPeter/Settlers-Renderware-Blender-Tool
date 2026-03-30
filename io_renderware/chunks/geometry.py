from .container import Container
from .struct import Struct
from .extension import Extension
from .morphplg import MorphPLG
from .skinplg import SkinPLG
from .binmeshplg import BinMeshPLG
from .materiallist import MaterialList
from ..containers.rgba import RGBA
from ..containers.triangle import Triangle
from ..containers.sphere import Sphere
from ..containers.header import Header
from struct import pack, unpack
from mathutils import Vector
import bpy

class Geometry(Container):

    ID_STAMP = 0x0000000F

    def __init__(self, header):
        super().__init__(header)
        self.object = None
        self.tristrip = False
        self.has_vertices = False
        self.textured = False
        self.prelit = False
        self.light = False
        self.modulate_material_color = False
        self.textured2 = False
        self.native = False
        self.has_vertices = False
        self.has_normals = False
        self.number_of_triangles = 0
        self.number_of_vertices = 0
        self.number_of_morph_targets = 0
        self.number_of_texture_sets = 0
        self.prelit_colors = []
        self.texture_sets = []
        self.triangles = []
        self.bounding_sphere = None
        self.vertex_sets = []
        self.normal_sets = []

    def read(self, file):
        super().read(file)

        properties = self.children[Struct.ID_STAMP][0]
        format, = unpack("I", properties.content[:4])
        self.number_of_triangles, self.number_of_vertices, self.number_of_morph_targets = unpack("3I", properties.content[4:16])

        self.tristrip = bool(format & 0x00000001)
        self.has_vertices = bool(format & 0x00000002)
        self.textured = bool(format & 0x00000004)
        self.prelit = bool(format & 0x00000008)
        self.has_normals = bool(format & 0x00000010)
        self.light = bool(format & 0x00000020)
        self.modulate_material_color = bool(format & 0x00000040)
        self.textured2 = bool(format & 0x00000080)
        self.native = bool(format & 0x01000000)
        self.number_of_texture_sets = (format & 0x00FF0000) >> 16

        assert (not self.native), "Native Geometry is not supported in this version"
    
        if self.number_of_texture_sets == 0:
            if self.textured2:
                self.number_of_texture_sets = 2
            elif self.textured:
                self.number_of_texture_sets = 1

        pointer = 16

        if self.prelit:
            for byte in range(pointer, self.number_of_vertices*RGBA.BYTE_SIZE + pointer, RGBA.BYTE_SIZE):
                rgba = RGBA()
                rgba.read(properties.content[byte:byte+RGBA.BYTE_SIZE])
                self.prelit_colors.append(rgba)
            pointer += self.number_of_vertices*RGBA.BYTE_SIZE

        for _ in range(self.number_of_texture_sets):
            texture_set = []
            for byte in range(pointer, self.number_of_vertices*8 + pointer, 8):
                texture_set.append(Vector(unpack("ff", properties.content[byte:byte+8])))
            self.texture_sets.append(texture_set)
            pointer += self.number_of_vertices*8

        for byte in range(pointer, self.number_of_triangles*Triangle.BYTE_SIZE + pointer, Triangle.BYTE_SIZE):
            triangle = Triangle()
            triangle.read(properties.content[byte:byte+Triangle.BYTE_SIZE])
            self.triangles.append(triangle)
        pointer += self.number_of_triangles*Triangle.BYTE_SIZE

        for _ in range(self.number_of_morph_targets):
            self.bounding_sphere = Sphere()
            self.bounding_sphere.read(properties.content[pointer:pointer+Sphere.BYTE_SIZE])
            pointer += Sphere.BYTE_SIZE
            has_vertices, has_normals = unpack("II", properties.content[pointer:pointer+8])
            has_vertices = bool(has_vertices)
            has_normals = bool(has_normals)
            pointer += 8

            vertices = []
            normals = []

            if has_vertices:
                for byte in range(pointer, self.number_of_vertices*12 + pointer, 12):
                    vertices.append(Vector(unpack("3f", properties.content[byte:byte+12])))
                pointer += self.number_of_vertices*12
                self.vertex_sets.append(vertices)

            if has_normals:
                for byte in range(pointer, self.number_of_vertices*12 + pointer, 12):
                    normals.append(Vector(unpack("3f", properties.content[byte:byte+12])))
                pointer += self.number_of_vertices*12
                self.normal_sets.append(normals)

        if Extension.ID_STAMP not in self.children:
            return

        extensions = self.children[Extension.ID_STAMP]
        for extension in extensions:
            for child_type, children in extension.children.items():
                # We need to know the number of vertices for this, hence this is called (again) after self has been parsed
                if child_type == SkinPLG.ID_STAMP:
                    for child in children:
                        child.read(file=None, number_of_vertices=self.number_of_vertices)
                # There might be cases where triangle information is only stored in the BinMeshPLG
                if child_type == BinMeshPLG.ID_STAMP and not self.triangles:
                    for child in children:
                        self.triangles = child.triangles

    def build(self, armature):
        
        triangles = [triangle.as_tuple() for triangle in self.triangles]
        if self.number_of_morph_targets == 0 or not self.has_vertices:
            vertices = []
        else:
            vertices = self.vertex_sets[0]

        # Create Mesh
        index = len(bpy.data.meshes)
        mesh = bpy.data.meshes.new("Mesh{:03}".format(index))
        mesh.from_pydata(vertices, [], triangles)
        mesh.update()

        for texture_set in self.texture_sets:
            uv = mesh.uv_layers.new(name="UVMap{:03}".format(len(mesh.uv_layers)))
            for triangle in mesh.polygons:
                for vert_idx, loop_idx in zip(triangle.vertices, triangle.loop_indices):
                    uv.data[loop_idx].uv = texture_set[vert_idx]

        # Create Materials and Textures
        if MaterialList.ID_STAMP in self.children:
            for child in self.children[MaterialList.ID_STAMP]:
                child.build(mesh)

        for i, face in enumerate(mesh.polygons):
            face.material_index = self.triangles[i].material

        # Create Object to attach the mesh to
        object = bpy.data.objects.new("Object{:03}".format(index), mesh)

        # Link Object to current collection
        if bpy.context.collection is not None:
            bpy.context.collection.objects.link(object)

        self.object = object

        if self.number_of_morph_targets <= 0:
            return

        shape_key_basis = object.shape_key_add(name="Basis")
        object.data.shape_keys.use_relative = False
        shape_key_basis.interpolation = "KEY_LINEAR"

        # Create potential subsequent vertex sets
        if self.number_of_morph_targets > 1:
            for index, vertex_set in enumerate(self.vertex_sets[1:]):
                shape_key = object.shape_key_add(name="Key"+str(index+1))
                shape_key.interpolation = "KEY_LINEAR"
                for i in range(len(vertices)):
                    shape_key.data[i].co = vertex_set[i]

        if Extension.ID_STAMP not in self.children:
            return

        # TODO: UserDataPLG
        extensions = self.children[Extension.ID_STAMP]
        for extension in extensions:
            for child_type, children in extension.children.items():
                if child_type == SkinPLG.ID_STAMP and armature is not None:
                    for child in children:
                        child.build(object, armature)
                elif child_type == MorphPLG.ID_STAMP:
                    for child in children:
                        child.build(object)

    def fetch(self, object):

        self.object = object
        mesh = object.data

        self.number_of_morph_targets = len(mesh.shape_keys.key_blocks)
        # Number of shape keys is only 0 if there are no vertices
        if self.number_of_morph_targets == 0 and len(mesh.vertices) > 0:
            self.number_of_morph_targets = 1

        self.tristrip = True
        self.has_vertices = True
        self.number_of_texture_sets = len(mesh.uv_layers)
        self.textured = self.number_of_texture_sets == 1
        self.textured2 = self.number_of_texture_sets > 1
        self.prelit = False
        self.has_normals = True
        self.light = True
        self.modulate_material_color = False
        self.native = False

        self.number_of_vertices = len(mesh.vertices)
        self.number_of_triangles = len(mesh.polygons)

        # In a .dff file, a single vertex can only have 1 UV coordinate. In cases where a vertex has multiple
        # UV coordinates, duplicates have to be created
        vertex_remap = {vertex: [vertex] for vertex in range(len(mesh.vertices))}
        # Start with a dictionary since vertices don't come up in order when iterating the polygons
        texture_sets = [{} for _ in range(len(mesh.uv_layers))]
        for polygon in mesh.polygons:

            if len(polygon.vertices) != 3:
                raise Exception("All faces must be triangles. Triangulate all faces before exporting")

            triangle = list(polygon.vertices)

            for loop_index, vertex_index in zip(polygon.loop_indices, range(len(triangle))):
                vertex = triangle[vertex_index]
                candidates = set(vertex_remap[vertex])

                for texture_set, uv_layer in zip(texture_sets, mesh.uv_layers):
                    uv = uv_layer.data[loop_index].uv
                    candidates = candidates.intersection(candidate for candidate in candidates if candidate in texture_set and uv == texture_set[candidate])

                if candidates:
                    new_vertex = candidates.pop()
                else:
                    if vertex not in texture_set:
                        new_vertex = vertex
                    else:
                        new_vertex = self.number_of_vertices
                        vertex_remap[vertex].append(new_vertex)
                        self.number_of_vertices += 1
                    for texture_set, uv_layer in zip(texture_sets, mesh.uv_layers):
                        texture_set[new_vertex] = uv_layer.data[loop_index].uv

                triangle[vertex_index] = new_vertex

            self.triangles.append(Triangle(triangle[0], triangle[1], triangle[2], polygon.material_index))

        for texture_set in texture_sets:
            self.texture_sets.append([uv for _, uv in sorted(texture_set.items(), key=lambda x: x[0])])

        for modifier in object.modifiers:
            if modifier.type == "ARMATURE":
                skin = SkinPLG(Header())
                skin.fetch(object, vertex_remap)


        # TODO: Per morph target, get all vertices and copy those from the map
        # TODO Bounding Sphere is min+abs(max-min)/2 as center with radius being the largest distance from any vertex. Use bound_box, change frame for shape keys

        # self.number_of_triangles, self.number_of_vertices, self.number_of_morph_targets = unpack("3I", properties.content[4:16])

        # self.tristrip = bool(format & 0x00000001)
        # self.positions = bool(format & 0x00000002)
        # self.textured = bool(format & 0x00000004)
        # self.prelit = bool(format & 0x00000008)
        # self.has_normals = bool(format & 0x00000010)
        # self.light = bool(format & 0x00000020)
        # self.modulate_material_color = bool(format & 0x00000040)
        # self.textured2 = bool(format & 0x00000080)
        # self.native = bool(format & 0x01000000)
        # self.number_of_texture_sets = (format & 0x00FF0000) >> 16

        # assert (not self.native), "Native Geometry is not supported in this version"
    
        # if self.number_of_texture_sets == 0:
        #     if self.textured2:
        #         self.number_of_texture_sets = 2
        #     elif self.textured:
        #         self.number_of_texture_sets = 1

        # self.object = None
        # self.tristrip = False
        # self.positions = False
        # self.textured = False
        # self.prelit = False
        # self.light = False
        # self.modulate_material_color = False
        # self.textured2 = False
        # self.native = False
        # self.has_vertices = False
        # self.has_normals = False
        # self.number_of_triangles = 0
        # self.number_of_vertices = 0
        # self.number_of_morph_targets = 0
        # self.number_of_texture_sets = 0
        # self.prelit_colors = []
        # self.texture_sets = []
        # self.triangles = []
        # self.bounding_sphere = None
        # self.vertex_sets = []
        # self.normal_sets = []

    def write(self):
        return b""