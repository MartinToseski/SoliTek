"""
Physics-based solar cell performance model.

Predicts: Isc, Voc, Rs, Rsh, FF, Pmpp, Umpp, Impp, NCell
from cell geometry and operating conditions.

Calibrated on SoliTek BC ring data (344 cells) and
ISC-ZEBRA full-size data (331 cells).
"""

import math
from dataclasses import dataclass
from evaluation.measurements import (
    OUTER_RADIUS, INNER_RADIUS,
    RING_N_FINGERS, RING_FINGER_PITCH_MM, RING_FINGER_WIDTH_UM,
    RING_N_BUSBARS, RING_BUSBAR_WIDTH_MM,
    FULL_CELL_WIDTH, FULL_CELL_HEIGHT, FULL_N_FINGERS,
    FULL_FINGER_PITCH_MM, FULL_FINGER_WIDTH_UM,
    FULL_N_BUSBARS, FULL_BUSBAR_WIDTH_MM,
)


# ── Data classes ────────────────────────────────────────
@dataclass
class CellGeometry:
    """Physical design of a single solar cell element."""
    shape: str                     # "ring" or "square"
    area_cm2: float = 0.0
    n_fingers: int = 4
    finger_pitch_mm: float = 0.55
    finger_width_um: float = 50.0
    outer_radius_mm: float = 0.0   # ring only
    inner_radius_mm: float = 0.0   # ring only
    cell_width_mm: float = 0.0     # square only
    cell_height_mm: float = 0.0    # square only
    n_busbars: int = 0
    busbar_width_mm: float = 0.0

    def __post_init__(self):
        if self.area_cm2 == 0:
            if self.shape == "ring" and self.outer_radius_mm > 0:
                self.area_cm2 = math.pi * (self.outer_radius_mm**2 - self.inner_radius_mm**2) / 100
            elif self.shape == "square" and self.cell_width_mm > 0:
                self.area_cm2 = (self.cell_width_mm * self.cell_height_mm / 100)

    @property
    def finger_length_mm(self):
        if self.shape == "ring":
            return self.outer_radius_mm - self.inner_radius_mm
        if self.n_busbars > 0:
            return self.cell_width_mm / (2 * self.n_busbars)
        return self.cell_width_mm / 2


@dataclass
class OperatingConditions:
    irradiance: float = 1000.0   # W/m²
    temperature: float = 25.0    # °C


@dataclass
class CellPrediction:
    Isc: float = 0.0
    Voc: float = 0.0
    Rs: float = 0.0
    Rsh: float = 0.0
    FF: float = 0.0        # percentage
    Pmpp: float = 0.0
    Umpp: float = 0.0
    Impp: float = 0.0
    NCell: float = 0.0     # efficiency (fraction)
    n_cells: int = 1

    def to_dict(self):
        return {k: round(v, 6) for k, v in self.__dict__.items()}


# ── Calibrated material constants ───────────────────────
@dataclass
class MaterialParams:
    """
    Two technology bases, calibrated from SoliTek measured data.

    BC ring cells:  Jsc ≈ 57.4 mA/cm² (back-contact, zero front shading)
    ISC-ZEBRA full: Jsc ≈ 39.4 mA/cm² (different architecture)
    """
    # BC ring technology
    Jsc_ring: float = 0.0574
    J0_ring: float = 1.5e-13
    Rsh_ring: float = 109.0       # Ω per ring
    Umpp_Voc_ring: float = 0.858

    # ISC-ZEBRA full-size technology
    Jsc_full: float = 0.0394
    J0_full: float = 1.8e-13
    Rsh_full: float = 23.2        # Ω
    Umpp_Voc_full: float = 0.819

    # Shared
    beta_Voc: float = -0.0021     # V/°C

    # Rs: empirical baselines from measured data with power-law scaling
    # Ring: measured wafer Rs = 0.036 Ω with 16 parallel rings → 0.576 Ω/ring
    Rs_baseline_ring: float = 0.576
    Rs_ref_fingers_ring: int = 4
    # Full-size: measured Rs = 0.002 Ω at 288 fingers
    Rs_baseline_full: float = 0.002
    Rs_ref_fingers_full: int = 288
    Rs_ref_busbars_full: int = 8
    # Exponent from 2xFinger data: 8F → 26.4% lower Rs
    Rs_alpha: float = 0.442

    # FF: geometry-dependent Rs→FF coupling
    ff_rs_coeff_ring: float = 1.95
    ff_rs_coeff_full: float = 3.70


