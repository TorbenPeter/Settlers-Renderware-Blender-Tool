from .content import Content

class String(Content):

    ID_STAMP = 0x00000002

    def read(self, file):
        super().read(file)
        self.content = self.content.decode("latin_1").strip("\0")