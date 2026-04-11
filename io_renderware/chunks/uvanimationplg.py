from .container import Container
from .struct import Struct
from ..containers.header import Header
from struct import pack, unpack

class UVAnimationPLG(Container):

    ID_STAMP = 0x00000135

    def __init__(self, header):
        super().__init__(header)
        self.uv_animations = []

    def read(self, file):
        super().read(file)
        content = self.children[Struct.ID_STAMP][0].content
        number_of_animations, = unpack("I", content[:4])

        pointer = 4
        for _ in range(number_of_animations):
            animation_name = content[pointer:pointer+32].decode("latin_1").strip("\0")
            self.uv_animations.append(animation_name)
            pointer += 32

    def build(self, material):
        material["UV Animations"] = tuple(self.uv_animations)

    def fetch(self, material):
        if "UV Animations" in material:
            self.uv_animations = tuple(material["UV Animations"])

    def write(self):
        content = b""
        struct = Struct(Header())
        struct.content += pack("I", len(self.uv_animations))
        for uv_animation in self.uv_animations:
            name = uv_animation + "\0"*(32 - len(uv_animation))
            struct.content += name.encode("utf-8")
        content += struct.write()

        self.header.chunk_size = len(content)
        return self.header.write() + content