import busbars
import cells
import contact_pads
import dicing
import fingers
import insulation
import wafer

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

cell_w_margin = 0.53
cell_h_margin = 0.5

wafer_w_margin = 16.675
wafer_h_margin = 6.225
wafer_corner_w = 1.512

contact_w = 0.025
contact_h = 0.15
contact_gap_x = 0.525
contact_gap_y = 0.3
contact_margin_x = 0.538
contact_margin_y = 0.5

dicing_protrusion_x = 17.3
dicing_protrusion_y = 6.85

insulation_w = 0.5
insulation_h = 0.7
insulation_protrusion = 0.13
insulation_h_margin = 0.15
insulation_gap = 0.6
insulation_inset = 0.35

def export_finger_block_dxf(rects, filename, busbars_rects, cells_rects, contacts_rects, dicing_rects, insulation_rects, wafer):
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()

    doc.header["$LUNITS"] = 2
    doc.header["$LUPREC"] = 4

    doc.layers.add("FINGERS", color=1)
    doc.layers.add("BUSBARS", color=3)
    doc.layers.add("CELLS",   color=5)
    doc.layers.add("WAFER",   color=1)
    doc.layers.add("CONTACT_PADS", color=2)
    doc.layers.add("DICING", color=4)
    doc.layers.add("INSULATION", color=2)

    for r in rects:
        coords = list(r["geometry"].exterior.coords)
        msp.add_lwpolyline(coords, close=True, dxfattribs={"layer": "FINGERS"})

    for geom in busbars_rects:
        for g in getattr(geom, "geoms", [geom]):
            msp.add_lwpolyline(list(g.exterior.coords), close=True, dxfattribs={"layer": "BUSBARS"})

    for cell in cells_rects:
        msp.add_lwpolyline(list(cell.exterior.coords), close=True, dxfattribs={"layer": "CELLS"})

    for c in contacts_rects:
        msp.add_lwpolyline(list(c.exterior.coords), close=True, dxfattribs={"layer": "CONTACT_PADS"})

    for start, end in dicing_rects:
        msp.add_line(start, end, dxfattribs={"layer": "DICING"})

    for rect in insulation_rects:
        msp.add_lwpolyline(list(rect.exterior.coords), close=True, dxfattribs={"layer": "INSULATION"})

    msp.add_lwpolyline(list(wafer.exterior.coords), close=True, dxfattribs={"layer": "WAFER"})

    doc.saveas(f"../../../data/{filename}.dxf")

def generate_finger_block_grid(row_grid_params: fingers.RowGridParams,
                                             block_row_params: fingers.FingerBlockRowParams,
                                             finger_block_params: fingers.FingerBlockParams,
                                             busbar_params: busbars.BusbarParams,
                                             cell_params: cells.CellParams,
                                             contact_pads_params: contact_pads.ContactParams,
                                             dicing_params: dicing.DicingParams,
                                             insulation_params: insulation.InsulationParams,
                                             wafer_params: wafer.WaferParams,
                                             origin=(0, 0)):
    all_rects    = []
    all_busbars  = []
    all_cells    = []
    all_contacts = []
    dicing_lines = []
    all_insulation = []

    block_w = (finger_block_params.amount * finger_block_params.w
               + (finger_block_params.amount - 1) * finger_block_params.d)

    for row in range(row_grid_params.amount):
        row_origin = (origin[0], origin[1] + row * (finger_block_params.h + row_grid_params.d))
        for b in range(block_row_params.amount):
            block_origin = (row_origin[0] + b * (block_w + block_row_params.d), row_origin[1])
            all_rects.extend(fingers.generate_square_finger_block(finger_block_params, origin=block_origin))
            all_busbars.extend(busbars.generate_busbars_for_block(
                block_origin, block_w, finger_block_params.h, busbar_params
            ))
            cell = cells.generate_cell_for_block(
                block_origin, block_w, finger_block_params.h,
                cell_params
            )
            all_cells.append(cell)
            all_insulation.extend(insulation.generate_insulation_for_block(
                block_origin, block_w, finger_block_params.h, cell, busbar_params, insulation_params
            ))
            all_insulation.append(insulation.generate_insulation_cell_inset(cell, insulation_params))
            dicing_lines.extend(dicing.generate_grid_lines(all_cells, dicing_params))
            all_contacts.extend(contact_pads.generate_contact_pads_for_cell(cell, contact_pads_params))

    wafer_rect = wafer.generate_wafer(all_cells, wafer_params)

    return all_rects, all_busbars, all_cells, all_contacts, dicing_lines, all_insulation, wafer_rect


rects, busbar_rects, cells_rects, contact_rects, dicing_rects, insulation_rects, wafer_rect = generate_finger_block_grid(
    fingers.RowGridParams(finger_block_line_amount, finger_block_line_distance),
    fingers.FingerBlockRowParams(finger_block_amount_line, finger_block_distance),
    fingers.FingerBlockParams(finger_amount, finger_width, finger_height, finger_distance),
    busbars.BusbarParams(top_busbar_top_d, bottom_busbar_bottom_d,
                         top_busbar_left_d, top_busbar_right_d,
                         bottom_busbar_left_d, bottom_busbar_right_d,
                         top_busbar_protrusion_w, top_busbar_protrusion_h),
    cells.CellParams(cell_w_margin, cell_h_margin),
    contact_pads.ContactParams(contact_w, contact_h,
                               contact_gap_x, contact_gap_y,
                               contact_margin_x, contact_margin_y),
    dicing.DicingParams(dicing_protrusion_x, dicing_protrusion_y),
    insulation.InsulationParams(insulation_w, insulation_h, insulation_protrusion,
                                insulation_h_margin, insulation_gap, insulation_inset),
    wafer.WaferParams(wafer_w_margin, wafer_h_margin, wafer_corner_w)
)

export_finger_block_dxf(rects, "square-cells-test", busbar_rects, cells_rects, contact_rects, dicing_rects, insulation_rects, wafer_rect)