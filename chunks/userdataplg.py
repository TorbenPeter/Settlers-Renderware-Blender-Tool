from .content import Content
from struct import pack, unpack
from re import match

class UserDataPLG(Content):

    ID_STAMP = 0x0000011F

    def __init__(self, header):
        super().__init__(header)
        self.integers = []
        self.floats = []
        self.data = {}

    def read(self, file):
        super().read(file)
        number_of_entries, title_size = unpack("II", self.content[:8])
        title = self.content[8:8+title_size].decode("ascii")
        type, count = unpack("II", self.content[8+title_size:16+title_size])
        pointer = 16 + title_size
        for _ in range(count):
            if type == 1:
                integer, = unpack("i", self.content[pointer:pointer+4])
                self.integers.append(integer)
                pointer += 4
            elif type == 2:
                number, = unpack("f", self.content[pointer:pointer+4])
                self.floats.append(number)
                pointer += 4
            elif type == 3:
                string_size, = unpack("I", self.content[pointer:pointer+4])
                string = self.content[pointer+4:pointer+4+string_size].decode("ascii")
                re_match = match(r"(?P<key>\w+)\s*=\s*(?P<value>.+)", string)
                if re_match is not None:
                    self.data[re_match.group("key")] = re_match.group("value")
                pointer += 4+string_size