from .container import Container
from .struct import Struct
from .animanimation import AnimAnimation
from ..containers.header import Header
from struct import pack, unpack
import bpy

class UVAnimationDictionary(Container):

    ID_STAMP = 0x0000002B

    def __init__(self, header):
        super().__init__(header)
        self.number_of_animations = 0

    def read(self, file):
        super().read(file)

        properties = self.children[Struct.ID_STAMP][0]
        self.number_of_animations, = unpack("I", properties.content[:4])

    def build(self):
        for animation in self.children[AnimAnimation.ID_STAMP]:
            animation.build()

    def fetch(self):
        self.children[AnimAnimation.ID_STAMP] = []
        animation_names = set()
        for material in bpy.data.materials:
            if "UV Animations" in material:
                for animation_name in material["UV Animations"]:
                    if animation_name not in animation_names:
                        animation = AnimAnimation(Header())
                        animation.fetch_uv(material, animation_name)
                        self.children[AnimAnimation.ID_STAMP].append(animation)
                        animation_names.add(animation_name)
        self.number_of_animations = len(self.children[AnimAnimation.ID_STAMP])

    def write(self):
        content = b""
        struct = Struct(Header())
        struct.content += pack("I", self.number_of_animations)
        content += struct.write()

        for child in self.children[AnimAnimation.ID_STAMP][::-1]:
            content += child.write_uv()

        self.header.chunk_size = len(content)
        return self.header.write() + content