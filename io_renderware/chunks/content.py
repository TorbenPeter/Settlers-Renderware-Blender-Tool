from .chunk import Chunk

class Content(Chunk):

    def __init__(self, header):
        super().__init__(header)
        self.content = b""

    def read(self, file):
        self.content = file.read(self.header.chunk_size)

    def build(self):
        pass

    def fetch(self):
        pass

    def write(self):
        self.header.chunk_size = len(self.content)
        return self.header.write() + self.content