import math

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def dist(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)

def sign(v: float) -> int:
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0