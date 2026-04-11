from struct import pack, unpack

class MorphTarget:
    """
    Container for MorphPLG targets
    """

    def __init__(self):
        self.start = 0
        self.end = 0
        self.delta_time = 0.0
        self.next = 0

    def read(self, bin):
        zero, self.start, self.end, self.delta_time, self.next = unpack("iiifi", bin)

    def write(self):
        return pack("iiifi", 0, self.start, self.end, self.delta_time, self.next)