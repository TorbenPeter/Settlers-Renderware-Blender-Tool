from .chunk import Chunk

class Content(Chunk):

    def __init__(self, header):
        super().__init__(header)
        self.content = None

    def read(self, file):
        self.content = file.read(self.header.chunk_size)

    # TODO
    def build(self):
        pass

    # TODO
    def load(self):
        pass

    # TODO
    def write(self):
        pass