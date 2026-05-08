from shapely.geometry import box
from src.config.config import WAFER_SIZE, WAFER_SIZE_LARGE, RING_SPACING, EDGE_MARGIN, OUTER_DIAMETER, INNER_DIAMETER
from src.core.layout import generate_ring_layout
from src.export.export_dxf import export_dxf


if __name__ == '__main__':
    wafer1 = box(0, 0, WAFER_SIZE, WAFER_SIZE)
    wafer2 = box(0, 0, WAFER_SIZE_LARGE, WAFER_SIZE_LARGE)

    rings1, actual_margin_x1, actual_margin_y1 = generate_ring_layout(wafer1, INNER_DIAMETER, OUTER_DIAMETER, RING_SPACING, EDGE_MARGIN)
    rings2, actual_margin_x2, actual_margin_y2 = generate_ring_layout(wafer2, INNER_DIAMETER, OUTER_DIAMETER, RING_SPACING, EDGE_MARGIN)
    print(f"Small wafer -> Generated {len(rings1)} rings")
    print(f"Large wafer -> Generated {len(rings2)} rings")

    export_dxf(wafer1, rings1, INNER_DIAMETER, OUTER_DIAMETER, actual_margin_x1, actual_margin_y1, "irregular_rings_small")
    export_dxf(wafer2, rings2, INNER_DIAMETER, OUTER_DIAMETER, actual_margin_x2, actual_margin_y2, "irregular_rings_large")