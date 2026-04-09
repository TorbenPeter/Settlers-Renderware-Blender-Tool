from .content import Content

class String(Content):

    ID_STAMP = 0x00000002

    def read(self, file):
        super().read(file)
        self.content = self.content.decode("latin_1").strip("\0")

    def write(self):
        # Padding to 4 byte-align
        content = self.content + "\0"*((len(self.content)//4 + 1)*4 - len(self.content))
        content = content.encode("utf-8")
        self.header.chunk_size = len(content)
        return self.header.write() + content