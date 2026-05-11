from shapely.geometry import box
import busbars
import math


class InsulationParams:
    def __init__(self, w, h, protrusion, h_margin, gap, inset):
        self.w          = w
        self.h          = h
        self.protrusion = protrusion
        self.h_margin   = h_margin
        self.gap        = gap
        self.inset      = inset


def generate_insulation_for_block(origin, block_w, finger_h, cell,
                                   bp: busbars.BusbarParams,
                                   ip: InsulationParams):
    ox, oy = origin
    cell_minx, _, cell_maxx, _ = cell.bounds
    clip_left  = cell_minx + ip.inset
    clip_right = cell_maxx - ip.inset

    def _row(left, right, bot, top):
        r_bot   = bot + ip.h_margin
        r_top   = top - ip.h_margin
        x_start = left  - ip.protrusion
        x_end   = right + ip.protrusion
        step    = ip.w + ip.gap
        rects   = []
        n       = math.ceil((x_end - x_start) / step)
        for i in range(n):
            x0 = x_start + i * step
            x1 = x0 + ip.w
            if x0 >= x_end:
                break
            # clip only the outer edges against the inset border
            if i == 0:
                x0 = max(x0, clip_left)
            if i == n - 1 or x1 >= x_end:
                x1 = min(x1, clip_right)
            rects.append(box(x0, r_bot, x1, r_top))
        return rects

    tb_top   = oy + finger_h - bp.top_d
    tb_bot   = tb_top        - bp.busbar_h
    tb_left  = ox            + bp.top_left_d
    tb_right = ox + block_w  - bp.top_right_d

    bb_bot   = oy            + bp.bottom_d
    bb_top   = bb_bot        + bp.busbar_h
    bb_left  = ox            + bp.bottom_left_d
    bb_right = ox + block_w  - bp.bottom_right_d

    return _row(tb_left, tb_right, tb_bot, tb_top) + \
           _row(bb_left, bb_right, bb_bot, bb_top)

def generate_insulation_cell_inset(cell, ip: InsulationParams):
    minx, miny, maxx, maxy = cell.bounds
    d = ip.inset
    return box(minx + d, miny + d, maxx - d, maxy - d)