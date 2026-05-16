from shapely.geometry import box

from src.config.config import *

from . import ablation
from . import busbars
from . import cells
from . import contact_pads
from . import dicing
from . import fingers
from . import insulation
from . import wafer

def generate_square_cell(row_grid_params: fingers.RowGridParams,
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