from collections import defaultdict
from .chunk import Chunk
from .content import Content
from ..containers.header import Header

class Container(Chunk):

    def __init__(self, header):
        super().__init__(header)
        self.children = defaultdict(list)

    """
    Generic read function for Container Chunks
    Puts Chunks contained in the Container into a list of children
    """
    def read(self, file):
        remaining_size = self.header.chunk_size
        while remaining_size > 0:
            header = Header()
            header.read(file)
            for subclass in Container.__subclasses__():
                if subclass.ID_STAMP == header.chunk_id_stamp:
                    chunk = subclass(header)
                    break
            else:
                for subclass in Content.__subclasses__():
                    if subclass.ID_STAMP == header.chunk_id_stamp:
                        chunk = subclass(header)
                        break
                else:
                    raise Exception("Chunk type with id " + str(header.chunk_id_stamp) + " not implemented")
                
            self.children[header.chunk_id_stamp].append(chunk)
            chunk.read(file)

            remaining_size -= header.chunk_size + Header.HEADER_SIZE

    # TODO
    def build(self):
        pass

    # TODO
    def load(self):
        pass

    # TODO
    def write(self):
        pass