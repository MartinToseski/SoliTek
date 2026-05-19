"""
Design search engine.

Sweeps over finger-count and width variations, returns ranked designs
with trade-off explanations.
"""

import os
from dataclasses import dataclass
from evaluation.physics_model import SolarCellModel, CellGeometry, CellPrediction, OperatingConditions
from evaluation.ml_correction import HybridPredictor


@dataclass
class DesignResult:
    geometry: CellGeometry
    prediction: CellPrediction
    label: str
    description: str
    rank: int = 0
    is_recommended: bool = False
    tradeoff: str = ""


class DesignOptimizer:
    """
    Usage:
        opt = DesignOptimizer()
        results = opt.search(shape="ring", n_cells=16, priority="efficiency")
    """

    def __init__(self, model=None):
        ml_path = "evaluation/ml_model.pkl"
        if os.path.exists(ml_path):
            predictor = HybridPredictor.load(ml_path)
            print("Using hybrid physics+ML predictor")
        else:
            predictor = SolarCellModel()
            print("Using physics-only predictor (no ML model found)")
        self.model = model or predictor

    def search(
        self,
        shape="ring",
        outer_radius_mm=18.73,
        inner_radius_mm=16.63,
        cell_width_mm=158.75,
        cell_height_mm=158.75,
        n_cells=16,
        priority="efficiency",
        temperature=25.0,
        irradiance=1000.0,
        n_results=5,
    ):
        cond = OperatingConditions(irradiance, temperature)

        if shape == "ring":
            candidates = self._ring_candidates(outer_radius_mm, inner_radius_mm, n_cells, cond)
        else:
            candidates = self._square_candidates(cell_width_mm, cell_height_mm, cond)

        key = {
            "efficiency": lambda c: -c.prediction.NCell,
            "power":      lambda c: -c.prediction.Pmpp,
            "low_rs":     lambda c: c.prediction.Rs,
            "high_ff":    lambda c: -c.prediction.FF,
        }.get(priority, lambda c: -c.prediction.NCell)

        candidates.sort(key=key)

        best = candidates[0] if candidates else None
        alts = self._pick_diverse(candidates[1:], n_results - 1)

        results = []
        if best:
            best.rank = 0
            best.is_recommended = True
            best.tradeoff = self._explain_best(best, priority)
            results.append(best)

        for i, alt in enumerate(alts):
            alt.rank = i + 1
            alt.tradeoff = self._explain_tradeoff(alt, best)
            results.append(alt)

        return results

    def _ring_candidates(self, Ro, Ri, n_cells, cond):
        out = []
        for nf in [2, 4, 6, 8, 12, 16]:
            for fw in [30, 50, 70]:
                geo = CellGeometry(
                    shape="ring", outer_radius_mm=Ro, inner_radius_mm=Ri,
                    n_fingers=nf, finger_pitch_mm=0.55, finger_width_um=fw,
                    n_busbars=2, busbar_width_mm=2.0,
                )
                pred = self.model.predict_wafer(geo, n_cells, cond)
                out.append(DesignResult(
                    geometry=geo, prediction=pred,
                    label=f"Ring {nf}F/{fw}µm",
                    description=(
                        f"{nf} radial fingers, {fw}µm width, "
                        f"{n_cells} cells on wafer"
                    ),
                ))
        return out

    def _square_candidates(self, w, h, cond):
        out = []
        for nf in [144, 216, 288, 360, 432]:
            for nb in [4, 6, 8, 12]:
                pitch = w / nf
                geo = CellGeometry(
                    shape="square", cell_width_mm=w, cell_height_mm=h,
                    n_fingers=nf, finger_pitch_mm=pitch, finger_width_um=50,
                    n_busbars=nb, busbar_width_mm=1.5,
                )
                pred = self.model.predict_cell(geo, cond)
                out.append(DesignResult(
                    geometry=geo, prediction=pred,
                    label=f"Square {nf}F/{nb}BB",
                    description=f"{nf} fingers at {pitch:.2f}mm, {nb} busbars",
                ))
        return out

    def _pick_diverse(self, candidates, n):
        selected, seen = [], set()
        for c in candidates:
            key = c.geometry.n_fingers
            if key not in seen:
                seen.add(key)
                selected.append(c)
            if len(selected) >= n:
                break
        return selected

    def _explain_best(self, design, priority):
        p = design.prediction
        reasons = {
            "efficiency": f"highest efficiency at {p.NCell*100:.2f}%",
            "power":      f"maximum power at {p.Pmpp:.4f} W",
            "low_rs":     f"lowest series resistance at {p.Rs:.4f} Ω",
            "high_ff":    f"highest fill factor at {p.FF:.1f}%",
        }
        return f"Recommended: {reasons.get(priority, 'best overall')}."

    def _explain_tradeoff(self, alt, best):
        a, b = alt.prediction, best.prediction
        diffs = [
            ("efficiency", (a.NCell - b.NCell) / max(b.NCell, 1e-10) * 100, False),
            ("Rs",         (a.Rs - b.Rs) / max(b.Rs, 1e-10) * 100,         True),
            ("FF",         (a.FF - b.FF) / max(b.FF, 1e-10) * 100,         False),
        ]
        good, bad = [], []
        for name, pct, lower_better in diffs:
            if abs(pct) < 0.5:
                continue
            is_good = (pct < 0) if lower_better else (pct > 0)
            (good if is_good else bad).append(f"{pct:+.1f}% {name}")
        result = ""
        if good:
            result += "Advantages: " + ", ".join(good) + ". "
        if bad:
            result += "Trade-offs: " + ", ".join(bad) + "."
        return result or "Very similar to recommended design."