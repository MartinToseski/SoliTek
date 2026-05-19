"""
Data analysis + ML correction layer — single script.

Analyzes physics model residuals, produces visualization data,
trains XGBoost correction, and reports improvement.

Usage from C:\\SoliTek:
    python -m evaluation.ml_correction              # analyze + train
    python -m evaluation.ml_correction --save       # also save model
"""

import os
import sys
import math
import pickle
import argparse
import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.physics_model import (
    SolarCellModel, ring_geometry, fullsize_geometry,
    OperatingConditions, CellPrediction,
)
from evaluation.measurements import get_n_rings, WAFER_SIZE


# ═══════════════════════════════════════════════════════
# DATA LOADING + PHYSICS PREDICTIONS
# ═══════════════════════════════════════════════════════

def load_and_prepare():
    """Load all datasets, run physics model, compute residuals."""
    model = SolarCellModel()
    data_dir = Path(__file__).parent.parent / "data"
    geo_ring = ring_geometry()
    geo_full = fullsize_geometry()

    datasets = []

    # Ring File 1 (210mm wafer, 25 rings)
    path = data_dir / "Electrical_measurements.xlsx"
    if path.exists():
        df = pd.read_excel(path, sheet_name="2", header=0)
        df = df[df["Class"] != "Shunt"].copy()
        df["source"] = "ring_f1"
        df["cell_type"] = "ring"
        df["n_cells"] = 25
        datasets.append(df)

    # Ring File 2 (158mm wafer, 16 rings)
    path = data_dir / "Electrical_measurements_ring.xlsx"
    if path.exists():
        df = pd.read_excel(path, sheet_name="Foglio1", header=0)
        df = df[df["Class"] != "Shunt"].copy()
        df["source"] = "ring_f2"
        df["cell_type"] = "ring"
        df["n_cells"] = get_n_rings(WAFER_SIZE)
        datasets.append(df)

    # Full-size
    path = data_dir / "Full_size_cell.xlsx"
    if path.exists():
        df = pd.read_excel(path, sheet_name="data", header=0)
        df = df[(df["BIN_Comment"] != "Shunt") & (df["FF"] < 100)].copy()
        df["source"] = "full"
        df["cell_type"] = "full"
        df["n_cells"] = 1
        datasets.append(df)

    if not datasets:
        print("No data files found in data/")
        sys.exit(1)

    df_all = pd.concat(datasets, ignore_index=True)

    records = []
    for _, row in df_all.iterrows():
        cond = OperatingConditions(row["E"], row["Temperature"])

        if row["cell_type"] == "ring":
            pred = model.predict_wafer(geo_ring, int(row["n_cells"]), cond)
        else:
            pred = model.predict_cell(geo_full, cond)

        rec = {
            "source": row["source"],
            "cell_type": row["cell_type"],
            "LotCounter": row["LotCounter"],
            "E": row["E"],
            "Temperature": row["Temperature"],
            # Physics predictions
            "phys_Isc": pred.Isc,
            "phys_Voc": pred.Voc,
            "phys_Rs": pred.Rs,
            "phys_FF": pred.FF,
            "phys_Pmpp": pred.Pmpp,
            # Measured
            "meas_Pmpp": row["Pmpp"],
            "meas_Isc": row["Isc"],
            "meas_Voc": row["Uoc"],
            "meas_FF": row["FF"],
            "meas_Rs": row["Rs"],
            # Residuals
            "res_Pmpp": row["Pmpp"] - pred.Pmpp,
            "res_Isc": row["Isc"] - pred.Isc,
            "res_Voc": row["Uoc"] - pred.Voc,
            "res_FF": row["FF"] - pred.FF,
        }

        # Low-light ratios
        if "Isc_2" in row and pd.notna(row.get("Isc_2")) and row["Isc"] > 0:
            rec["Isc_ratio"] = row["Isc_2"] / row["Isc"]
        if "FF_2" in row and pd.notna(row.get("FF_2")) and row["FF"] > 0:
            rec["FF_ratio"] = row["FF_2"] / row["FF"]

        # EL quality
        if "Comment" in row and pd.notna(row.get("Comment")):
            rec["EL_good"] = 1 if "GOOD" in str(row["Comment"]).upper() else 0

        records.append(rec)

    return pd.DataFrame(records)


