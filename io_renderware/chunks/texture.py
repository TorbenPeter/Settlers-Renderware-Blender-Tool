from .container import Container
from .struct import Struct
from .string import String
from struct import pack, unpack

class Texture(Container):

    ID_STAMP = 0x00000006
    TEXTURE_PATH = ""

    def __init__(self, header):
        super().__init__(header)
        self.filtering = 0
        self.u_adressing = 0
        self.v_adressing = 0
        self.use_mip_levels = False

    def read(self, file):
        super().read(file)
        properties = self.children[Struct.ID_STAMP][0]
        self.filtering, adressing, self.use_mip_levels = unpack("BBH", properties.content[:4])
        self.u_adressing = adressing & 0x0F
        self.v_adressing = (adressing & 0xF0) >> 4
        self.use_mip_levels = bool(self.use_mip_levels)
        self.texture_name = self.children[String.ID_STAMP][0].content.strip("\0")
        # Technically, the second string contains an RGB value
        # That one seems to be uninportant though

    def build(self):
        pass