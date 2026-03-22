from abc import ABC, abstractmethod

class Chunk(ABC):

    ID_STAMP: int

    def __init__(self, header):
        self.header = header
        self.header.chunk_id_stamp = self.__class__.ID_STAMP

    @abstractmethod
    def read(self, file):
        pass

    @abstractmethod
    def build(self):
        pass

    @abstractmethod
    def fetch(self):
        pass

    @abstractmethod
    def write(self):
        pass