# ── Physics model ───────────────────────────────────────
class SolarCellModel:
    """
    Analytical 1-diode model for BC and ISC-ZEBRA cells.

    Usage:
        model = SolarCellModel()
        geo = ring_geometry()
        cell = model.predict_cell(geo)           # one ring
        wafer = model.predict_wafer(geo, n=16)   # full wafer
    """
    k_B = 1.381e-23
    q_e = 1.602e-19

    def __init__(self, material=None):
        self.mat = material or MaterialParams()

    def predict_cell(self, geo, cond=None):
        """Predict electrical parameters for ONE cell element."""
        cond = cond or OperatingConditions()
        result = CellPrediction(n_cells=1)
        is_ring = geo.shape == "ring"

        Jsc_base = self.mat.Jsc_ring if is_ring else self.mat.Jsc_full
        J0 = self.mat.J0_ring if is_ring else self.mat.J0_full

        # 1. Isc
        Jsc = Jsc_base * (cond.irradiance / 1000)
        result.Isc = Jsc * geo.area_cm2

        # 2. Voc
        T_K = cond.temperature + 273.15
        Vt = self.k_B * T_K / self.q_e
        if Jsc > 0 and J0 > 0:
            result.Voc = Vt * math.log(Jsc / J0 + 1)
        result.Voc += self.mat.beta_Voc * (cond.temperature - 25.0)

        # 3. Rs (empirical baseline + power-law scaling)
        result.Rs = self._compute_Rs(geo)

        # 4. Rsh
        result.Rsh = self.mat.Rsh_ring if is_ring else self.mat.Rsh_full

        # 5. FF
        coeff = self.mat.ff_rs_coeff_ring if is_ring else self.mat.ff_rs_coeff_full
        result.FF = self._compute_FF(result.Voc, result.Isc, result.Rs, result.Rsh, Vt, coeff)

        # 6. Pmpp, Umpp, Impp
        result.Pmpp = result.Isc * result.Voc * (result.FF / 100)
        ratio = self.mat.Umpp_Voc_ring if is_ring else self.mat.Umpp_Voc_full
        result.Umpp = result.Voc * ratio
        result.Impp = result.Pmpp / result.Umpp if result.Umpp > 0 else 0

        # 7. NCell (efficiency)
        area_m2 = geo.area_cm2 * 1e-4
        if area_m2 > 0 and cond.irradiance > 0:
            result.NCell = result.Pmpp / (cond.irradiance * area_m2)

        return result

    def predict_wafer(self, geo, n_cells, cond=None):
        """Predict for n_cells identical cells wired in parallel."""
        cell = self.predict_cell(geo, cond)
        cond = cond or OperatingConditions()

        wafer = CellPrediction(n_cells=n_cells)
        wafer.Isc = cell.Isc * n_cells
        wafer.Voc = cell.Voc
        wafer.Rs = cell.Rs / n_cells
        wafer.Rsh = cell.Rsh / n_cells

        Vt = self.k_B * (cond.temperature + 273.15) / self.q_e
        is_ring = geo.shape == "ring"
        coeff = self.mat.ff_rs_coeff_ring if is_ring else self.mat.ff_rs_coeff_full
        wafer.FF = self._compute_FF(wafer.Voc, wafer.Isc, wafer.Rs, wafer.Rsh, Vt, coeff)

        wafer.Pmpp = wafer.Isc * wafer.Voc * (wafer.FF / 100)
        ratio = self.mat.Umpp_Voc_ring if is_ring else self.mat.Umpp_Voc_full
        wafer.Umpp = wafer.Voc * ratio
        wafer.Impp = wafer.Pmpp / wafer.Umpp if wafer.Umpp > 0 else 0

        total_area_m2 = geo.area_cm2 * n_cells * 1e-4
        if total_area_m2 > 0 and cond.irradiance > 0:
            wafer.NCell = wafer.Pmpp / (cond.irradiance * total_area_m2)

        return wafer

    def _compute_Rs(self, geo):
        """Rs from empirical baseline with power-law finger-count scaling."""
        is_ring = geo.shape == "ring"
        baseline = self.mat.Rs_baseline_ring if is_ring else self.mat.Rs_baseline_full
        n_ref = self.mat.Rs_ref_fingers_ring if is_ring else self.mat.Rs_ref_fingers_full

        n = max(geo.n_fingers, 1)

        # Finger count scaling (existing)
        Rs = baseline * (n_ref / n) ** self.mat.Rs_alpha

        # Finger width correction (new)
        # Wider fingers → lower resistance. The baseline was calibrated at 50µm.
        # Finger resistance scales as 1/width, but fingers are only part of total Rs.
        # Use a mild correction: 20% of Rs scales inversely with width.
        width_ref = 50.0  # µm — the reference width in our measured data
        width_ratio = width_ref / max(geo.finger_width_um, 10.0)
        Rs = Rs * (0.80 + 0.20 * width_ratio)

        # Busbar count correction (square cells only)
        if geo.shape == "square" and geo.n_busbars > 0:
            # More busbars → shorter finger path → lower finger resistance.
            # Baseline calibrated at 8 busbars (full-size data).
            # Finger resistance contribution scales as 1/n_busbars².
            bb_ref = self.mat.Rs_ref_busbars_full  # add this to MaterialParams: 8
            bb_ratio = (bb_ref / max(geo.n_busbars, 1)) ** 2
            # Finger resistance is ~30% of total Rs in H-pattern cells
            Rs = Rs * (0.70 + 0.30 * bb_ratio)

        return Rs

    def _compute_FF(self, Voc, Isc, Rs, Rsh, Vt, rs_coeff):
        """Fill factor via Green's approximation with calibrated Rs coupling."""
        if Voc <= 0 or Isc <= 0 or Vt <= 0:
            return 0.0
        voc_n = Voc / Vt
        FF0 = (voc_n - math.log(voc_n + 0.72)) / (voc_n + 1)
        rs_n = Rs * Isc / Voc
        rsh_n = Rsh * Isc / Voc if Rsh > 0 else 1000
        FF = FF0 * (1 - rs_coeff * rs_n)
        if rsh_n > 0:
            FF *= (1 - (FF0 - rs_n) / rsh_n)
        return max(25.0, min(FF * 100, 85.0))


# ── Preset geometries ───────────────────────────────────
def ring_geometry(n_fingers=RING_N_FINGERS, finger_width_um=RING_FINGER_WIDTH_UM):
    """Standard SoliTek BC ring cell from CAD."""
    return CellGeometry(
        shape="ring",
        outer_radius_mm=OUTER_RADIUS,
        inner_radius_mm=INNER_RADIUS,
        n_fingers=n_fingers,
        finger_pitch_mm=RING_FINGER_PITCH_MM,
        finger_width_um=finger_width_um,
        n_busbars=RING_N_BUSBARS,
        busbar_width_mm=RING_BUSBAR_WIDTH_MM,
    )

def fullsize_geometry():
    """Standard SoliTek ISC-ZEBRA 158×158mm cell."""
    return CellGeometry(
        shape="square",
        cell_width_mm=FULL_CELL_WIDTH,
        cell_height_mm=FULL_CELL_HEIGHT,
        n_fingers=FULL_N_FINGERS,
        finger_pitch_mm=FULL_FINGER_PITCH_MM,
        finger_width_um=FULL_FINGER_WIDTH_UM,
        n_busbars=FULL_N_BUSBARS,
        busbar_width_mm=FULL_BUSBAR_WIDTH_MM,
    )