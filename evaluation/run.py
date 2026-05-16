"""
Design optimizer entry point.

Usage from project root:
    python -m prediction.run                    # default ring optimization
    python -m prediction.run --shape square     # full-size cell
    python -m prediction.run --wafer 210        # 210mm wafer (25 rings)
    python -m prediction.run --priority low_rs  # optimize for low resistance
    python -m prediction.run --demo             # run all 5 demo scenarios
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evaluation.measurements import WAFER_SIZE, WAFER_SIZE_LARGE, get_n_rings, OUTER_RADIUS, INNER_RADIUS, FULL_CELL_WIDTH, FULL_CELL_HEIGHT
from evaluation.physics_model import SolarCellModel
from evaluation.optimizer import DesignOptimizer


def print_results(results):
    print()
    for r in results:
        p = r.prediction
        geo = r.geometry

        if r.is_recommended:
            print("━" * 60)
            print(f"  ★ RECOMMENDED: {r.label}")
            print("━" * 60)
        else:
            print(f"  Alternative {r.rank}: {r.label}")
            print("─" * 60)

        print(f"  {r.description}")
        print()
        print(f"  Pmpp  = {p.Pmpp:.4f} W      Efficiency = {p.NCell*100:.2f}%")
        print(f"  Isc   = {p.Isc:.4f} A      Voc  = {p.Voc:.4f} V")
        print(f"  Impp  = {p.Impp:.4f} A      Umpp = {p.Umpp:.4f} V")
        print(f"  FF    = {p.FF:.1f}%          Rs   = {p.Rs:.4f} Ω")

        if geo.shape == "ring":
            print(f"  Cells = {p.n_cells}           Area/ring = {geo.area_cm2:.4f} cm²")

        print(f"\n  {r.tradeoff}")
        print()


def run_demo(model):
    optimizer = DesignOptimizer(model)

    scenarios = [
        ("Smart watch face",
         "Small ring cells for a circular watch face",
         dict(shape="ring", outer_radius_mm=10, inner_radius_mm=8,
              n_cells=4, priority="efficiency", temperature=30)),
        ("Standard 158mm production cell",
         "Full-size ISC-ZEBRA, maximize power",
         dict(shape="square", priority="power")),
        ("BIPV facade tile",
         "100×100mm building-integrated PV",
         dict(shape="square", cell_width_mm=100, cell_height_mm=100,
              priority="efficiency")),
        ("Vehicle roof panel",
         "High temperature operation at 55°C",
         dict(shape="square", priority="power", temperature=55)),
        ("IoT outdoor sensor",
         "Tiny ring cell for low-power sensor",
         dict(shape="ring", outer_radius_mm=6, inner_radius_mm=4,
              n_cells=1, priority="low_rs")),
    ]

    for name, desc, kwargs in scenarios:
        print("\n" + "═" * 60)
        print(f"  SCENARIO: {name}")
        print(f"  {desc}")
        print("═" * 60)
        results = optimizer.search(n_results=4, **kwargs)
        print_results(results)


def main():
    parser = argparse.ArgumentParser(description="SoliTek Design Optimizer")
    parser.add_argument("--shape", choices=["ring", "square"], default="ring")
    parser.add_argument("--wafer", type=int, default=WAFER_SIZE,
                        help=f"Wafer size mm (default: {WAFER_SIZE})")
    parser.add_argument("--priority",
                        choices=["efficiency", "power", "low_rs", "high_ff"],
                        default="efficiency")
    parser.add_argument("--temp", type=float, default=25.0)
    parser.add_argument("--irr", type=float, default=1000.0)
    parser.add_argument("--demo", action="store_true",
                        help="Run all 5 demo scenarios")
    args = parser.parse_args()

    model = SolarCellModel()

    if args.demo:
        run_demo(model)
        return

    optimizer = DesignOptimizer(model)
    n_rings = get_n_rings(args.wafer)

    print(f"\nSoliTek Design Optimizer")
    print(f"Shape: {args.shape}, Priority: {args.priority}")
    print(f"Conditions: {args.temp}°C, {args.irr} W/m²")

    if args.shape == "ring":
        print(f"Wafer: {args.wafer}mm, {n_rings} rings")
        results = optimizer.search(
            shape="ring", n_cells=n_rings,
            outer_radius_mm=OUTER_RADIUS,
            inner_radius_mm=INNER_RADIUS,
            priority=args.priority,
            temperature=args.temp, irradiance=args.irr,
        )
    else:
        results = optimizer.search(
            shape="square",
            cell_width_mm=FULL_CELL_WIDTH,
            cell_height_mm=FULL_CELL_HEIGHT,
            priority=args.priority,
            temperature=args.temp, irradiance=args.irr,
        )

    print_results(results)


if __name__ == "__main__":
    main()