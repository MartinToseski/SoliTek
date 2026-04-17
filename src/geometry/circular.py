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