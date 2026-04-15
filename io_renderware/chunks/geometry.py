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
from ..util import apply_vertex_remap
from struct import pack, unpack
from mathutils import Vector
import bpy

class Geometry(Container):

    # UV Map V-coordinate is flipped in this range
    UV_MIN = -16
    UV_MAX = 16

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
        self.bounding_spheres = []
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
            bounding_sphere = Sphere()
            bounding_sphere.read(properties.content[pointer:pointer+Sphere.BYTE_SIZE])
            self.bounding_spheres.append(bounding_sphere)
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
                # Triangle information in the BinMeshPLG is the one that counts
                if child_type == BinMeshPLG.ID_STAMP:
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
                    # Flip V-coordinate, because Renderware is quirky like that
                    uv.data[loop_idx].uv[1] = Geometry.UV_MAX - uv.data[loop_idx].uv[1] + Geometry.UV_MIN

        # Create Materials and Textures
        if MaterialList.ID_STAMP in self.children:
            for child in self.children[MaterialList.ID_STAMP]:
                child.build(mesh)

        for i, face in enumerate(mesh.polygons):
            face.material_index = self.triangles[i].material

        if self.prelit:
            vertex_colors = mesh.vertex_colors.new()
            i = 0
            for polygon in mesh.polygons:
                for vertex in polygon.vertices:
                    color = self.prelit_colors[vertex]
                    vertex_colors.data[i].color[0] = color.r/255
                    vertex_colors.data[i].color[1] = color.g/255
                    vertex_colors.data[i].color[2] = color.b/255
                    vertex_colors.data[i].color[3] = color.a/255
                    i += 1

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

        # There is always at least one morph target, even for empty geometries
        self.number_of_morph_targets = 1
        if mesh.shape_keys is not None:
            self.number_of_morph_targets = max(1, len(mesh.shape_keys.key_blocks))

        self.tristrip = len(mesh.vertices) > 0
        self.has_vertices = len(mesh.vertices) > 0
        self.number_of_texture_sets = len(mesh.uv_layers)
        self.textured = self.number_of_texture_sets == 1
        self.textured2 = self.number_of_texture_sets > 1
        self.prelit = len(mesh.vertex_colors) > 0
        self.has_normals = len(mesh.vertices) > 0
        self.light = len(mesh.vertices) > 0 and not self.prelit
        self.modulate_material_color = False
        self.native = False

        self.number_of_vertices = len(mesh.vertices)
        self.number_of_triangles = len(mesh.polygons)

        # In a .dff file, a single vertex can only have 1 UV coordinate. In cases where a vertex has multiple
        # UV coordinates, duplicates have to be created
        vertex_remap = {vertex: [vertex] for vertex in range(len(mesh.vertices))}
        # Start with a dictionary since vertices don't come up in order when iterating the polygons
        texture_sets = [{} for _ in range(len(mesh.uv_layers))]
        # Faces must be split by their respective material for the BinMeshPLG
        face_splits = {material: [[]] for material in range(len(mesh.materials))}
        # TODO: There appear to be duplicate triangles in some meshes that later on crash the tristrip generation
        # Might have to handle that at some point
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
            face_splits[polygon.material_index][0].append((triangle[0], triangle[1], triangle[2]))

        for texture_set in texture_sets:
            self.texture_sets.append([Vector((uv[0], Geometry.UV_MIN - uv[1] + Geometry.UV_MAX)) for _, uv in sorted(texture_set.items(), key=lambda x: x[0])])

        face_splits = {material_id: splits for material_id, splits in face_splits.items() if sum(len(split) for split in splits) > 0}

        material_list = MaterialList(Header())
        self.children[MaterialList.ID_STAMP] = [material_list]
        material_list.fetch(object.data)
        
        extension = Extension(Header())
        self.children[Extension.ID_STAMP] = [extension]

        for modifier in object.modifiers:
            if modifier.type == "ARMATURE":
                skin = SkinPLG(Header())
                skin.fetch(object, vertex_remap, face_splits, self.number_of_vertices)
                extension.children[SkinPLG.ID_STAMP] = [skin]

        binmesh = BinMeshPLG(Header())
        binmesh.fetch(face_splits)
        extension.children[BinMeshPLG.ID_STAMP] = [binmesh]

        # First Morph Target always exists (and is easier to compute)
        center_x = object.bound_box[0][0] + abs(object.bound_box[4][0]-object.bound_box[0][0])/2
        center_y = object.bound_box[0][1] + abs(object.bound_box[2][1]-object.bound_box[0][1])/2
        center_z = object.bound_box[0][2] + abs(object.bound_box[1][2]-object.bound_box[0][2])/2
        center = Vector((center_x, center_y, center_z))
        radius = 0
        if len(mesh.vertices) > 0:
            radius = max((vertex.co - center).magnitude for vertex in mesh.vertices)
        bounding_sphere = Sphere(position=center, radius=radius)
        vertices = [vertex.co for vertex in mesh.vertices]
        # NOTE: These normals are in general not identical to the ones provided in a .dff file
        normals = [vertex.normal for vertex in mesh.vertices]
        apply_vertex_remap(vertices, vertex_remap, self.number_of_vertices)
        apply_vertex_remap(normals, vertex_remap, self.number_of_vertices)
        self.bounding_spheres.append(bounding_sphere)
        self.vertex_sets.append(vertices)
        self.normal_sets.append(normals)

        if self.prelit:
            self.prelit_colors = [RGBA() for _ in range(self.number_of_vertices)]
            vertex_colors = mesh.vertex_colors[0]
            i = 0
            for polygon in mesh.polygons:
                for vertex in polygon.vertices:
                    color = self.prelit_colors[vertex]
                    vertex_color = vertex_colors.data[i].color
                    color.r = int(vertex_color[0] * 255)
                    color.g = int(vertex_color[1] * 255)
                    color.b = int(vertex_color[2] * 255)
                    color.a = int(vertex_color[3] * 255)
                    i += 1

        if self.number_of_morph_targets <= 1:
            return
        
        for key_block in mesh.shape_keys.key_blocks[1:]:
            min_x, max_x, min_y, max_y, min_z, max_z = float("inf"), float("-inf"), float("inf"), float("-inf"), float("inf"), float("-inf")
            vertices = []
            for point in key_block.points:
                vertices.append(point.co)
                min_x = min(min_x, point.co[0])
                max_x = max(max_x, point.co[0])
                min_y = min(min_y, point.co[1])
                max_y = max(max_y, point.co[1])
                min_z = min(min_z, point.co[2])
                max_z = max(max_z, point.co[2])
            center_x = min_x + abs(max_x-min_x)/2
            center_y = min_y + abs(max_y-min_y)/2
            center_z = min_z + abs(max_z-min_z)/2
            center = Vector((center_x, center_y, center_z))
            bounding_sphere = Sphere(position=center, radius=max((vertex.co - center).magnitude for vertex in mesh.vertices))
            # This is way more inconvenient than it has to be
            normals_list = key_block.normals_vertex_get()
            normals = [(normals_list[i:i+3]) for i in range(0, len(normals_list), 3)]
            apply_vertex_remap(vertices, vertex_remap, self.number_of_vertices)
            apply_vertex_remap(normals, vertex_remap, self.number_of_vertices)
            self.bounding_spheres.append(bounding_sphere)
            self.vertex_sets.append(vertices)
            self.normal_sets.append(normals)

        # If shape keys have animation data, create morph PLG
        if mesh.shape_keys.animation_data is not None:
            morph = MorphPLG(Header())
            morph.fetch(object)
            extension.children[MorphPLG.ID_STAMP] = [morph]


    def write(self):
        content = b""
        struct = Struct(Header())

        format = 0
        format |= int(self.tristrip)
        format |= int(self.has_vertices) << 1
        format |= int(self.textured) << 2
        format |= int(self.prelit) << 3
        format |= int(self.has_normals) << 4
        format |= int(self.light) << 5
        format |= int(self.modulate_material_color) << 6
        format |= int(self.textured2) << 7
        format |= int(self.native) << 24
        format |= self.number_of_texture_sets << 16

        struct.content += pack("IIII", format, self.number_of_triangles, self.number_of_vertices, self.number_of_morph_targets)

        if self.prelit:
            for color in self.prelit_colors:
                struct.content += color.write()

        for texture_set in self.texture_sets:
            struct.content += pack("{}f".format(2*len(texture_set)), *[coord for uv in texture_set for coord in uv])

        for triangle in self.triangles:
            struct.content += triangle.write()

        for i in range(self.number_of_morph_targets):
            bounding_sphere = self.bounding_spheres[i]
            vertices = self.vertex_sets[i]
            normals = self.normal_sets[i]
            struct.content += bounding_sphere.write()

            has_vertices = len(vertices) > 0
            has_normals = len(normals) > 0
            struct.content += pack("II", int(has_vertices), int(has_normals))

            struct.content += pack("{}f".format(3*len(vertices)), *[coord for position in vertices for coord in position])
            struct.content += pack("{}f".format(3*len(normals)), *[coord for vector in normals for coord in vector])

        content += struct.write()

        if MaterialList.ID_STAMP in self.children:
            for child in self.children[MaterialList.ID_STAMP]:
                content += child.write()

        if Extension.ID_STAMP in self.children:
            for child in self.children[Extension.ID_STAMP]:
                content += child.write()

        self.header.chunk_size = len(content)
        return self.header.write() + content