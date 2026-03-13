from .container import Container

class Texture(Container):

    ID_STAMP = 0x00000006

    def __init__(self, header):
        super().__init__(header)

    def read(self, file):
        super().read(file)
        # self.filtering, adressing, self.use_mip_levels = unpack("BBH", data)
        # self.u_adressing = adressing & 0x0F
        # self.v_adressing = (adressing & 0xF0) >> 4