# ═══════════════════════════════════════════════════════
# ANALYSIS
# ═══════════════════════════════════════════════════════

def run_analysis(df):
    """Analyze residuals and determine if ML is worthwhile."""
    print("\n" + "=" * 60)
    print("RESIDUAL ANALYSIS")
    print("=" * 60)

    # ── 1. Overall stats ──
    print("\n1. OVERALL RESIDUAL STATISTICS")
    for t in ["res_Pmpp", "res_Isc", "res_Voc", "res_FF"]:
        v = df[t]
        print(f"   {t:>10}: mean={v.mean():+.4f}  std={v.std():.4f}  "
              f"[{v.min():.4f}, {v.max():.4f}]")

    # ── 2. By dataset ──
    print("\n2. BY DATASET")
    for src in sorted(df["source"].unique()):
        sub = df[df["source"] == src]
        print(f"   {src} (n={len(sub)}):")
        print(f"     Pmpp residual: mean={sub['res_Pmpp'].mean():+.4f}, std={sub['res_Pmpp'].std():.4f}")
        print(f"     Isc  residual: mean={sub['res_Isc'].mean():+.4f}, std={sub['res_Isc'].std():.4f}")

    # ── 3. By lot — THE KEY TABLE ──
    print("\n3. BY WAFER LOT (lot-to-lot variation)")
    lot_stats = df.groupby(["source", "LotCounter"]).agg(
        n=("res_Pmpp", "count"),
        Pmpp_bias=("res_Pmpp", "mean"),
        Pmpp_std=("res_Pmpp", "std"),
        Isc_bias=("res_Isc", "mean"),
    ).round(4)
    print(lot_stats.to_string())

    # ── 4. Signal-to-noise ──
    lot_biases = df.groupby("LotCounter")["res_Pmpp"].mean()
    between_lot_spread = lot_biases.std()
    within_lot_noise = df.groupby("LotCounter")["res_Pmpp"].std().mean()
    snr = between_lot_spread / within_lot_noise if within_lot_noise > 0 else 0

    print(f"\n4. SIGNAL-TO-NOISE RATIO")
    print(f"   Between-lot bias spread: {between_lot_spread:.4f} W")
    print(f"   Within-lot noise:        {within_lot_noise:.4f} W")
    print(f"   Signal/noise ratio:      {snr:.2f}x")

    # ── 5. Feature correlations ──
    print(f"\n5. FEATURE CORRELATIONS WITH Pmpp RESIDUAL")
    feat_cols = ["E", "Temperature", "phys_Isc", "phys_Voc", "phys_FF", "phys_Rs"]
    opt_cols = ["Isc_ratio", "FF_ratio", "EL_good"]
    for f in feat_cols + [c for c in opt_cols if c in df.columns]:
        if df[f].notna().sum() > 10:
            r = df["res_Pmpp"].corr(df[f])
            bar = "█" * int(abs(r) * 30)
            print(f"   {f:>15}: r={r:+.3f} {bar}")

    # ── 6. Decision ──
    print(f"\n{'=' * 60}")
    if snr > 1.0:
        print(f"VERDICT: STRONG LOT EFFECT (SNR={snr:.1f}x) — ML WILL HELP")
    elif snr > 0.5:
        print(f"VERDICT: MODERATE LOT EFFECT (SNR={snr:.1f}x) — ML WORTH TRYING")
    else:
        print(f"VERDICT: WEAK LOT EFFECT (SNR={snr:.1f}x) — ML MAY NOT HELP")
    print("=" * 60)

    return snr, lot_stats


# ═══════════════════════════════════════════════════════
# ML TRAINING
# ═══════════════════════════════════════════════════════

FEATURE_COLS = [
    "phys_Isc", "phys_Voc", "phys_Rs", "phys_FF", "phys_Pmpp",
    "E", "Temperature",
]
OPTIONAL_FEATURES = ["Isc_ratio", "FF_ratio", "EL_good"]


