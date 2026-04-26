from shapely.geometry import box

class FingerBlockParams:
    def __init__(self, amount, w, h, d) -> None:
        self.amount = amount
        self.w = w
        self.h = h
        self.d = d

class FingerBlockRowParams:
    def __init__(self, amount, d) -> None:
        self.amount = amount
        self.d = d

class RowGridParams:
    def __init__(self, amount, d) -> None:
        self.amount = amount
        self.d = d

def generate_square_finger_block(finger_block_params: FingerBlockParams, origin=(0, 0)):
    rects = []
    step_x = finger_block_params.w + finger_block_params.d
    start_x, start_y = origin

    for j in range(finger_block_params.amount):
        x0 = start_x + j * step_x
        y0 = start_y
        rect = box(x0, y0, x0 + finger_block_params.w, y0 + finger_block_params.h)
        rects.append({
            "geometry": rect,
            "center": (x0 + finger_block_params.w / 2, y0 + finger_block_params.h / 2),
            "origin": (x0, y0),
        })

    return rects

def generate_finger_block_array(block_row_params: FingerBlockRowParams, finger_block_params: FingerBlockParams, origin=(0, 0)):
    blocks = []
    block_w = finger_block_params.amount * finger_block_params.w + (finger_block_params.amount - 1) * finger_block_params.d

    for b in range(block_row_params.amount):
        block_origin = (origin[0] + b * (block_w + block_row_params.d), origin[1])
        rects = generate_square_finger_block(finger_block_params, origin=block_origin)
        blocks.append(rects)

    return blocks

def generate_finger_block_grid(row_grid_params: RowGridParams, block_row_params: FingerBlockRowParams, finger_block_params: FingerBlockParams, origin=(0, 0)):
    all_rects = []

    for row in range(row_grid_params.amount):
        row_origin = (origin[0], origin[1] + row * (finger_block_params.h + row_grid_params.d))
        blocks = generate_finger_block_array(block_row_params, finger_block_params, origin=row_origin)
        all_rects.extend([r for block in blocks for r in block])

    return all_rects