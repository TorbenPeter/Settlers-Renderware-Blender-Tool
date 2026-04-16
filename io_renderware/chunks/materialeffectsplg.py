from .content import Content
from .texture import Texture
from ..containers.header import Header
from struct import pack, unpack

class MaterialEffectsPLG(Content):

    ID_STAMP = 0x00000120

    NULL = 0
    BUMPMAP = 1
    ENVMAP = 2
    BUMPENVMAP = 3
    DUAL = 4
    UVTRANSFORM = 5
    DUALUVTRANSFORM = 6

    def __init__(self, header):
        super().__init__(header)
        self.type = 0
        self.source_blend_mode = 0
        self.destination_blend_mode = 0
        self.textures = []


    def read(self, file, is_atomic=False):

        # Some Atomics contain a MaterialEffectsPLG section as well. That can be ignored for the import
        if is_atomic:
            super().read(file)
            return

        self.type, = unpack("I", file.read(4))

        # NOTE: Currently, only (UV) DUAL is supported. Other effects don't occur in the Settlers games which makes them hard to verify
        if (self.type == MaterialEffectsPLG.NULL or
            self.type == MaterialEffectsPLG.ENVMAP or
            self.type == MaterialEffectsPLG.BUMPMAP or
            self.type == MaterialEffectsPLG.BUMPENVMAP or
            self.type == MaterialEffectsPLG.UVTRANSFORM):
            file.read(self.header.chunk_size - 4)
            return
        
        if self.type == MaterialEffectsPLG.DUALUVTRANSFORM:
            file.read(4)
        
        if self.type == MaterialEffectsPLG.DUAL or self.type == MaterialEffectsPLG.DUALUVTRANSFORM:
            _, self.source_blend_mode, self.destination_blend_mode, contains_texture = unpack("i3I", file.read(16))
            contains_texture = bool(contains_texture)
            
            if not contains_texture:
                return
            
            texture_header = Header()
            texture_header.read(file)
            texture = Texture(texture_header)
            texture.read(file)
            
            # There seems to be padding at the end when no second effect is used
            pointer = 4 + 16 + Header.HEADER_SIZE + texture_header.chunk_size
            if self.type == MaterialEffectsPLG.DUALUVTRANSFORM:
                pointer += 4
            file.read(self.header.chunk_size - pointer)
            self.textures.append(texture)


    def build(self, texture, node_tree, input, output):

        if len(self.textures) == 0:
            return

        if self.type == MaterialEffectsPLG.DUAL or self.type == MaterialEffectsPLG.DUALUVTRANSFORM:
            mixer = node_tree.nodes.new("ShaderNodeMix")
            mixer.data_type = "RGBA"
            mixer.clamp_factor = True
            mixer.clamp_result = True
            node_tree.links.new(output, mixer.outputs["Result"])
            node_tree.links.new(mixer.inputs["A"], texture.texture_node.outputs["Color"])

            self.textures[0].build(node_tree, input, mixer.inputs["B"])

            # NOTE: There will only be support for a very limited subset of blending options
            # Again, difficult to verify without examples
            if self.source_blend_mode == 5 and self.destination_blend_mode == 6:
                # Used for "regular" dual textures
                node_tree.links.new(mixer.inputs["Factor"], self.textures[0].texture_node.outputs["Alpha"])
                
            elif self.source_blend_mode == self.destination_blend_mode == 2:
                # Used in S5 for speculars
                node_tree.links.new(mixer.inputs["Factor"], self.textures[0].texture_node.outputs["Color"])


    def fetch(self, mixer, has_uv_animation=False):

        if mixer.type != "MIX" or mixer.blend_type != "MIX":
            return

        self.type = MaterialEffectsPLG.DUAL
        if has_uv_animation:
            self.type = MaterialEffectsPLG.DUALUVTRANSFORM

        if not mixer.inputs["Factor"].is_linked:
            return
        
        if mixer.inputs["Factor"].links[0].from_socket.type == "VALUE":
            self.source_blend_mode = 5
            self.destination_blend_mode = 6
        elif mixer.inputs["Factor"].links[0].from_socket.type == "RGBA":
            self.source_blend_mode = 2
            self.destination_blend_mode = 2

        if mixer.inputs["B"].is_linked:
            texture = Texture(Header())
            texture.fetch(mixer.inputs["B"].links[0].from_node)
            self.textures.append(texture)


    def write(self):
        content = b""

        if self.type != MaterialEffectsPLG.DUAL and self.type != MaterialEffectsPLG.DUALUVTRANSFORM:
            return content
        
        content += pack("I", self.type)
        if self.type == MaterialEffectsPLG.DUALUVTRANSFORM:
            content += pack("I", MaterialEffectsPLG.UVTRANSFORM)
        content += pack("4I", MaterialEffectsPLG.DUAL, self.source_blend_mode, self.destination_blend_mode, int(len(self.textures) > 0))
        
        for texture in self.textures:
            content += texture.write()

        # Padding for second effect
        if self.type == MaterialEffectsPLG.DUAL:
            content += pack("i", 0)

        self.header.chunk_size = len(content)
        return self.header.write() + content