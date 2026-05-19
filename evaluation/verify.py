"""
Validate physics model predictions against measured SoliTek data.

Usage from project root:
    python -m prediction.verify
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evaluation.physics_model import SolarCellModel, ring_geometry, fullsize_geometry, OperatingConditions
from evaluation.measurements import get_n_rings, WAFER_SIZE
from evaluation.ml_correction import HybridPredictor


def load_data():
    try:
        import pandas as pd
    except ImportError:
        print("Install pandas + openpyxl:  pip install pandas openpyxl")
        sys.exit(1)

    root = os.path.join(os.path.dirname(__file__), "..")
    data_dir = os.path.join(root, "data")
    dfs = {}

    for key, fname, sheet in [
        ("ring_f1", "Electrical_measurements.xlsx",      "2"),
        ("ring_f2", "Electrical_measurements_ring.xlsx",  "Foglio1"),
        ("full",    "Full_size_cell.xlsx",                "data"),
    ]:
        path = os.path.join(data_dir, fname)
        if os.path.exists(path):
            dfs[key] = pd.read_excel(path, sheet_name=sheet, header=0)
        else:
            print(f"  ⚠ {fname} not found in data/ — skipping")
    return dfs


def _compare(pred, measured):
    params = [
        ("Isc",  pred.Isc,  measured["Isc"],  "A"),
        ("Voc",  pred.Voc,  measured["Voc"],  "V"),
        ("Rs",   pred.Rs,   measured["Rs"],   "Ω"),
        ("FF",   pred.FF,   measured["FF"],   "%"),
        ("Pmpp", pred.Pmpp, measured["Pmpp"], "W"),
    ]
    print(f"  {'Param':<8} {'Predicted':>10} {'Measured':>10} {'Error':>8}")
    print(f"  {'-'*40}")
    ok = True
    for name, p, m, unit in params:
        err = (p - m) / m * 100 if m != 0 else 0
        flag = "✓" if abs(err) < 5 else "⚠"
        if abs(err) >= 5:
            ok = False
        print(f"  {name:<8} {p:>9.4f}{unit} {m:>9.4f}{unit} {err:>+7.1f}% {flag}")
    status = "All within 5%" if ok else "Some >5% — tune MaterialParams"
    print(f"  ── {status} ──")


def main():
    print("\nSoliTek Physics Model — Verification\n")
    model = SolarCellModel()
    dfs = load_data()

    # ── Ring wafers ──
    print("=" * 60)
    print("RING WAFER VERIFICATION (158mm, 4×4 = 16 rings)")
    print("=" * 60)
    geo = ring_geometry()
    n = get_n_rings(WAFER_SIZE)
    print(f"Ring area: {geo.area_cm2:.4f} cm², {n} rings\n")

    for label, key in [("File 1", "ring_f1"), ("File 2", "ring_f2")]:
        if key not in dfs:
            continue
        df = dfs[key]
        df = df[df["Class"] != "Shunt"] if "Class" in df.columns else df
        cond = OperatingConditions(df["E"].mean(), df["Temperature"].mean())
        pred = model.predict_wafer(geo, n, cond)
        measured = {
            "Isc": df["Isc"].mean(), "Voc": df["Uoc"].mean(),
            "Rs": df["Rs"].mean(), "FF": df["FF"].mean(),
            "Pmpp": df["Pmpp"].mean(),
        }
        print(f"  {label}  (n={len(df)}, E={cond.irradiance:.0f}, T={cond.temperature:.1f}°C)")
        _compare(pred, measured)
        print()

    # ── Full-size ──
    print("=" * 60)
    print("FULL-SIZE VERIFICATION (158×158mm ISC-ZEBRA)")
    print("=" * 60)
    if "full" in dfs:
        df = dfs["full"]
        df = df[(df["BIN_Comment"] != "Shunt") & (df["FF"] < 100)]
        geo_f = fullsize_geometry()
        cond = OperatingConditions(df["E"].mean(), df["Temperature"].mean())
        pred = model.predict_cell(geo_f, cond)
        measured = {
            "Isc": df["Isc"].mean(), "Voc": df["Uoc"].mean(),
            "Rs": df["Rs"].mean(), "FF": df["FF"].mean(),
            "Pmpp": df["Pmpp"].mean(),
        }
        print(f"  Full-size  (n={len(df)}, E={cond.irradiance:.0f}, T={cond.temperature:.1f}°C)")
        _compare(pred, measured)
    print()

    # ── 2xFinger ──
    print("=" * 60)
    print("2×FINGER EFFECT")
    print("=" * 60)
    n = get_n_rings(WAFER_SIZE)
    p4 = model.predict_wafer(ring_geometry(n_fingers=4), n)
    p8 = model.predict_wafer(ring_geometry(n_fingers=8), n)
    rs_d = (p8.Rs - p4.Rs) / p4.Rs * 100
    pm_d = (p8.Pmpp - p4.Pmpp) / p4.Pmpp * 100
    print(f"  4F: Rs={p4.Rs:.4f}Ω, Pmpp={p4.Pmpp:.4f}W")
    print(f"  8F: Rs={p8.Rs:.4f}Ω, Pmpp={p8.Pmpp:.4f}W")
    print(f"  Rs change:   {rs_d:+.1f}% (measured: -26.4%)")
    print(f"  Pmpp change: {pm_d:+.1f}% (measured: +3.6%)")
    print()


if __name__ == "__main__":
    main()