from shapely.geometry import box

class CellParams:
    def __init__(self, w_margin, h_margin):
        self.w_margin = w_margin
        self.h_margin = h_margin


def generate_cell_for_block(origin, block_w, finger_h, cp: CellParams):
    ox, oy = origin
    return box(
        ox - cp.w_margin,
        oy - cp.h_margin,
        ox + block_w + cp.w_margin,
        oy + finger_h + cp.h_margin
    )