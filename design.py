"""
Combined design tool: optimize → predict → generate CAD.

Runs the optimizer to find the best design, then generates a DXF file
with the recommended parameters (finger count for rings, full config for square).

Usage:
    python design.py                                           # ring, efficiency priority
    python design.py --wafer 210                               # 210mm wafer (25 rings)
    python design.py --priority low_rs                         # optimize for low Rs
    python design.py --shape square                            # square cell
    python design.py --outer-radius 15.0 --inner-radius 12.0  # custom ring size
    python design.py --no-cad                                  # prediction only, skip DXF
"""

import argparse

from shapely.geometry import box

# ── Prediction / optimizer ──────────────────────────────
from evaluation.physics_model import SolarCellModel, CellGeometry, ring_geometry, fullsize_geometry
from evaluation.optimizer import DesignOptimizer
from evaluation.measurements import (
    get_n_rings, WAFER_SIZE, WAFER_SIZE_LARGE,
    OUTER_RADIUS, INNER_RADIUS,
    FULL_CELL_WIDTH, FULL_CELL_HEIGHT,
)

# ── CAD generation (existing pipeline) ──────────────────
from src.config.config import *
from src.core.layout import generate_ring_layout
from src.export.export_dxf import export_dxf, export_square_cell_dxf

# Square cell geometry modules
import src.geometry.square.ablation as ablation
import src.geometry.square.busbars as busbars
import src.geometry.square.cells as cells
import src.geometry.square.contact_pads as contact_pads
import src.geometry.square.dicing as dicing
import src.geometry.square.fingers as fingers
import src.geometry.square.insulation as insulation
import src.geometry.square.wafer as wafer
from src.geometry.square.generate import generate_square_cell


def print_results(results):
    """Print ranked design recommendations with trade-offs."""
    for r in results:
        p = r.prediction
        geo = r.geometry

        if r.is_recommended:
            print("\n" + "━" * 60)
            print(f"  ★ RECOMMENDED: {r.label}")
            print("━" * 60)
        else:
            print(f"\n  Alternative {r.rank}: {r.label}")
            print("─" * 60)

        print(f"  {r.description}")
        print(f"  Pmpp  = {p.Pmpp:.4f} W      Eff  = {p.NCell*100:.2f}%")
        print(f"  Isc   = {p.Isc:.4f} A      Voc  = {p.Voc:.4f} V")
        print(f"  Impp  = {p.Impp:.4f} A      Umpp = {p.Umpp:.4f} V")
        print(f"  FF    = {p.FF:.1f}%          Rs   = {p.Rs:.4f} Ω")

        if geo.shape == "ring":
            print(f"  Cells = {p.n_cells}           Area/ring = {geo.area_cm2:.4f} cm²")

        print(f"  {r.tradeoff}")


# ── Ring CAD generation ─────────────────────────────────

def generate_ring_cad(wafer_size, n_fingers, filename):
    """Generate ring layout DXF with the specified finger count."""
    wafer_box = box(0, 0, wafer_size, wafer_size)
    rings, margin_x, margin_y = generate_ring_layout(
        wafer_box, INNER_DIAMETER, OUTER_DIAMETER,
        RING_SPACING, EDGE_MARGIN,
    )
    export_dxf(
        wafer_box, rings, INNER_DIAMETER, OUTER_DIAMETER,
        margin_x, margin_y, filename,
        n_fingers=n_fingers,
    )
    return len(rings)


# ── Square CAD generation ──────────────────────────────

def generate_square_cad(filename):
    """Generate square cell DXF using existing config parameters."""
    rects, busbar_rects, cells_rects, contact_rects, \
        dicing_rects, insulation_rects, ablation_rects, wafer_rect = \
        generate_square_cell(
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
            wafer.WaferParams(sq_wafer_w_margin, sq_wafer_h_margin, sq_wafer_corner_w),
        )
    export_square_cell_dxf(
        rects, filename,
        busbar_rects, cells_rects, contact_rects,
        dicing_rects, insulation_rects, ablation_rects, wafer_rect,
    )


