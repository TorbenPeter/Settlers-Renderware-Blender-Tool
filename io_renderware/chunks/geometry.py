from .container import Container
from .struct import Struct
from .extension import Extension
from .skinplg import SkinPLG
from .materiallist import MaterialList
from ..containers.rgba import RGBA
from ..containers.uv import UV
from ..containers.triangle import Triangle
from ..containers.sphere import Sphere
from ..containers.vector3d import Vector3d
from struct import pack, unpack
import bpy

class Geometry(Container):

    ID_STAMP = 0x0000000F

    def __init__(self, header):
        super().__init__(header)
        self.object = None
        self.tristrip = False
        self.positions = False
        self.textured = False
        self.prelit = False
        self.has_normals = False
        self.light = False
        self.modulate_material_color = False
        self.textured2 = False
        self.native = False
        self.number_of_triangles = 0
        self.number_of_vertices = 0
        self.number_of_morph_targets = 0
        self.number_of_texture_sets = 0
        self.prelit_colors = []
        self.texture_sets = []
        self.triangles = []
        self.bounding_sphere = None
        self.has_vertices = False
        self.vertices = []
        self.normals = []

    def read(self, file):
        super().read(file)

        properties = self.children[Struct.ID_STAMP][0]
        format, = unpack("I", properties.content[:4])
        self.number_of_triangles, self.number_of_vertices, self.number_of_morph_targets = unpack("3I", properties.content[4:16])

        # TODO: Empty meshes (e.g. in effects) have 0 morph targets
        # TODO: Standarte (and possibly other entities) have multiple morph targets
        # TODO: Store morph targets as shape key. Basic shape key can always be created
        assert (self.number_of_morph_targets <= 1), "Multiple morph targets are not supported in this version"

        self.tristrip = bool(format & 0x00000001)
        self.positions = bool(format & 0x00000002)
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
            for byte in range(pointer, self.number_of_vertices*UV.BYTE_SIZE + pointer, UV.BYTE_SIZE):
                uv = UV()
                uv.read(properties.content[byte:byte+UV.BYTE_SIZE])
                texture_set.append(uv)
            self.texture_sets.append(texture_set)
            pointer += self.number_of_vertices*UV.BYTE_SIZE

        for byte in range(pointer, self.number_of_triangles*Triangle.BYTE_SIZE + pointer, Triangle.BYTE_SIZE):
            triangle = Triangle()
            triangle.read(properties.content[byte:byte+Triangle.BYTE_SIZE])
            self.triangles.append(triangle)
        pointer += self.number_of_triangles*Triangle.BYTE_SIZE

        self.bounding_sphere = Sphere()
        self.bounding_sphere.read(properties.content[pointer:pointer+Sphere.BYTE_SIZE])
        pointer += Sphere.BYTE_SIZE
        self.has_vertices, self.has_normals = unpack("II", properties.content[pointer:pointer+8])
        self.has_vertices = bool(self.has_vertices)
        self.has_normals = bool(self.has_normals)
        pointer += 8

        if self.has_vertices:
            for byte in range(pointer, self.number_of_vertices*Vector3d.BYTE_SIZE + pointer, Vector3d.BYTE_SIZE):
                vertex = Vector3d()
                vertex.read(properties.content[byte:byte+Vector3d.BYTE_SIZE])
                self.vertices.append(vertex)
            pointer += self.number_of_vertices*Vector3d.BYTE_SIZE

        if self.has_normals:
            for byte in range(pointer, self.number_of_vertices*Vector3d.BYTE_SIZE + pointer, Vector3d.BYTE_SIZE):
                normal = Vector3d()
                normal.read(properties.content[byte:byte+Vector3d.BYTE_SIZE])
                self.normals.append(normal)
            pointer += self.number_of_vertices*Vector3d.BYTE_SIZE

        # We need to know the number of vertices for this, hence this is called (again) after self has been parsed
        extensions = self.children[Extension.ID_STAMP]
        for extension in extensions:
            for child_type, children in extension.children.items():
                if child_type == SkinPLG.ID_STAMP:
                    for child in children:
                        child.read(file=None, number_of_vertices=self.number_of_vertices)


    def build(self, armature):
        vertices = [vertex.as_tuple() for vertex in self.vertices]
        triangles = [triangle.as_tuple() for triangle in self.triangles]

        # Create Mesh
        index = len(bpy.data.meshes)
        mesh = bpy.data.meshes.new("Mesh{:03}".format(index))
        mesh.from_pydata(vertices, [], triangles)
        mesh.update()

        for texture_set in self.texture_sets:
            uv = mesh.uv_layers.new(name="UVMap{:03}".format(len(mesh.uv_layers)))
            for triangle in mesh.polygons:
                for vert_idx, loop_idx in zip(triangle.vertices, triangle.loop_indices):
                    uv.data[loop_idx].uv = (texture_set[vert_idx].u, texture_set[vert_idx].v)

        # Create Materials and Textures
        self.children[MaterialList.ID_STAMP][0].build(mesh)

        for i, face in enumerate(mesh.polygons):
            face.material_index = self.triangles[i].material

        # Create Object to attach the mesh to
        object = bpy.data.objects.new("Object{:03}".format(index), mesh)

        # Link Object to current collection
        bpy.context.collection.objects.link(object)

        self.object = object

        # TODO: MorphPLG
        # TODO: UserDataPLG
        extensions = self.children[Extension.ID_STAMP]
        for extension in extensions:
            for child_type, children in extension.children.items():
                for child in children:
                    if child_type == SkinPLG.ID_STAMP and armature is not None:
                        child.build(object, armature)