import math
from shapely.geometry import Polygon
from shapely.ops import unary_union

class WaferParams:
    def __init__(self, w_margin, h_margin, corner_w):
        self.w_margin = w_margin
        self.h_margin = h_margin
        self.corner_w = corner_w


def generate_wafer(cells, wp: WaferParams):
    all_cells = unary_union(cells)
    minx, miny, maxx, maxy = all_cells.bounds

    l = minx - wp.w_margin
    r = maxx + wp.w_margin
    b = miny - wp.h_margin
    t = maxy + wp.h_margin
    c = wp.corner_w / math.sqrt(2)

    coords = [
        (l + c, b),
        (r - c, b),
        (r,     b + c),
        (r,     t - c),
        (r - c, t),
        (l + c, t),
        (l,     t - c),
        (l,     b + c),
        (l + c, b),
    ]

    return Polygon(coords)