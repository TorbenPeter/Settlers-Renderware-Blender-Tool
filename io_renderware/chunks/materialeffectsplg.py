from .content import Content

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

    def read(self, file):
        super().read(file)
        # TODO