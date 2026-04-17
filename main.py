from shapely.geometry import box
from src.config.config import WAFER_SIZE, WAFER_SIZE_LARGE, RING_SPACING, EDGE_MARGIN, OUTER_DIAMETER, INNER_DIAMETER
from src.core.layout import generate_ring_layout
from src.export.export_dxf import export_dxf


if __name__ == '__main__':
    wafer = box(0, 0, WAFER_SIZE, WAFER_SIZE)

    rings = generate_ring_layout(wafer, INNER_DIAMETER, OUTER_DIAMETER, RING_SPACING, EDGE_MARGIN)
    print(f"Generated {len(rings)} rings")

    export_dxf(wafer, rings, INNER_DIAMETER, OUTER_DIAMETER)