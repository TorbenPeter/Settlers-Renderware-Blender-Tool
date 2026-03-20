from .container import Container
from .struct import Struct
from .texture import Texture
from .extension import Extension
from .materialeffectsplg import MaterialEffectsPLG
from .uvanimationplg import UVAnimationPLG
from ..containers.rgba import RGBA
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

            separate = node_tree.nodes.new("ShaderNodeSeparateXYZ")
            combine = node_tree.nodes.new("ShaderNodeCombineXYZ")

            # Range is from 0 to 8 since UV Maps scale for different texture sizes
            # 8 seems to be the maximum ratio at which texture sizes differ
            map_range = node_tree.nodes.new("ShaderNodeMapRange")
            map_range.inputs["From Max"].default_value = 8.0
            map_range.inputs["To Max"].default_value = 0.0
            map_range.inputs["To Min"].default_value = 8.0

            node_tree.links.new(separate.inputs["Vector"], input_node.outputs["UV"])
            node_tree.links.new(combine.inputs["X"], separate.outputs["X"])
            node_tree.links.new(map_range.inputs["Value"], separate.outputs["Y"])
            node_tree.links.new(combine.inputs["Y"], map_range.outputs["Result"])
            uv_sources.append(combine.outputs["Vector"])

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