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
    usable_width  = maxx - minx
    usable_height = maxy - miny
    nx = int((usable_width  + spacing) // step)
    ny = int((usable_height + spacing) // step)
    grid_width  = nx * outer_d + (nx - 1) * spacing
    grid_height = ny * outer_d + (ny - 1) * spacing
    offset_x = (usable_width  - grid_width)  / 2
    offset_y = (usable_height - grid_height) / 2
    start_x = minx + offset_x + outer_d / 2
    start_y = miny + offset_y + outer_d / 2
    actual_margin_x = edge_margin + offset_x
    actual_margin_y = edge_margin + offset_y
    for i in range(ny):
        for j in range(nx):
            x = start_x + j * step
            y = start_y + i * step
            ring, outer = create_ring((x, y), inner_d, outer_d)
            if fits_inside(outer, boundary):
                rings.append({
                    "geometry": ring,
                    "outer":    outer,
                    "center":   (x, y)
                })
    return rings, actual_margin_x, actual_margin_y