# ── Main ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SoliTek Design Tool: optimize → predict → generate CAD"
    )
    parser.add_argument("--shape", choices=["ring", "square"], default="ring")
    parser.add_argument("--wafer", type=float, default=WAFER_SIZE,
                        help=f"Wafer size in mm (default: {WAFER_SIZE})")
    parser.add_argument("--outer-radius", type=float, default=OUTER_RADIUS)
    parser.add_argument("--inner-radius", type=float, default=INNER_RADIUS)
    parser.add_argument("--priority",
                        choices=["efficiency", "power", "low_rs", "high_ff"],
                        default="efficiency")
    parser.add_argument("--temp", type=float, default=25.0,
                        help="Operating temperature °C")
    parser.add_argument("--irr", type=float, default=1000.0,
                        help="Irradiance W/m²")
    parser.add_argument("--results", type=int, default=5,
                        help="Number of design alternatives")
    parser.add_argument("--no-cad", action="store_true",
                        help="Skip CAD generation, prediction only")
    parser.add_argument("--filename", type=str, default=None,
                        help="DXF output filename (without .dxf)")
    args = parser.parse_args()

    # ═══════════════════════════════════════════════════
    # 1. OPTIMIZE
    # ═══════════════════════════════════════════════════
    optimizer = DesignOptimizer()
    n_rings = get_n_rings(args.wafer)

    print(f"\nSoliTek Design Tool")
    print(f"Shape: {args.shape}, Priority: {args.priority}")
    print(f"Conditions: {args.temp}°C, {args.irr} W/m²")

    if args.shape == "ring":
        print(f"Wafer: {args.wafer}mm, {n_rings} rings")
        print(f"Ring: Ro={args.outer_radius}mm, Ri={args.inner_radius}mm")

        results = optimizer.search(
            shape="ring",
            outer_radius_mm=args.outer_radius,
            inner_radius_mm=args.inner_radius,
            n_cells=n_rings,
            priority=args.priority,
            temperature=args.temp,
            irradiance=args.irr,
            n_results=args.results,
        )
    else:
        print(f"Cell: {FULL_CELL_WIDTH}×{FULL_CELL_HEIGHT}mm")

        results = optimizer.search(
            shape="square",
            cell_width_mm=FULL_CELL_WIDTH,
            cell_height_mm=FULL_CELL_HEIGHT,
            priority=args.priority,
            temperature=args.temp,
            irradiance=args.irr,
            n_results=args.results,
        )

    # ═══════════════════════════════════════════════════
    # 2. PRINT RECOMMENDATIONS
    # ═══════════════════════════════════════════════════
    print_results(results)
    best = results[0]

    if args.no_cad:
        print("\n  (CAD generation skipped — run without --no-cad to generate DXF)")
        return

    # ═══════════════════════════════════════════════════
    # 3. GENERATE CAD WITH RECOMMENDED PARAMETERS
    # ═══════════════════════════════════════════════════
    rec_fingers = best.geometry.n_fingers
    rec_busbars = best.geometry.n_busbars

    if args.shape == "ring":
        fname = args.filename or f"design_ring_{int(args.wafer)}mm_{rec_fingers}F"

        print(f"\n{'═' * 60}")
        print(f"  Generating ring CAD: data/{fname}.dxf")
        print(f"  Applying recommended finger count: {rec_fingers}")
        print(f"{'═' * 60}")

        n_generated = generate_ring_cad(args.wafer, rec_fingers, fname)
        print(f"  Done: {n_generated} rings × {rec_fingers} fingers")

    else:
        fname = args.filename or f"design_square_{rec_fingers}F_{rec_busbars}BB"

        print(f"\n{'═' * 60}")
        print(f"  Generating square cell CAD: data/{fname}.dxf")
        print(f"{'═' * 60}")

        generate_square_cad(fname)

        print(f"  Done: square cell with current config")
        print(f"  Optimizer recommends: {rec_fingers} fingers, {rec_busbars} busbars")


if __name__ == "__main__":
    main()