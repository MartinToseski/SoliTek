"""
Design search engine.

Sweeps over finger-count and width variations, returns ranked designs
with trade-off explanations.
"""

WAFER_SIZE = 158.75
WAFER_SIZE_LARGE = 210
RING_SPACING = 1.4905
EDGE_MARGIN = 2.1965
FINGERS_PER_RING = 4
FINGER_THICKNESS = 0.025
FINGER_SPACING = 0.4899
FINGER_TO_RING = 0.2576
OUTER_DIAMETER = 37.46
INNER_DIAMETER = 33.26
PAD_WIDTH = 0.025
PAD_LENGTH = 0.15
PAD_GAP = 0.301

# === SQUARE CELL CONFIGS ===
sq_finger_width = 0.04
sq_finger_height = 19.9
sq_finger_distance = 0.51
sq_finger_block_distance = 1.06
sq_finger_amount = 37
sq_finger_block_amount_line = 6
sq_finger_block_line_distance = 1
sq_finger_block_line_amount = 7

sq_top_busbar_top_d = sq_bottom_busbar_bottom_d = 6.2
sq_top_busbar_left_d = sq_top_busbar_right_d = 0.45
sq_bottom_busbar_left_d = sq_bottom_busbar_right_d = -0.1
sq_top_busbar_protrusion_w = 1.2
sq_top_busbar_protrusion_h = 0.2

sq_cell_w_margin = 0.53
sq_cell_h_margin = 0.5

sq_wafer_w_margin = 16.675
sq_wafer_h_margin = 6.225
sq_wafer_corner_w = 1.512

sq_contact_w = 0.025
sq_contact_h = 0.15
sq_contact_gap_x = 0.525
sq_contact_gap_y = 0.3
sq_contact_margin_x = 0.538
sq_contact_margin_y = 0.5

sq_dicing_protrusion_x = 17.3
sq_dicing_protrusion_y = 6.85

sq_insulation_w = 0.5
sq_insulation_h = 0.7
sq_insulation_protrusion = 0.13
sq_insulation_h_margin = 0.15
sq_insulation_gap = 0.6
sq_insulation_inset = 0.35

sq_ablation_w        = 0.8
sq_ablation_h        = 20.3
sq_ablation_gap      = 0.3
sq_ablation_x_margin = 0.15
sq_ablation_wafer_margin = 1.0

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
        outer_radius_mm=OUTER_DIAMETER / 2,
        inner_radius_mm=INNER_DIAMETER / 2,
        cell_width_mm=WAFER_SIZE,
        cell_height_mm=WAFER_SIZE,
        n_cells=16,
        priority="efficiency",
        temperature=25.0,
        irradiance=1000.0,
        n_results=5,
        # square user-adjustable
        sq_finger_amount=sq_finger_amount,
        sq_finger_width=sq_finger_width,
        sq_finger_distance=sq_finger_distance,
        sq_finger_block_distance=sq_finger_block_distance,
        sq_contact_w=sq_contact_w,
        sq_contact_h=sq_contact_h,
        sq_contact_gap_x=sq_contact_gap_x,
        sq_contact_gap_y=sq_contact_gap_y,
    ):
        cond = OperatingConditions(irradiance, temperature)
        if shape == "ring":
            candidates = self._ring_candidates(outer_radius_mm, inner_radius_mm, n_cells, cond)
        else:
            sq_params = dict(
                finger_amount=sq_finger_amount,
                finger_width=sq_finger_width,
                finger_distance=sq_finger_distance,
                finger_block_distance=sq_finger_block_distance,
                contact_w=sq_contact_w,
                contact_h=sq_contact_h,
                contact_gap_x=sq_contact_gap_x,
                contact_gap_y=sq_contact_gap_y,
            )
            candidates = self._square_candidates(cell_width_mm, cell_height_mm, n_cells, cond, sq_params)

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

    def _square_candidates(self, w, h, n_cells, cond, sq_params):
        out = []
        base_fingers = sq_params["finger_amount"]
        finger_w     = sq_params["finger_width"]
        finger_dist  = sq_params["finger_distance"]
        blk_dist     = sq_params["finger_block_distance"]

        for finger_scale in [0.75, 1.0, 1.25, 1.5, 2.0]:
            nf = max(1, round(base_fingers * finger_scale))
            pitch = finger_dist  # spacing is fixed by user param, not derived
            for nb in [4, 6, 8, 12]:
                geo = CellGeometry(
                    shape="square",
                    cell_width_mm=w,
                    cell_height_mm=h,
                    n_fingers=nf,
                    finger_pitch_mm=pitch,
                    finger_width_um=finger_w * 1000,   # mm → µm
                    n_busbars=nb,
                    busbar_width_mm=blk_dist,
                )
                pred = self.model.predict_cell(geo, cond)
                out.append(DesignResult(
                    geometry=geo,
                    prediction=pred,
                    label=f"Square {nf}F/{finger_w*1000:.0f}µm",
                    description=(
                        f"{nf} fingers, {finger_w*1000:.0f}µm width, "
                        f"{n_cells} cells on wafer"
                    ),
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