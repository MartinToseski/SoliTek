from shapely.geometry import Point
from src.config.config import FINGER_TO_RING, FINGER_SPACING, FINGER_THICKNESS


def create_ring(center, inner_d, outer_d):
    outer = Point(center).buffer(outer_d / 2.0, resolution=128)
    inner = Point(center).buffer(inner_d / 2.0, resolution=128)
    return outer.difference(inner), outer


def create_fingers(inner_d, outer_d):
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


# ================= CUSTOM FINGER GENERATION =================
def create_fingers_n(inner_diameter, outer_diameter, n_fingers):
    """
    Generate finger radii for an arbitrary number of fingers.

    Distributes n_fingers evenly in the available radial space
    between the outer ring edge (minus FINGER_TO_RING gap) and
    the inner ring edge.

    Returns a list of outer radii for each finger, from outermost
    to innermost (same format as create_fingers).
    """
    r_outer = outer_diameter / 2
    r_inner = inner_diameter / 2

    # Available radial space
    r_start = r_outer - FINGER_TO_RING  # outermost finger position
    r_end = r_inner + FINGER_THICKNESS  # innermost finger must clear inner ring

    if n_fingers <= 0 or r_start <= r_end:
        return []

    if n_fingers == 1:
        return [r_start]

    # Spacing between finger outer edges
    step = (r_start - r_end) / (n_fingers - 1)

    radii = [r_start - i * step for i in range(n_fingers)]
    return radii


