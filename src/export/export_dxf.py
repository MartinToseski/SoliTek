import ezdxf
from src.geometry.circular import create_fingers
from src.config.config import RING_SPACING, EDGE_MARGIN, FINGER_THICKNESS, FINGER_SPACING, FINGER_TO_RING
from shapely.geometry import Point


def export_dxf(boundary, rings, inner_diameter, outer_diameter,
               actual_margin_x, actual_margin_y, filename):

    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()

    # ===== DIM STYLE =====
    if "EZ_DIM" not in doc.dimstyles:
        dimstyle = doc.dimstyles.new("EZ_DIM")
    else:
        dimstyle = doc.dimstyles.get("EZ_DIM")

    dimstyle.dxf.dimdec = 4
    dimstyle.dxf.dimzin = 0

    # ===== LINETYPE =====
    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[0.5, 0.25, -0.25])

    # ===== LAYERS =====
    doc.layers.add("WAFER", color=1, linetype="DASHED")
    doc.layers.add("RINGS", color=1, linetype="DASHED")
    doc.layers.add("FINGERS", color=7)
    doc.layers.add("DIMS", color=3)

    OFFSET = 25

    minx, miny, maxx, maxy = boundary.bounds

    # ===== WAFER =====
    msp.add_lwpolyline(
        [(minx, miny), (maxx, miny), (maxx, maxy),
         (minx, maxy), (minx, miny)],
        dxfattribs={"layer": "WAFER"}
    )

    # ===== WAFER WIDTH =====
    msp.add_linear_dim(
        base=(minx, miny - OFFSET),
        p1=(minx, miny),
        p2=(maxx, miny),
        dimstyle="EZ_DIM",
        dxfattribs={"layer": "DIMS"}
    ).render()

    # Precompute finger radii
    finger_radii = create_fingers(inner_diameter, outer_diameter)

    for i, ring_data in enumerate(rings):
        cx, cy = ring_data["center"]

        r_outer = outer_diameter / 2
        r_inner = inner_diameter / 2

        # ===== RINGS =====
        msp.add_circle((cx, cy), r_outer, dxfattribs={"layer": "RINGS"})
        msp.add_circle((cx, cy), r_inner, dxfattribs={"layer": "RINGS"})

        # ===== FINGERS (FILLED WITH HATCH) =====
        for r in finger_radii:
            r_outer_f = r
            r_inner_f = r - FINGER_THICKNESS

            if r_inner_f <= r_inner:
                continue

            # Draw boundaries (optional but useful)
            msp.add_circle((cx, cy), r_outer_f, dxfattribs={"layer": "FINGERS"})
            msp.add_circle((cx, cy), r_inner_f, dxfattribs={"layer": "FINGERS"})

            outer_poly = Point(cx, cy).buffer(r_outer_f, resolution=128)
            inner_poly = Point(cx, cy).buffer(r_inner_f, resolution=128)

            # Hatch fill (arc-based for compatibility)
            hatch = msp.add_hatch(color=7)

            # Outer boundary (2 arcs)
            hatch.paths.add_polyline_path(
                list(outer_poly.exterior.coords),
                is_closed=True
            )

            # Inner boundary (hole)
            hatch.paths.add_polyline_path(
                list(inner_poly.exterior.coords),
                is_closed=True
            )

        # ===== DIMENSIONS (ONLY FIRST RING) =====
        if i == 0:

            # ---- LEFT edge margin ----
            ring_left = cx - r_outer

            msp.add_linear_dim(
                base=(minx - OFFSET - 30, cy),
                p1=(minx, cy),
                p2=(ring_left, cy),
                dimstyle="EZ_DIM",
                dxfattribs={"layer": "DIMS"}
            ).render()

            # ---- BOTTOM edge margin ----
            ring_bottom = cy - r_outer

            msp.add_linear_dim(
                base=(cx, miny - OFFSET - 40),
                p1=(cx, miny),
                p2=(cx, ring_bottom),
                angle=90,
                dimstyle="EZ_DIM",
                dxfattribs={"layer": "DIMS"}
            ).render()

            # ---- OUTER DIAMETER ----
            msp.add_diameter_dim(
                center=(cx, cy),
                radius=r_outer,
                angle=0,
                mpoint=(cx, cy - r_outer),
                dimstyle="EZ_DIM",
                dxfattribs={"layer": "DIMS"}
            ).render()

            # ---- INNER DIAMETER (LEFT) ----
            msp.add_diameter_dim(
                center=(cx, cy),
                radius=r_inner,
                angle=180,
                mpoint=(cx - r_inner, cy),
                dimstyle="EZ_DIM",
                dxfattribs={"layer": "DIMS"}
            ).render()

            # ---- FINGER SPACING ----
            if len(finger_radii) >= 2:
                r1 = finger_radii[0]
                r2 = finger_radii[1]
                inner_r1 = r1 - FINGER_THICKNESS

                msp.add_linear_dim(
                    base=(cx, maxy + OFFSET),
                    p1=(cx + inner_r1, cy),
                    p2=(cx + r2, cy),
                    dimstyle="EZ_DIM",
                    dxfattribs={"layer": "DIMS"}
                ).render()

            # ---- RING SPACING ----
            if len(rings) > 1:
                cx2, cy2 = rings[1]["center"]

                msp.add_linear_dim(
                    base=(cx, maxy + OFFSET + 20),
                    p1=(cx + r_outer, cy),
                    p2=(cx2 - r_outer, cy),  # fixed alignment
                    dimstyle="EZ_DIM",
                    dxfattribs={"layer": "DIMS"}
                ).render()

            # ---- FINGER THICKNESS ----
            if len(finger_radii) >= 1:
                r = finger_radii[0]

                msp.add_linear_dim(
                    base=(cx, maxy + OFFSET + 40),
                    p1=(cx + r, cy),
                    p2=(cx + r - FINGER_THICKNESS, cy),
                    dimstyle="EZ_DIM",
                    dxfattribs={"layer": "DIMS"}
                ).render()

    # ===== CONSTANTS PANEL =====
    text_x = maxx + 60
    text_y = maxy

    constants = [
        f"WAFER_SIZE = {(maxx - minx):.4f}",
        f"OUTER_DIAMETER = {outer_diameter:.4f}",
        f"INNER_DIAMETER = {inner_diameter:.4f}",
        f"RING_SPACING = {RING_SPACING:.4f}",
        f"MIN_EDGE_MARGIN = {EDGE_MARGIN:.4f}",
        f"ACTUAL_MARGIN_X = {actual_margin_x:.4f}",
        f"ACTUAL_MARGIN_Y = {actual_margin_y:.4f}",
        f"FINGER_THICKNESS = {FINGER_THICKNESS:.4f}",
        f"FINGER_SPACING = {FINGER_SPACING:.4f}",
        f"FINGER_TO_RING = {FINGER_TO_RING:.4f}",
    ]

    for i, line in enumerate(constants):
        txt = msp.add_text(
            line,
            dxfattribs={"height": 3, "layer": "DIMS", "color": 3}
        )
        txt.dxf.insert = (text_x, text_y - i * 5)

    doc.saveas(f"data/{filename}.dxf")
    print("DXF file saved with filled fingers")