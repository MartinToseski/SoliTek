from shapely.geometry import box
from shapely.geometry.polygon import Polygon
import math

class ContactParams:
    def __init__(self, w, h, gap_x, gap_y,
                 margin_x, margin_y):
        self.w = w
        self.h = h
        self.gap_x = gap_x
        self.gap_y = gap_y
        self.margin_x = margin_x
        self.margin_y = margin_y



def generate_contact_pads_for_cell(cell: Polygon, cp: ContactParams):
    min_x, min_y, max_x, max_y = cell.bounds

    available_w = (max_x - min_x) - 2 * cp.margin_x
    available_h = (max_y - min_y) - 2 * cp.margin_y

    n_x = max(0, math.floor((available_w + cp.gap_x) / (cp.w + cp.gap_x)))
    n_y = max(0, math.floor((available_h + cp.gap_y) / (cp.h + cp.gap_y)))

    contacts = []
    for j in range(n_y):
        for i in range(n_x):
            lx = min_x + cp.margin_x + i * (cp.w + cp.gap_x)
            ly = min_y + cp.margin_y + j * (cp.h + cp.gap_y)
            contacts.append(box(lx, ly, lx + cp.w, ly + cp.h))

    return contacts