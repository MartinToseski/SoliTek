from src.geometry.circular import create_ring


def fits_inside(geometry, boundary):
    return boundary.contains(geometry)


def generate_ring_layout(boundary, inner_d, outer_d, spacing, edge_margin):
    rings = []

    step = outer_d + spacing
    minx, miny, maxx, maxy = boundary.bounds

    minx += edge_margin
    miny += edge_margin
    maxx -= edge_margin
    maxy -= edge_margin

    start_x = minx + outer_d / 2
    start_y = miny + outer_d / 2

    y = start_y
    while y <= maxy - outer_d / 2:
        x = start_x
        while x <= maxx - outer_d / 2:
            ring, outer = create_ring((x, y), inner_d, outer_d)

            if fits_inside(outer, boundary):
                rings.append((ring, outer, (x, y)))

            x += step
        y += step

    return rings