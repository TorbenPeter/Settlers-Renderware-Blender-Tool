from .content import Content
from struct import pack, unpack
from re import match

class UserDataPLG(Content):

    DEFAULT_TITLE = "3dsmax User Properties"
    ID_STAMP = 0x0000011F

    def __init__(self, header):
        super().__init__(header)
        self.integers = []
        self.floats = []
        self.data = {}

    def read(self, file):
        super().read(file)
        number_of_entries, title_size = unpack("II", self.content[:8])
        title = self.content[8:8+title_size].decode("latin_1")
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
                string = self.content[pointer+4:pointer+4+string_size].decode("latin_1")
                re_match = match(r"(?P<key>\w+)\s*=\s*(?P<value>.+)", string)
                if re_match is not None:
                    self.data[re_match.group("key")] = re_match.group("value").strip("\0")
                pointer += 4+string_size
        
    def write(self):
        content = b""
        # NOTE: We're not going to be fancy for this
        number_of_entries = 1
        title = UserDataPLG.DEFAULT_TITLE + "\0"
        title_size = len(title)
        content += pack("II", number_of_entries, title_size)
        content += title.encode("utf-8")
        if self.integers:
            type = 1
            count = len(self.integers)
        elif self.floats:
            type = 2
            count = len(self.floats)
        else:
            type = 3
            count = len(self.data)
        content += pack("II", type, count)

        if type == 1:
            content += pack("{}i".format(count), *self.integers)
        elif type == 2:
            content += pack("{}f".format(count), *self.floats)
        else:
            for key, value in self.data.items():
                string = key + "=" + value + "\0"
                content += pack("I", len(string)) + string.encode("utf-8")
        self.header.chunk_size = len(content)
        return self.header.write() + content