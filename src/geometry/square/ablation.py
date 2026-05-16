from shapely.geometry import box, Polygon
import math


class AblationParams:
    def __init__(self, w, h, gap, x_margin, wafer_margin):
        self.w        = w
        self.h        = h
        self.gap      = gap
        self.x_margin = x_margin
        self.wafer_margin = wafer_margin


def generate_ablation_for_cell(cell, ap: AblationParams):
    minx, miny, maxx, maxy = cell.bounds
    cy      = (miny + maxy) / 2
    r_bot   = cy - ap.h / 2
    r_top   = cy + ap.h / 2
    x_start = minx + ap.x_margin
    x_end   = maxx - ap.x_margin
    step    = ap.w + ap.gap
    rects   = []
    n       = math.floor((x_end - x_start + ap.gap) / step)
    for i in range(n):
        x0 = x_start + i * step
        rects.append(box(x0, r_bot, x0 + ap.w, r_top))
    return rects

def generate_ablation_with_wafer_margin(
    cell,
    wafer: Polygon,
    ap: AblationParams,
):
    cell_rects = generate_ablation_for_cell(cell, ap)

    minx, miny, maxx, maxy = cell.bounds
    w_minx, _, w_maxx, _   = wafer.bounds

    cy    = (miny + maxy) / 2
    r_bot = cy - ap.h / 2
    r_top = cy + ap.h / 2
    step  = ap.w + ap.gap

    x_start = minx + ap.x_margin
    x_end   = maxx - ap.x_margin
    n       = math.floor((x_end - x_start + ap.gap) / step)

    wafer_inner = wafer.buffer(-ap.wafer_margin)

    right_rects = []
    x = x_start + n * step
    while x + ap.w <= w_maxx - ap.wafer_margin:
        r = box(x, r_bot, x + ap.w, r_top)
        if wafer_inner.contains(r):
            right_rects.append(r)
        x += step

    left_rects = []
    x = x_start - step
    while x >= w_minx + ap.wafer_margin:
        r = box(x, r_bot, x + ap.w, r_top)
        if wafer_inner.contains(r):
            left_rects.append(r)
        x -= step
    left_rects.reverse()

    all_rects = left_rects + cell_rects + right_rects

    return all_rects