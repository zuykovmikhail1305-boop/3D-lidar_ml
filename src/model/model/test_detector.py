class Detector:
    def __init__(self):
        self.flip = True
    def resolve(self, points):
        self.flip = not self.flip
        if self.flip:
            return float(100)
        else:
            return None
