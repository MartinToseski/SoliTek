"""
Prediction-specific configuration.

Imports geometry from the existing src.config.config (used by CAD generation)
and adds electrical/metallization constants needed for performance prediction.
"""

from src.config.config import OUTER_DIAMETER, INNER_DIAMETER, WAFER_SIZE, WAFER_SIZE_LARGE, RING_SPACING, EDGE_MARGIN


OUTER_RADIUS = OUTER_DIAMETER / 2    # mm
INNER_RADIUS = INNER_DIAMETER / 2    # mm
RINGS_PER_ROW = {
    WAFER_SIZE: 4,
    WAFER_SIZE_LARGE: 5,
}
RING_WIDTH = OUTER_RADIUS - INNER_RADIUS  # 2.10 mm


def get_n_rings(wafer_size=None):
    """Return total ring count for a given wafer size."""
    ws = wafer_size or WAFER_SIZE
    per_row = RINGS_PER_ROW.get(ws, 4)
    return per_row * per_row


# ── Ring metallization (from CAD + SoliTek rep) ─────────
RING_N_FINGERS = 4
RING_FINGER_WIDTH_UM = 50       # µm
RING_FINGER_PITCH_MM = 0.55     # mm (fine contact line spacing)
RING_N_BUSBARS = 2
RING_BUSBAR_WIDTH_MM = 2.0      # mm

# ── Full-size cell (158×158 mm, ISC-ZEBRA-new) ──────────
FULL_CELL_WIDTH = 158.75            # mm
FULL_CELL_HEIGHT = 158.75           # mm
FULL_N_FINGERS = 288
FULL_FINGER_WIDTH_UM = 50        # µm
FULL_FINGER_PITCH_MM = 0.55      # mm
FULL_N_BUSBARS = 8
FULL_BUSBAR_WIDTH_MM = 1.5       # mm
FULL_EDGE_EXCLUSION_MM = 0.255   # mm