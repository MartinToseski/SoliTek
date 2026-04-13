import ezdxf
import svgwrite
from geometry import create_fingers
from config import WAFER_SIZE, RING_SPACING, EDGE_MARGIN, FINGER_TO_RING, FINGER_SPACING, FINGER_THICKNESS, FINGERS_PER_RING


def draw_svg(boundary, rings, inner_diameter, outer_diameter):
    dwg = svgwrite.Drawing("wafer_layout.svg", size=("500px", "500px"))

    dwg.add(dwg.rect(
        insert=(0, 0),
        size=("100%", "100%"),
        fill="black"
    ))

    # Wafer boundary
    minx, miny, maxx, maxy = boundary.bounds
    dwg.add(dwg.rect(
        insert=(minx, miny),
        size=(maxx - minx, maxy - miny),
        stroke="red",
        fill="none",
        stroke_width=2
    ))

    for ring, outer in rings:
        center = outer.centroid.coords[0]

        # Outer ring
        dwg.add(dwg.polygon(
            list(outer.exterior.coords),
            stroke="red",
            fill="none",
            stroke_width=1
        ))

        # Inner ring
        for interior in ring.interiors:
            dwg.add(dwg.polygon(
                list(interior.coords),
                stroke="red",
                fill="none",
                stroke_width=1
            ))

        # Circular fingers
        finger_radii = create_fingers(center, inner_diameter, outer_diameter)

        for r in finger_radii:
            dwg.add(dwg.circle(
                center=center,
                r=r,
                stroke="white",
                fill="none",
                stroke_width=FINGER_THICKNESS * 20  # scaled for visibility
            ))

    dwg.save()
    print("SVG saved: wafer_layout.svg")


def export_dxf(boundary, rings, inner_diameter, outer_diameter):
    doc = ezdxf.new()
    msp = doc.modelspace()

    # Wafer boundary
    minx, miny, maxx, maxy = boundary.bounds
    msp.add_lwpolyline([
        (minx, miny),
        (maxx, miny),
        (maxx, maxy),
        (minx, maxy),
        (minx, miny)
    ])

    for ring, outer in rings:
        center = outer.centroid.coords[0]

        # Rings
        msp.add_circle(center, outer_diameter / 2)
        msp.add_circle(center, inner_diameter / 2)

        # Circular fingers
        finger_radii = create_fingers(center, inner_diameter, outer_diameter)

        for r in finger_radii:
            msp.add_circle(center, r)

    doc.saveas("wafer_layout.dxf")
    print("DXF saved: wafer_layout.dxf")