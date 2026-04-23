import math
from shapely.geometry import Polygon

from src.config.config import FINGER_THICKNESS


def create_cut_sector(cx, cy, radius, theta, angle_deg):
    angle_start = math.radians(theta - angle_deg / 2)
    angle_end = math.radians(theta + angle_deg / 2)

    points = [(cx, cy)]
    steps = 60

    for i in range(steps + 1):
        a = angle_start + (angle_end - angle_start) * i / steps
        x = cx + radius * math.cos(a)
        y = cy + radius * math.sin(a)
        points.append((x, y))

    points.append((cx, cy))
    return Polygon(points).buffer(0)


def get_cut_endpoints(cx, cy, radius, theta, angle_deg):
    a1 = math.radians(theta - angle_deg / 2)
    a2 = math.radians(theta + angle_deg / 2)

    p1 = (cx + radius * math.cos(a1), cy + radius * math.sin(a1))
    p2 = (cx + radius * math.cos(a2), cy + radius * math.sin(a2))

    return p1, p2


def create_exact_bridge(p1_outer, p2_outer, p1_inner, p2_inner):
    return Polygon([p1_outer, p2_outer, p2_inner, p1_inner])


def split_bridge_segments(p1_outer, p2_outer, p1_inner, p2_inner, ratio=0.15):
    def lerp(p1, p2, t):
        return (p1[0] + (p2[0] - p1[0]) * t,
                p1[1] + (p2[1] - p1[1]) * t)

    pA_outer = lerp(p1_outer, p2_outer, ratio)
    pB_outer = lerp(p1_outer, p2_outer, 1 - ratio)

    pA_inner = lerp(p1_inner, p2_inner, ratio)
    pB_inner = lerp(p1_inner, p2_inner, 1 - ratio)

    left_bridge = Polygon([p1_outer, pA_outer, pA_inner, p1_inner])
    right_bridge = Polygon([pB_outer, p2_outer, p2_inner, pB_inner])

    return left_bridge, right_bridge, pA_outer, pB_outer, pA_inner, pB_inner


def create_middle_curve_bridge_exact(cx, cy, pA_outer, pB_outer, pA_inner, pB_inner, thickness_mult=12, steps=40):
    def angle_of(p):
        return math.atan2(p[1] - cy, p[0] - cx)

    r_inner = math.hypot(pA_inner[0] - cx, pA_inner[1] - cy)

    a_start = angle_of(pA_inner)
    a_end = angle_of(pB_inner)

    if a_end < a_start:
        a_end += 2 * math.pi

    inner_path = []
    for i in range(steps + 1):
        t = i / steps
        a = a_start + (a_end - a_start) * t
        inner_path.append((cx + r_inner * math.cos(a),
                           cy + r_inner * math.sin(a)))

    dx = pB_outer[0] - pA_outer[0]
    dy = pB_outer[1] - pA_outer[1]
    length = math.hypot(dx, dy)

    if length == 0:
        return None

    ux = dx / length
    uy = dy / length

    nx = uy
    ny = -ux

    offset = thickness_mult * FINGER_THICKNESS

    outer_A = (pA_outer[0] + nx * offset, pA_outer[1] + ny * offset)
    outer_B = (pB_outer[0] + nx * offset, pB_outer[1] + ny * offset)

    coords = []
    coords.extend(inner_path)
    coords.append(pB_inner)
    coords.append(pB_outer)
    coords.append(outer_B)
    coords.append(outer_A)
    coords.append(pA_outer)
    coords.append(pA_inner)

    return Polygon(coords)