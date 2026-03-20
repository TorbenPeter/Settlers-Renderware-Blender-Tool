from .container import Container
from .struct import Struct
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