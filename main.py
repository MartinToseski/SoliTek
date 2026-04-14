from shapely.geometry import Point, box
from config import WAFER_SIZE, RING_SPACING, EDGE_MARGIN, FINGER_TO_RING, FINGER_SPACING, FINGER_THICKNESS, FINGERS_PER_RING
from geometry import generate_rings
from export import export_dxf


OUTER_DIAMETER = 37.46
INNER_DIAMETER = 33.26


if __name__ == '__main__':
    wafer = box(0, 0, WAFER_SIZE, WAFER_SIZE)

    rings = generate_rings(wafer, INNER_DIAMETER, OUTER_DIAMETER, RING_SPACING, EDGE_MARGIN)
    print(f"Generated {len(rings)} rings")

    export_dxf(wafer, rings, INNER_DIAMETER, OUTER_DIAMETER)