from shapely.geometry import Point, box
from config import WAFER_SIZE, RING_SPACING, EDGE_MARGIN, FINGER_TO_RING, FINGER_SPACING, FINGER_THICKNESS, FINGERS_PER_RING


def create_ring(center, inner_d, outer_d):
    outer = Point(center).buffer(outer_d / 2.0)
    inner = Point(center).buffer(inner_d / 2.0)
    return outer.difference(inner), outer


def fits_inside(geometry, boundary):
    return boundary.contains(geometry)


def generate_rings(boundary, inner_d, outer_d, spacing, edge_margin):
    rings = []

    step = outer_d + spacing
    minx, miny, maxx, maxy = boundary.bounds

    # Apply edge margin
    minx += edge_margin
    miny += edge_margin
    maxx -= edge_margin
    maxy -= edge_margin

    usable_width = maxx - minx
    usable_height = maxy - miny

    # Number of rings that fit
    nx = int((usable_width + spacing) // step)
    ny = int((usable_height + spacing) // step)

    # Center the grid
    offset_x = (usable_width - (nx * outer_d + (nx - 1) * spacing)) / 2
    offset_y = (usable_height - (ny * outer_d + (ny - 1) * spacing)) / 2

    start_x = minx + offset_x + outer_d / 2
    start_y = miny + offset_y + outer_d / 2

    for i in range(ny):
        for j in range(nx):
            x = start_x + j * step
            y = start_y + i * step

            ring, outer = create_ring((x, y), inner_d, outer_d)

            if fits_inside(outer, boundary):
                rings.append((ring, outer))

    return rings


def create_fingers(center, inner_d, outer_d):
    finger_radii = []

    r_outer = outer_d / 2 - FINGER_TO_RING
    r_inner = inner_d / 2 + FINGER_TO_RING

    step = FINGER_THICKNESS + FINGER_SPACING
    current_r = r_outer

    while True:
        r_inner_edge = current_r - FINGER_THICKNESS
        if r_inner_edge <= r_inner:
            break
        finger_radii.append(current_r)
        current_r -= step

    return finger_radii