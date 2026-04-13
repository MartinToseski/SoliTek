import math
import ezdxf
from shapely.geometry import Point, box
from shapely.affinity import rotate
import svgwrite
from config import WAFER_SIZE, RING_SPACING, EDGE_MARGIN, FINGER_TO_RING, FINGER_SPACING, FINGER_THICKNESS, FINGERS_PER_RING

OUTER_DIAMETER = 37.46
INNER_DIAMETER = 33.26


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


def draw_svg(boundary, rings):
    dwg = svgwrite.Drawing("wafer_layout.svg", size=("500px", "500px"))

    # Wafer boundary
    bx, by, bx2, by2 = boundary.bounds
    dwg.add(dwg.rect(
        insert=(bx, by),
        size=(bx2 - bx, by2 - by),
        stroke="red",
        fill="none",
        stroke_width=2
    ))

    # Rings
    for ring, outer in rings:
        # outer circle
        dwg.add(dwg.polygon(
            list(outer.exterior.coords),
            stroke="black",
            fill="none",
            stroke_width=1
        ))

        # inner hole
        for interior in ring.interiors:
            dwg.add(dwg.polygon(
                list(interior.coords),
                stroke="gray",
                fill="none",
                stroke_width=1
            ))

    dwg.save()
    print("wafer_layout.svg created")


if __name__ == '__main__':
    # Wafer box
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