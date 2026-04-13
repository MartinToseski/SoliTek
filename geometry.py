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

    y = miny + outer_d / 2
    while y <= maxy - outer_d / 2:
        x = minx + outer_d / 2
        while x <= maxx - outer_d / 2:
            ring, outer = create_ring((x, y), inner_d, outer_d)

            if fits_inside(outer, boundary):
                rings.append((ring, outer))

            x += step
        y += step

    return rings


# ================= FINGERS =================
def create_fingers(center, inner_d, outer_d):
    finger_radii = []

    r_outer = outer_d / 2
    r_inner = inner_d / 2

    # Start just inside outer ring
    current_r = r_outer - FINGER_TO_RING

    for _ in range(FINGERS_PER_RING):
        if current_r <= r_inner:
            break

        finger_radii.append(current_r)

        # Move inward
        current_r -= (FINGER_SPACING + FINGER_THICKNESS)

    return finger_radii