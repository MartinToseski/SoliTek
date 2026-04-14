from shapely.geometry import Point
from config import FINGER_TO_RING, FINGER_SPACING, FINGER_THICKNESS


def create_ring(center, inner_d, outer_d):
    outer = Point(center).buffer(outer_d / 2.0, resolution=128)
    inner = Point(center).buffer(inner_d / 2.0, resolution=128)

    return outer.difference(inner), outer


def fits_inside(geometry, boundary):
    return boundary.contains(geometry)


def generate_rings(boundary, inner_d, outer_d, spacing, edge_margin):
    rings = []

    step = outer_d + spacing
    minx, miny, maxx, maxy = boundary.bounds

    minx += edge_margin
    miny += edge_margin
    maxx -= edge_margin
    maxy -= edge_margin

    start_x = minx + outer_d / 2
    start_y = miny + outer_d / 2

    y = start_y
    while y <= maxy - outer_d / 2:
        x = start_x
        while x <= maxx - outer_d / 2:
            ring, outer = create_ring((x, y), inner_d, outer_d)

            if fits_inside(outer, boundary):
                rings.append((ring, outer, (x, y)))

            x += step
        y += step

    return rings


def create_fingers(center, inner_d, outer_d):
    finger_radii = []

    r_outer = outer_d / 2 - FINGER_TO_RING
    r_inner_limit = inner_d / 2 + FINGER_TO_RING

    step = FINGER_THICKNESS + FINGER_SPACING
    current_r = r_outer

    while True:
        r_inner = current_r - FINGER_THICKNESS

        if r_inner <= r_inner_limit:
            break

        finger_radii.append(current_r)
        current_r -= step

    return finger_radii