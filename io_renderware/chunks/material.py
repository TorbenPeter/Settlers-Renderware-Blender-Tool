from .container import Container
from .struct import Struct
from ..containers.rgba import RGBA
from struct import pack, unpack

class Material(Container):

    ID_STAMP = 0x00000007

    def __init__(self, header):
        super().__init__(header)
        self.color = None
        self.is_textured = False
        self.ambient = 0
        self.specular = 0
        self.diffuse = 0
        self.textures = []
        
    def read(self, file):
        super().read(file)

        properties = self.children[Struct.ID_STAMP][0]
        self.color = RGBA()
        self.color.read(properties.content[4:8])
        self.is_textured = unpack("I", properties.content[12:16])
        if self.header.get_dff_version() > 0x30400:
            self.ambient, self.specular, self.diffuse = unpack("fff", properties.content[16:28])

    def build(self):
        pass