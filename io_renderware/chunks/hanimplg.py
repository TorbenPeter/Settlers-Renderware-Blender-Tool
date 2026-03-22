from .content import Content
from struct import pack, unpack

class HAnimPLG(Content):

    ID_STAMP = 0x0000011E
    CONST = 256

    def __init__(self, header):
        super().__init__(header)
        self.id = 0
        self.number_of_bones = 0
        self.subhierarchy = False
        self.no_matrices = False
        self.update_modelling_matrices = False
        # LTMs = Local Translation Matrices
        self.update_ltms = False
        self.local_space_matrices = False
        self.keyframe_size = 36
        self.bone_info = []

    def read(self, file):
        super().read(file)
        const, self.id, self.number_of_bones = unpack("III", self.content[:12])

        if self.number_of_bones <= 0:
            return
        
        flags, self.keyframe_size = unpack("II", self.content[12:20])
        self.subhierarchy = bool(flags & 0x0001)
        self.no_matrices = bool(flags & 0x0002)
        self.update_modelling_matrices = bool(flags & 0x1000)
        self.update_ltms = bool(flags & 0x2000)
        self.local_space_matrices = bool(flags & 0x4000)

        for byte in range(20, 20+self.number_of_bones*12, 12):
            bone_id, bone_index, flags = unpack("III", self.content[byte:byte+12])
            self.bone_info.append((bone_id, bone_index, flags))

        self.bone_info.sort(key = lambda x: x[1])

    def write(self):
        content = b""
        content += pack("III", HAnimPLG.CONST, self.id, self.number_of_bones)

        if self.number_of_bones > 0:
            flags = int(self.subhierarchy) | int(self.no_matrices) << 1 | int(self.update_modelling_matrices) << 12 | int(self.update_ltms) << 13 | int(self.local_space_matrices) << 14
            content += pack("II", flags, self.keyframe_size)

            for bone_info in self.bone_info:
                content += pack("III", *bone_info)
            
        self.header.chunk_size = len(content)
        return self.header.write() + content