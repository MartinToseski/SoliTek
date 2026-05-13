import math


def get_group_center(
        cx,
        cy,
        pitch,
        wafer_center_x,
        wafer_center_y,
        nx,
        ny):

    # Convert to centered lattice coordinates
    lx = (cx - wafer_center_x) / pitch
    ly = (cy - wafer_center_y) / pitch

    # ------------------------------------------------------------
    # EVEN grids:
    #
    # true symmetry center lies BETWEEN rings
    # ------------------------------------------------------------

    if nx % 2 == 0:
        gx_idx = (math.floor((lx + nx / 2) / 2.0) * 2.0) - (nx / 2) + 1
    else:
        gx_idx = round((lx - 0.5) / 2.0) * 2.0 + 0.5

    if ny % 2 == 0:
        gy_idx = (math.floor((ly + ny / 2) / 2.0) * 2.0) - (ny / 2) + 1
    else:
        gy_idx = round((ly - 0.5) / 2.0) * 2.0 + 0.5

    gx = wafer_center_x + gx_idx * pitch
    gy = wafer_center_y + gy_idx * pitch

    return gx, gy


def get_theta(cx, cy, gx, gy):
    theta = math.degrees(math.atan2(gy - cy, gx - cx))
    return (theta + 360) % 360


def get_cut_angles(theta, angle_deg):
    start = theta + angle_deg / 2
    end = theta - angle_deg / 2
    return start % 360, end % 360