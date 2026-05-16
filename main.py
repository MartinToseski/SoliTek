from shapely.geometry import box
from src.config.config import *
from src.core.layout import generate_ring_layout
from src.export.export_dxf import export_dxf, export_square_cell_dxf

import src.geometry.square.ablation as ablation
import src.geometry.square.busbars as busbars
import src.geometry.square.cells as cells
import src.geometry.square.contact_pads as contact_pads
import src.geometry.square.dicing as dicing
import src.geometry.square.fingers as fingers
import src.geometry.square.insulation as insulation
import src.geometry.square.wafer as wafer
from src.geometry.square.generate import generate_square_cell

# ── Prediction imports ──────────────────────────────────
from evaluation.physics_model import SolarCellModel, ring_geometry, fullsize_geometry


def print_prediction(label, pred, n_cells=None):
    """Print a compact prediction summary."""
    print(f"\n  {'─' * 50}")
    print(f"  Predicted performance: {label}")
    print(f"  {'─' * 50}")
    print(f"  Pmpp  = {pred.Pmpp:.4f} W      Eff  = {pred.NCell*100:.2f}%")
    print(f"  Isc   = {pred.Isc:.4f} A      Voc  = {pred.Voc:.4f} V")
    print(f"  Impp  = {pred.Impp:.4f} A      Umpp = {pred.Umpp:.4f} V")
    print(f"  FF    = {pred.FF:.1f}%          Rs   = {pred.Rs:.4f} Ω")
    if n_cells:
        print(f"  Cells = {n_cells}")


if __name__ == '__main__':
    model = SolarCellModel()

    # ═══════════════════════════════════════════════════
    # RING CELLS — CAD generation (existing, untouched)
    # ═══════════════════════════════════════════════════
    wafer1 = box(0, 0, WAFER_SIZE, WAFER_SIZE)
    wafer2 = box(0, 0, WAFER_SIZE_LARGE, WAFER_SIZE_LARGE)

    rings1, actual_margin_x1, actual_margin_y1 = generate_ring_layout(wafer1, INNER_DIAMETER, OUTER_DIAMETER, RING_SPACING, EDGE_MARGIN)
    rings2, actual_margin_x2, actual_margin_y2 = generate_ring_layout(wafer2, INNER_DIAMETER, OUTER_DIAMETER, RING_SPACING, EDGE_MARGIN)
    print(f"Small wafer -> Generated {len(rings1)} rings")
    print(f"Large wafer -> Generated {len(rings2)} rings")

    export_dxf(wafer1, rings1, INNER_DIAMETER, OUTER_DIAMETER, actual_margin_x1, actual_margin_y1, "irregular_rings_small")
    export_dxf(wafer2, rings2, INNER_DIAMETER, OUTER_DIAMETER, actual_margin_x2, actual_margin_y2, "irregular_rings_large")

    # ── Predict ring wafer performance ──────────────────
    geo_ring = ring_geometry()
    pred_small = model.predict_wafer(geo_ring, n_cells=len(rings1))
    pred_large = model.predict_wafer(geo_ring, n_cells=len(rings2))

    print_prediction(
        f"Small wafer ({WAFER_SIZE:.0f}mm, {len(rings1)} rings)",
        pred_small, n_cells=len(rings1),
    )
    print_prediction(
        f"Large wafer ({WAFER_SIZE_LARGE:.0f}mm, {len(rings2)} rings)",
        pred_large, n_cells=len(rings2),
    )

    # ═══════════════════════════════════════════════════
    # SQUARE CELLS — CAD generation (existing, untouched)
    # ═══════════════════════════════════════════════════
    rects, busbar_rects, cells_rects, contact_rects, dicing_rects, insulation_rects, ablation_rects, wafer_rect = generate_square_cell(
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

    export_square_cell_dxf(rects, "square-cells-test", busbar_rects, cells_rects, contact_rects, dicing_rects, insulation_rects, ablation_rects, wafer_rect)

    # ── Predict square cell performance ─────────────────
    geo_full = fullsize_geometry()
    pred_full = model.predict_cell(geo_full)
    print_prediction(
        f"Square cell ({geo_full.cell_width_mm:.0f}×{geo_full.cell_height_mm:.0f}mm)",
        pred_full,
    )