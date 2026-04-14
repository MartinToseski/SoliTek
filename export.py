import ezdxf
from geometry import create_fingers
from config import (
    WAFER_SIZE,
    RING_SPACING,
    EDGE_MARGIN,
    FINGER_THICKNESS,
    FINGER_SPACING,
    FINGER_TO_RING
)


def export_dxf(boundary, rings, inner_diameter, outer_diameter):
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM

    msp = doc.modelspace()

    if "EZ_DIM" not in doc.dimstyles:
        doc.dimstyles.new("EZ_DIM")

    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[0.5, 0.25, -0.25])

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

    # ===== Wafer size =====
    msp.add_linear_dim(
        base=(minx, miny - OFFSET),
        p1=(minx, miny),
        p2=(maxx, miny),
        dimstyle="EZ_DIM",
        dxfattribs={"layer": "DIMS"}
    ).render()

    for i, (ring, outer, center) in enumerate(rings):
        cx, cy = center

        # ===== Rings =====
        msp.add_circle(center, outer_diameter / 2, dxfattribs={"layer": "RINGS"})
        msp.add_circle(center, inner_diameter / 2, dxfattribs={"layer": "RINGS"})

        # ===== Fingers =====
        finger_radii = create_fingers(center, inner_diameter, outer_diameter)

        for r in finger_radii:
            r_outer = r
            r_inner = r - FINGER_THICKNESS

            if r_inner <= inner_diameter / 2:
                continue

            msp.add_circle(center, r_outer, dxfattribs={"layer": "FINGERS"})
            msp.add_circle(center, r_inner, dxfattribs={"layer": "FINGERS"})

        # ===== DIMENSIONS (ONLY FIRST RING) =====
        if i == 0:

            # ---- Edge margin ----
            ring_left = cx - outer_diameter / 2

            msp.add_linear_dim(
                base=(minx - OFFSET, cy),
                p1=(minx, cy),
                p2=(ring_left, cy),
                dimstyle="EZ_DIM",
                dxfattribs={"layer": "DIMS"}
            ).render()

            # ---- Outer diameter ----
            msp.add_diameter_dim(
                center=center,
                radius=outer_diameter / 2,
                angle=0,
                dimstyle="EZ_DIM",
                dxfattribs={"layer": "DIMS"}
            ).render()

            # ---- Inner diameter ----
            msp.add_diameter_dim(
                center=center,
                radius=inner_diameter / 2,
                angle=90,
                dimstyle="EZ_DIM",
                dxfattribs={"layer": "DIMS"}
            ).render()

            # ---- Finger spacing (correct: inner → outer) ----
            if len(finger_radii) >= 2:
                r1 = finger_radii[0]
                r2 = finger_radii[1]

                inner_r1 = r1 - FINGER_THICKNESS

                p1 = (cx + inner_r1, cy)
                p2 = (cx + r2, cy)

                msp.add_linear_dim(
                    base=(cx, maxy + OFFSET),
                    p1=p1,
                    p2=p2,
                    dimstyle="EZ_DIM",
                    dxfattribs={"layer": "DIMS"}
                ).render()

            # ---- Ring spacing ----
            if len(rings) > 1:
                _, _, center2 = rings[1]
                cx2, cy2 = center2

                r_outer = outer_diameter / 2

                p1 = (cx + r_outer, cy)
                p2 = (cx2 - r_outer, cy2)

                msp.add_linear_dim(
                    base=(cx, maxy + OFFSET + 20),
                    p1=p1,
                    p2=p2,
                    dimstyle="EZ_DIM",
                    dxfattribs={"layer": "DIMS"}
                ).render()

            # ---- Finger thickness ----
            if len(finger_radii) >= 1:
                r = finger_radii[0]

                p1 = (cx + r, cy)
                p2 = (cx + r - FINGER_THICKNESS, cy)

                msp.add_linear_dim(
                    base=(cx, maxy + OFFSET + 40),
                    p1=p1,
                    p2=p2,
                    dimstyle="EZ_DIM",
                    dxfattribs={"layer": "DIMS"}
                ).render()

    # ===== CONSTANTS PANEL =====
    text_x = maxx + 60
    text_y = maxy

    constants = [
        f"WAFER_SIZE = {WAFER_SIZE}",
        f"OUTER_DIAMETER = {outer_diameter}",
        f"INNER_DIAMETER = {inner_diameter}",
        f"RING_SPACING = {RING_SPACING}",
        f"EDGE_MARGIN = {EDGE_MARGIN}",
        f"FINGER_THICKNESS = {FINGER_THICKNESS}",
        f"FINGER_SPACING = {FINGER_SPACING}",
        f"FINGER_TO_RING = {FINGER_TO_RING}",
    ]

    for i, line in enumerate(constants):
        txt = msp.add_text(
            line,
            dxfattribs={"height": 3, "layer": "DIMS", "color": 3}
        )
        txt.dxf.insert = (text_x, text_y - i * 5)

    doc.saveas("wafer_layout.dxf")
    print("DXF saved with FULL dimension set")