import ezdxf
from shapely.geometry import Point, box
import svgwrite
from config import WAFER_SIZE, RING_SPACING, EDGE_MARGIN, FINGER_TO_RING, FINGER_SPACING, FINGER_THICKNESS, FINGERS_PER_RING


#OUTER_DIAMETER = 37.46
#INNER_DIAMETER = 33.26


# ================= GEOMETRY =================
def create_ring(center, inner_d, outer_d):
    outer = Point(center).buffer(outer_d / 2.0)
    inner = Point(center).buffer(inner_d / 2.0)
    return outer.difference(inner), outer


def fits_inside(geometry, boundary):
    return boundary.contains(geometry)


def generate_rings(boundary, inner_d, outer_d, spacing, edge_margin):
    rings = []

    step = outer_d + spacing
    minx, miny, maxx, maxy = boundary.bounds

    # Apply edge margin
    minx += edge_margin
    miny += edge_margin
    maxx -= edge_margin
    maxy -= edge_margin

    y = miny + outer_d / 2
    while y <= maxy - outer_d / 2:
        x = minx + outer_d / 2
        while x <= maxx - outer_d / 2:
            ring, outer = create_ring((x, y), inner_d, outer_d)

            if fits_inside(outer, boundary):
                rings.append((ring, outer))

            x += step
        y += step

    return rings


# ================= FINGERS =================
def create_fingers(center, inner_d, outer_d):
    finger_radii = []

    r_outer = outer_d / 2
    r_inner = inner_d / 2

    # Start just inside outer ring
    current_r = r_outer - FINGER_TO_RING

    for _ in range(FINGERS_PER_RING):
        if current_r <= r_inner:
            break

        finger_radii.append(current_r)

        # Move inward
        current_r -= (FINGER_SPACING + FINGER_THICKNESS)

    return finger_radii


# ================= SVG =================
def draw_svg(boundary, rings):
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
        finger_radii = create_fingers(center, INNER_DIAMETER, OUTER_DIAMETER)

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


# ================= DXF =================
def export_dxf(boundary, rings):
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
        msp.add_circle(center, OUTER_DIAMETER / 2)
        msp.add_circle(center, INNER_DIAMETER / 2)

        # Circular fingers
        finger_radii = create_fingers(center, INNER_DIAMETER, OUTER_DIAMETER)

        for r in finger_radii:
            msp.add_circle(center, r)

    doc.saveas("wafer_layout.dxf")
    print("DXF saved: wafer_layout.dxf")


# ================= MAIN =================
if __name__ == '__main__':
    wafer = box(0, 0, WAFER_SIZE, WAFER_SIZE)

    rings = generate_rings(
        wafer,
        INNER_DIAMETER,
        OUTER_DIAMETER,
        RING_SPACING,
        EDGE_MARGIN
    )

    print(f"Generated {len(rings)} rings")

    draw_svg(wafer, rings)
    export_dxf(wafer, rings)