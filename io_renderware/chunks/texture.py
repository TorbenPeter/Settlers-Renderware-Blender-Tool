from .container import Container
from .struct import Struct
from .string import String
from struct import pack, unpack
import bpy

class Texture(Container):

    ID_STAMP = 0x00000006
    TYPE_DIFFUSE = 0
    TYPE_MASK = 1
    TYPE_SPECULAR = 2
    TYPE_DUAL = 3
    TYPE_NORMAL = 4
    TEXTURE_PATH = ""

    def __init__(self, header):
        super().__init__(header)
        self.filtering = 0
        self.u_adressing = 0
        self.v_adressing = 0
        self.use_mip_levels = False
        self.texture_name = ""
        self.texture_node = None

    def read(self, file):
        super().read(file)
        properties = self.children[Struct.ID_STAMP][0]
        self.filtering, adressing, self.use_mip_levels = unpack("BBH", properties.content[:4])
        self.u_adressing = adressing & 0x0F
        self.v_adressing = (adressing & 0xF0) >> 4
        self.use_mip_levels = bool(self.use_mip_levels)
        self.texture_name = self.children[String.ID_STAMP][0].content
        # Technically, the second string contains an RGB value
        # That one seems to be uninportant though

    def build(self, node_tree, input, output):

        texture_node = node_tree.nodes.new("ShaderNodeTexImage")
        
        if Texture.TEXTURE_PATH:
            image = bpy.data.images.load(Texture.TEXTURE_PATH + self.texture_name + ".dds", check_existing = True)
            texture_node.image = image
        
        # NOTE: We ignore uv addressing here at the moment, since it appears to be the same for all models for now
        # If that changes, we need to modify the texture node here

        texture_node.name = texture_node.label = self.texture_name
            
        node_tree.links.new(texture_node.inputs["Vector"], input)
        node_tree.links.new(output, texture_node.outputs["Color"])

        self.texture_node = texture_node
