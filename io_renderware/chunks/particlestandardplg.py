from .content import Content

class ParticleStandardPLG(Content):

    ID_STAMP = 0x00000130

    def __init__(self, header):
        super().__init__(header)

    def read(self, file):
        super().read(file)

    def build(self, object):
        object["Particles"] = self.content