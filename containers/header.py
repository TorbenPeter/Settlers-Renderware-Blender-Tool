from struct import pack, unpack

class Header:
    """
    DFF Headers consist of 3 values:
    
    1. The Chunk ID Stamp
    2. The Chunk size
    3. A library ID Stamp (constant)
    
    as uint32
    """
    HEADER_SIZE = 12
    LIBRARY_ID_STAMP = 0x1C02002D
    
    def __init__(self):
        self.chunk_id_stamp = 0
        self.chunk_size = 0
        self.library_id_stamp = Header.LIBRARY_ID_STAMP
        
    def read(self, file):
        header = file.read(Header.HEADER_SIZE)
        self.chunk_id_stamp, self.chunk_size, self.library_id_stamp = unpack("III", header)

    def write(self):
        return pack("III", self.chunk_id_stamp, self.chunk_size, self.library_id_stamp)
    
    def get_dff_version(self):
        return (((self.library_id_stamp >> 14) & 0x3FF00) + 0x30000) | ((self.library_id_stamp >> 16) & 0x3F)