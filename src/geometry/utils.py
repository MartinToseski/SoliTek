import math


def get_group_center(cx, cy, pitch):
    ix = int(cx // pitch)
    iy = int(cy // pitch)
    gx = (ix // 2) * 2 * pitch + pitch
    gy = (iy // 2) * 2 * pitch + pitch
    return gx, gy


def get_theta(cx, cy, gx, gy):
    theta = math.degrees(math.atan2(gy - cy, gx - cx))
    return (theta + 360) % 360


def get_cut_angles(theta, angle_deg):
    start = theta + angle_deg / 2
    end = theta - angle_deg / 2
    return start % 360, end % 360