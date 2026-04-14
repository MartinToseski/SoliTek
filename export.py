import ezdxf
from geometry import create_fingers
from config import FINGER_THICKNESS


def export_dxf(boundary, rings, inner_diameter, outer_diameter):
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM

    msp = doc.modelspace()

    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[0.5, 0.25, -0.25])

    # ===== LAYERS =====
    doc.layers.add("WAFER", color=1, linetype="DASHED")
    doc.layers.add("RINGS", color=1, linetype="DASHED")
    doc.layers.add("FINGERS", color=7)

    # ===== WAFER =====
    minx, miny, maxx, maxy = boundary.bounds
    msp.add_lwpolyline(
        [
            (minx, miny),
            (maxx, miny),
            (maxx, maxy),
            (minx, maxy),
            (minx, miny),
        ],
        dxfattribs={"layer": "WAFER"}
    )

    # ===== RINGS =====
    for ring, outer in rings:
        center = outer.centroid.coords[0]

        # Outer ring
        msp.add_circle(
            center,
            outer_diameter / 2,
            dxfattribs={"layer": "RINGS"}
        )

        # Inner ring
        msp.add_circle(
            center,
            inner_diameter / 2,
            dxfattribs={"layer": "RINGS"}
        )

        # ===== FINGERS =====
        finger_radii = create_fingers(center, inner_diameter, outer_diameter)

        for r in finger_radii:
            r_outer = r
            r_inner = r - FINGER_THICKNESS

            if r_inner <= inner_diameter / 2:
                continue

            # Outer boundary of finger
            msp.add_circle(
                center,
                r_outer,
                dxfattribs={"layer": "FINGERS"}
            )

            # Inner boundary of finger
            msp.add_circle(
                center,
                r_inner,
                dxfattribs={"layer": "FINGERS"}
            )

    doc.saveas("wafer_layout.dxf")
    print("DXF saved!")