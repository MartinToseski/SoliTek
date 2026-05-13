from shapely.geometry import box
from shapely.ops import unary_union

class BusbarParams:
    def __init__(self, top_d, bottom_d, top_left_d, top_right_d,
                 bottom_left_d, bottom_right_d, protrusion_w, protrusion_h, busbar_h=1):
        self.top_d          = top_d
        self.bottom_d       = bottom_d
        self.top_left_d     = top_left_d
        self.top_right_d    = top_right_d
        self.bottom_left_d  = bottom_left_d
        self.bottom_right_d = bottom_right_d
        self.protrusion_w   = protrusion_w
        self.protrusion_h   = protrusion_h
        self.busbar_h       = busbar_h

def generate_busbars_for_block(origin, block_w, finger_h, bp: BusbarParams):
    ox, oy = origin
    block_top    = oy + finger_h
    block_bottom = oy
    cx = ox + block_w / 2
    pw, ph = bp.protrusion_w, bp.protrusion_h

    # ---- TOP BUSBAR ----
    tb_top   = block_top   - bp.top_d
    tb_bot   = tb_top      - bp.busbar_h
    tb_left  = ox          + bp.top_left_d
    tb_right = ox + block_w - bp.top_right_d

    top_main  = box(tb_left, tb_bot, tb_right, tb_top)
    top_prot  = box(cx - pw/2, tb_bot - ph, cx + pw/2, tb_top + ph)
    top_busbar = unary_union([top_main, top_prot])

    # ---- BOTTOM BUSBAR ----
    bb_bot   = block_bottom + bp.bottom_d
    bb_top   = bb_bot       + bp.busbar_h
    bb_left  = ox           + bp.bottom_left_d
    bb_right = ox + block_w  - bp.bottom_right_d

    bottom_busbar = box(bb_left, bb_bot, bb_right, bb_top)

    return top_busbar, bottom_busbar