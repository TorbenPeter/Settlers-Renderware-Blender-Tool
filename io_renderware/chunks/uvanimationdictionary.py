from .container import Container
from .struct import Struct
from .animanimation import AnimAnimation
from ..containers.header import Header
from struct import pack, unpack

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