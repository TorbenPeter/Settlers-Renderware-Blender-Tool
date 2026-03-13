from .container import Container
from .struct import Struct
from struct import pack, unpack

class Atomic(Container):

    ID_STAMP = 0x00000014

    def __init__(self, header):
        super().__init__(header)
        self.frame_index = 0
        self.geometry_index = 0
        self.collision_test = False
        self.render = False

    def read(self, file):
        super().read(file)
        properties = self.children[Struct.ID_STAMP][0]
        self.frame_index, self.geometry_index, flags, _ = unpack("iiii", properties.content)
        self.collision_test = bool(flags & 0x01)
        self.render = bool(flags & 0x04)

        # TODO: Material Effects and Particles