def get_features(df):
    cols = FEATURE_COLS.copy()
    for f in OPTIONAL_FEATURES:
        if f in df.columns and df[f].notna().sum() > len(df) * 0.5:
            cols.append(f)
    return cols


def train_ml(df, target="res_Pmpp"):
    """Train XGBoost on residuals with grouped cross-validation."""
    try:
        from xgboost import XGBRegressor
        from sklearn.model_selection import GroupKFold
    except ImportError:
        print("\nInstall dependencies: pip install xgboost scikit-learn")
        return None, None

    feature_cols = get_features(df)
    X = df[feature_cols].fillna(0).values
    y = df[target].values
    groups = df["LotCounter"].values

    n_groups = len(set(groups))
    n_splits = min(5, n_groups)

    print(f"\n{'=' * 60}")
    print(f"ML TRAINING: {target}")
    print(f"{'=' * 60}")
    print(f"   Features:  {feature_cols}")
    print(f"   Samples:   {len(X)}")
    print(f"   Lot groups: {n_groups}")
    print(f"   CV folds:  {n_splits}")

    model = XGBRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        min_child_weight=5,
        random_state=42,
    )

    # Grouped cross-validation
    gkf = GroupKFold(n_splits=n_splits)
    cv_preds = np.zeros_like(y)
    fold_maes = []

    print(f"\n   Fold results:")
    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups)):
        model.fit(X[train_idx], y[train_idx])
        preds = model.predict(X[test_idx])
        cv_preds[test_idx] = preds

        mae = np.mean(np.abs(preds - y[test_idx]))
        fold_maes.append(mae)
        test_lots = sorted(set(groups[test_idx]))
        print(f"     Fold {fold+1}: MAE={mae:.4f} W  (held out: {test_lots})")

    # ── Results ──
    physics_errors = np.abs(y)
    corrected_errors = np.abs(y - cv_preds)

    physics_mae = np.mean(physics_errors)
    corrected_mae = np.mean(corrected_errors)
    improvement = (1 - corrected_mae / physics_mae) * 100

    # MAPE on final Pmpp
    final_pmpp = df["meas_Pmpp"].values
    physics_pmpp = df["phys_Pmpp"].values
    corrected_pmpp = physics_pmpp + cv_preds
    physics_mape = np.mean(np.abs(physics_pmpp - final_pmpp) / np.abs(final_pmpp)) * 100
    corrected_mape = np.mean(np.abs(corrected_pmpp - final_pmpp) / np.abs(final_pmpp)) * 100

    # R²
    ss_res = np.sum((y - cv_preds)**2)
    ss_tot = np.sum((y - np.mean(y))**2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    print(f"\n   {'─' * 50}")
    print(f"   RESULTS:")
    print(f"   {'─' * 50}")
    print(f"   Physics-only MAE:        {physics_mae:.4f} W")
    print(f"   After ML correction MAE: {corrected_mae:.4f} W")
    print(f"   Improvement:             {improvement:.1f}%")
    print(f"   {'─' * 50}")
    print(f"   Physics-only MAPE:       {physics_mape:.2f}%")
    print(f"   After ML correction MAPE:{corrected_mape:.2f}%")
    print(f"   {'─' * 50}")
    print(f"   R² on residuals:         {r2:.3f}")

    if r2 > 0.5:
        print(f"   ✓ Strong systematic patterns captured")
    elif r2 > 0.3:
        print(f"   ~ Moderate patterns — ML helps but room for improvement")
    else:
        print(f"   ⚠ Weak patterns — most error is random noise")

    # Feature importance
    model.fit(X, y)  # final fit on all data
    importance = sorted(zip(feature_cols, model.feature_importances_),
                       key=lambda x: -x[1])

    print(f"\n   Feature importance:")
    for feat, imp in importance:
        bar = "█" * int(imp * 40)
        print(f"     {feat:<15} {imp:.3f} {bar}")

    # ── Per-dataset improvement ──
    print(f"\n   Per-dataset MAPE:")
    for src in sorted(df["source"].unique()):
        mask = df["source"] == src
        m = df.loc[mask, "meas_Pmpp"].values
        p = df.loc[mask, "phys_Pmpp"].values
        c = p + cv_preds[mask.values]
        p_mape = np.mean(np.abs(p - m) / np.abs(m)) * 100
        c_mape = np.mean(np.abs(c - m) / np.abs(m)) * 100
        print(f"     {src:>10}: physics={p_mape:.2f}% → corrected={c_mape:.2f}%  "
              f"({p_mape - c_mape:+.2f}pp)")

    return model, feature_cols


# ═══════════════════════════════════════════════════════
# HYBRID PREDICTOR
# ═══════════════════════════════════════════════════════

class HybridPredictor:
    """Combined physics + ML prediction."""

    def __init__(self, physics_model, ml_model, feature_cols):
        self.physics = physics_model
        self.ml = ml_model
        self.feature_cols = feature_cols

    def predict(self, geometry, conditions=None, n_cells=1):
        conditions = conditions or OperatingConditions()

        if n_cells > 1:
            pred = self.physics.predict_wafer(geometry, n_cells, conditions)
        else:
            pred = self.physics.predict_cell(geometry, conditions)

        features = {
            "phys_Isc": pred.Isc, "phys_Voc": pred.Voc,
            "phys_Rs": pred.Rs, "phys_FF": pred.FF,
            "phys_Pmpp": pred.Pmpp,
            "E": conditions.irradiance, "Temperature": conditions.temperature,
        }
        for col in self.feature_cols:
            if col not in features:
                features[col] = 0

        X = np.array([[features[c] for c in self.feature_cols]])
        correction = self.ml.predict(X)[0]

        # Safety clamp:
        max_correction = 0.05 * pred.Pmpp

        correction = max(
            -max_correction,
            min(max_correction, correction)
        )

        pred.Pmpp += correction
        if pred.Umpp > 0:
            pred.Impp = pred.Pmpp / pred.Umpp
        area_m2 = geometry.area_cm2 * n_cells * 1e-4
        if area_m2 > 0 and conditions.irradiance > 0:
            pred.NCell = pred.Pmpp / (conditions.irradiance * area_m2)

        return pred

    def save(self, path):
        with open(path, "wb") as f:
            pickle.dump({"ml_model": self.ml, "feature_cols": self.feature_cols}, f)
        print(f"\n   Model saved to {path}")

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            data = pickle.load(f)
        return cls(SolarCellModel(), data["ml_model"], data["feature_cols"])

    def predict_cell(self, geometry, conditions=None):
        return self.predict(
            geometry=geometry,
            conditions=conditions,
            n_cells=1,
        )

    def predict_wafer(self, geometry, n_cells, conditions=None):
        return self.predict(
            geometry=geometry,
            conditions=conditions,
            n_cells=n_cells,
        )


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Analysis + ML training")
    parser.add_argument("--save", action="store_true",
                        help="Save trained model to evaluation/ml_model.pkl")
    parser.add_argument("--target", default="res_Pmpp",
                        choices=["res_Pmpp", "res_Isc", "res_Voc", "res_FF"])
    args = parser.parse_args()

    print("SoliTek — Data Analysis & ML Correction Layer")
    print("=" * 60)

    # 1. Load and prepare
    df = load_and_prepare()
    print(f"Loaded {len(df)} samples from {df['source'].nunique()} datasets")
    print(f"Lots: {sorted(df['LotCounter'].unique())}")

    # 2. Analyze residuals
    snr, lot_stats = run_analysis(df)

    # 3. Train ML if signal exists
    if snr < 0.3:
        print("\nSkipping ML training — insufficient signal.")
        return

    ml_model, feature_cols = train_ml(df, target=args.target)

    if ml_model is None:
        return

    # 4. Save if requested
    if args.save:
        hybrid = HybridPredictor(SolarCellModel(), ml_model, feature_cols)
        save_path = Path(__file__).parent / "ml_model.pkl"
        hybrid.save(str(save_path))
        print(f"   To use: HybridPredictor.load('{save_path}')")


if __name__ == "__main__":
    main()