import fingers

import ezdxf

finger_width = 0.04
finger_height = 19.9
finger_distance = 0.51
finger_block_distance = 1.06
finger_amount = 37
finger_block_amount_line = 6
finger_block_line_distance = 1
finger_block_line_amount = 7

top_busbar_top_d = bottom_busbar_bottom_d = 6.2
top_busbar_left_d = top_busbar_right_d = 0.45
bottom_busbar_left_d = bottom_busbar_right_d = -0.1
top_busbar_protrusion_w = 1.2
top_busbar_protrusion_h = 0.2

def export_finger_block_dxf(rects, filename):
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()

    for r in rects:
        coords = list(r["geometry"].exterior.coords)
        msp.add_lwpolyline(coords, close=True)

    doc.saveas(f"data/{filename}.dxf")

rects = fingers.generate_finger_block_grid(
    fingers.RowGridParams(finger_block_line_amount, finger_block_line_distance),
    fingers.FingerBlockRowParams(finger_block_amount_line, finger_block_distance),
    fingers.FingerBlockParams(finger_amount, finger_width, finger_height, finger_distance)
);

export_finger_block_dxf(rects, "square-fingers-test")