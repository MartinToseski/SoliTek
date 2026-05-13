from shapely.geometry import box

from config.config import *

import ablation
import busbars
import cells
import contact_pads
import dicing
import fingers
import insulation
import wafer

import ezdxf

def export_square_cell_dxf(rects, filename, busbars_rects, cells_rects, contacts_rects, dicing_rects, insulation_rects, wafer):
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()

    doc.header["$LUNITS"] = 2
    doc.header["$LUPREC"] = 4

    doc.layers.add("FINGERS", color=1)
    doc.layers.add("BUSBARS", color=3)
    doc.layers.add("CELLS",   color=5)
    doc.layers.add("WAFER",   color=1)
    doc.layers.add("CONTACT_PADS", color=7)
    doc.layers.add("DICING", color=30)
    doc.layers.add("INSULATION", color=2)
    doc.layers.add("ABLATION", color=4)

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

    for rect in ablation_rects:
        for g in getattr(rect, "geoms", [rect]):
            msp.add_lwpolyline(list(g.exterior.coords), close=True, dxfattribs={"layer": "ABLATION"})
    
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
                                             ablation_params: ablation.AblationParams,
                                             wafer_params: wafer.WaferParams,
                                             origin=(0, 0)):
    all_rects    = []
    all_busbars  = []
    all_cells    = []
    all_contacts = []
    dicing_lines = []
    all_insulation = []
    all_ablation = []

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
    for cell in all_cells:
        all_ablation.extend(
            ablation.generate_ablation_with_wafer_margin(
                cell, wafer_rect, ablation_params
            )
        )

    wafer_inner = wafer_rect.buffer(-ablation_params.wafer_margin)

    for i, cell in enumerate(all_cells):
        row = i // sq_finger_block_amount_line
        base_rects = ablation.generate_ablation_with_wafer_margin(cell, wafer_rect, ablation_params)
        all_ablation.extend(base_rects)
        cy    = (cell.bounds[1] + cell.bounds[3]) / 2
        r_bot = cy - ablation_params.h / 2
        r_top = cy + ablation_params.h / 2

        if row == sq_finger_block_line_amount - 1:
            for r in base_rects:
                clipped = box(r.bounds[0], r_top + ablation_params.gap * 2, r.bounds[2], r_top + ablation_params.gap * 2 + ablation_params.h).intersection(wafer_inner)
                if not clipped.is_empty:
                    all_ablation.append(clipped)

        if row == 0:
            for r in base_rects:
                clipped = box(r.bounds[0], r_bot - ablation_params.gap * 2 - ablation_params.h, r.bounds[2], r_bot - ablation_params.gap * 2).intersection(wafer_inner)
                if not clipped.is_empty:
                    all_ablation.append(clipped)


    return all_rects, all_busbars, all_cells, all_contacts, dicing_lines, all_insulation, all_ablation, wafer_rect


rects, busbar_rects, cells_rects, contact_rects, dicing_rects, insulation_rects, ablation_rects, wafer_rect = generate_finger_block_grid(
    fingers.RowGridParams(sq_finger_block_line_amount, sq_finger_block_line_distance),
    fingers.FingerBlockRowParams(sq_finger_block_amount_line, sq_finger_block_distance),
    fingers.FingerBlockParams(sq_finger_amount, sq_finger_width, sq_finger_height, sq_finger_distance),
    busbars.BusbarParams(sq_top_busbar_top_d, sq_bottom_busbar_bottom_d,
                         sq_top_busbar_left_d, sq_top_busbar_right_d,
                         sq_bottom_busbar_left_d, sq_bottom_busbar_right_d,
                         sq_top_busbar_protrusion_w, sq_top_busbar_protrusion_h),
    cells.CellParams(sq_cell_w_margin, sq_cell_h_margin),
    contact_pads.ContactParams(sq_contact_w, sq_contact_h,
                               sq_contact_gap_x, sq_contact_gap_y,
                               sq_contact_margin_x, sq_contact_margin_y),
    dicing.DicingParams(sq_dicing_protrusion_x, sq_dicing_protrusion_y),
    insulation.InsulationParams(sq_insulation_w, sq_insulation_h, sq_insulation_protrusion,
                                sq_insulation_h_margin, sq_insulation_gap, sq_insulation_inset),
    ablation.AblationParams(sq_ablation_w, sq_ablation_h, sq_ablation_gap, sq_ablation_x_margin, sq_ablation_wafer_margin),
    wafer.WaferParams(sq_wafer_w_margin, sq_wafer_h_margin, sq_wafer_corner_w)
)

export_square_cell_dxf(rects, "square-cells-test", busbar_rects, cells_rects, contact_rects, dicing_rects, insulation_rects, wafer_rect)