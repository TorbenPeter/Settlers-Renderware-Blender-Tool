from .container import Container
from .struct import Struct
from .texture import Texture
from .extension import Extension
from .materialeffectsplg import MaterialEffectsPLG
from .uvanimationplg import UVAnimationPLG
from ..containers.rgba import RGBA
from ..containers.header import Header
from struct import pack, unpack
import bpy

class Material(Container):

    ID_STAMP = 0x00000007

    def __init__(self, header):
        super().__init__(header)
        self.material = None
        self.color = None
        self.is_textured = False
        # Could also be Ambient Occlusion map
        self.has_mask = False
        self.has_specular = False
        self.has_normal = False
        self.ambient = 0
        self.specular = 0
        self.diffuse = 0

        
    def read(self, file):
        super().read(file)

        properties = self.children[Struct.ID_STAMP][0]
        flags, = unpack("I", properties.content[:4])
        self.has_mask = bool(flags & Texture.TYPE_MASK)
        self.has_specular = bool(flags & Texture.TYPE_SPECULAR)
        self.has_normal = bool(flags & Texture.TYPE_NORMAL)
        self.color = RGBA()
        self.color.read(properties.content[4:8])
        self.is_textured = unpack("I", properties.content[12:16])
        if self.header.get_dff_version() > 0x30400:
            self.ambient, self.specular, self.diffuse = unpack("fff", properties.content[16:28])


    def build(self, mesh):
        self.material = bpy.data.materials.new("Material{:03}".format(len(bpy.data.materials)))
        self.material.use_backface_culling = True

        if "Principled BSDF" not in self.material.node_tree.nodes:
            raise Exception("Principled BSDF not included in default material. Material.build needs a patch")
        
        properties = self.material.node_tree.nodes["Principled BSDF"].inputs
        properties["Base Color"].default_value = (self.color.r, self.color.g, self.color.b, self.color.a)
        properties["Diffuse Roughness"].default_value = self.diffuse
        properties["Specular IOR Level"].default_value = self.specular
        # Just as a way to store this value I guess. Ideally, no one touches this
        properties["Roughness"].default_value = self.ambient

        if not self.is_textured:
            return

        textures = self.children[Texture.ID_STAMP]
        node_tree = self.material.node_tree
        # Gather all outputs of the meshes UV layers
        uv_sources = []

        # UV Map V coordinate needs to be flipped
        for uv_layer in mesh.uv_layers:
            input_node = node_tree.nodes.new("ShaderNodeUVMap")
            input_node.uv_map = uv_layer.name
            uv_sources.append(input_node.outputs["UV"])

        textures[0].build(node_tree, uv_sources[0], properties["Base Color"])

        extensions = self.children[Extension.ID_STAMP]
        for extension in extensions:
            for child_type, children in extension.children.items():
                if child_type == MaterialEffectsPLG.ID_STAMP:
                    uv_source = uv_sources[0]
                    if len(uv_sources) > 1:
                        uv_source = uv_sources[1]
                    for child in children:
                        child.build(textures[0], node_tree, uv_source, properties["Base Color"])
                if child_type == UVAnimationPLG.ID_STAMP:
                    for child in children:
                        child.build(self.material)

        texture_id = 1

        if self.has_mask:
            uv_source = uv_sources[0]
            if len(uv_sources) > texture_id:
                uv_source = uv_sources[texture_id]
            # TODO: The combination with the base texture does not make sense in every case
            mixer = node_tree.nodes.new("ShaderNodeMix")
            mixer.data_type = "RGBA"
            mixer.blend_type = "MULTIPLY"
            mixer.clamp_factor = True
            mixer.clamp_result = True
            mixer.inputs["Factor"].default_value = 1.0
            node_tree.links.new(properties["Base Color"], mixer.outputs["Result"])
            node_tree.links.new(mixer.inputs["A"], textures[0].texture_node.outputs["Color"])
            textures[texture_id].build(node_tree, uv_source, mixer.inputs["B"])
            texture_id += 1

        if self.has_specular:
            uv_source = uv_sources[0]
            if len(uv_sources) > texture_id:
                uv_source = uv_sources[texture_id]
            textures[texture_id].build(node_tree, uv_source, properties["Specular Tint"])
            texture_id += 1

        if self.has_normal:
            uv_source = uv_sources[0]
            if len(uv_sources) > texture_id:
                uv_source = uv_sources[texture_id]
            normal_node = node_tree.nodes.new("ShaderNodeNormalMap")
            node_tree.links.new(properties["Normal"], normal_node.outputs["Normal"])
            textures[texture_id].build(node_tree, uv_source, normal_node.inputs["Color"])
            texture_id += 1

        mesh.materials.append(self.material)


    def fetch(self, material):
        self.material = material

        if "Principled BSDF" not in material.node_tree.nodes:
            raise Exception("Principled BSDF not included in material")
        
        properties = self.material.node_tree.nodes["Principled BSDF"].inputs
        self.color = RGBA(*properties["Base Color"].default_value)
        self.diffuse = properties["Diffuse Roughness"].default_value
        self.specular = properties["Specular IOR Level"].default_value
        self.ambient = properties["Roughness"].default_value

        self.is_textured = properties["Base Color"].is_linked

        extension = Extension(Header())

        self.children[Extension.ID_STAMP] = [extension]

        if not self.is_textured:
            return
        
        self.children[Texture.ID_STAMP] = []
        
        if properties["Base Color"].links[0].from_node.type == "MIX":
            mix_node = properties["Base Color"].links[0].from_node

            if mix_node.inputs["A"].is_linked:
                texture = Texture(Header())
                texture.fetch(mix_node.inputs['A'].links[0].from_node)
                self.children[Texture.ID_STAMP].append(texture)

            # Mask
            if mix_node.inputs["B"].is_linked and mix_node.blend_type == "MULTIPLY":
                self.has_mask = True
                texture = Texture(Header())
                texture.fetch(mix_node.inputs["B"].links[0].from_node)
                self.children[Texture.ID_STAMP].append(texture)

            # Dual Texture
            elif mix_node.inputs["B"].is_linked and mix_node.blend_type == "MIX":
                material_effects = MaterialEffectsPLG(Header())
                material_effects.fetch(mix_node)
                extension.children[MaterialEffectsPLG.ID_STAMP] = [material_effects]

        elif properties["Base Color"].links[0].from_node.type == "TEX_IMAGE":
            texture = Texture(Header())
            texture.fetch(properties["Base Color"].links[0].from_node)
            self.children[Texture.ID_STAMP].append(texture)

        self.has_specular = properties["Specular Tint"].is_linked
        if self.has_specular:
            texture = Texture(Header())
            texture.fetch(properties["Specular Tint"].links[0].from_node)
            self.children[Texture.ID_STAMP].append(texture)

        self.has_normal = properties["Normal"].is_linked
        if self.has_normal:
            normal_node = properties["Normal"].links[0].from_node
            if normal_node.type == "NORMAL_MAP" and normal_node.inputs["Color"].is_linked:
                texture = Texture(Header())
                texture.fetch(normal_node.inputs["Color"].links[0].from_node)
                self.children[Texture.ID_STAMP].append(texture)


    def write(self):
        content = b""

        struct = Struct(Header())

        flags = 0
        flags |= int(self.has_mask) * Texture.TYPE_MASK
        flags |= int(self.has_specular) * Texture.TYPE_SPECULAR
        flags |= int(self.has_normal) * Texture.TYPE_NORMAL

        struct.content += pack("I", flags)
        struct.content += self.color.write()
        struct.content += pack("iI3f", 0, int(self.is_textured), self.ambient, self.specular, self.diffuse)
        content += struct.write()

        if self.is_textured:
            for child in self.children[Texture.ID_STAMP]:
                content += child.write()

        for child in self.children[Extension.ID_STAMP]:
            content += child.write()

        self.header.chunk_size = len(content)
        return self.header.write() + content

