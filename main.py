from shapely.geometry import box
from config import WAFER_SIZE, RING_SPACING, EDGE_MARGIN, OUTER_DIAMETER, INNER_DIAMETER
from geometry import generate_rings
from export import export_dxf


if __name__ == '__main__':
    wafer = box(0, 0, WAFER_SIZE, WAFER_SIZE)

    rings = generate_rings(wafer, INNER_DIAMETER, OUTER_DIAMETER, RING_SPACING, EDGE_MARGIN)
    print(f"Generated {len(rings)} rings")

    export_dxf(wafer, rings, INNER_DIAMETER, OUTER_DIAMETER)