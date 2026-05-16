class DicingParams:
    def __init__(self, protrusion_x, protrusion_y):
        self.protrusion_x = protrusion_x
        self.protrusion_y = protrusion_y


def generate_grid_lines(cells, dp: DicingParams):
    xs, ys = set(), set()
    for cell in cells:
        min_x, min_y, max_x, max_y = cell.bounds
        xs.update([min_x, max_x])
        ys.update([min_y, max_y])

    grid_min_x = min(xs)
    grid_max_x = max(xs)
    grid_min_y = min(ys)
    grid_max_y = max(ys)

    lines = []

    for x in xs:
        lines.append(((x, grid_min_y - dp.protrusion_y),
                      (x, grid_max_y + dp.protrusion_y)))

    for y in ys:
        lines.append(((grid_min_x - dp.protrusion_x, y),
                      (grid_max_x + dp.protrusion_x, y)))

    return lines