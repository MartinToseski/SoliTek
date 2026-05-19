from shapely.geometry import Point

def create_ring(center, inner_d, outer_d):
    outer = Point(center).buffer(outer_d / 2.0, resolution=128)
    inner = Point(center).buffer(inner_d / 2.0, resolution=128)
    return outer.difference(inner), outer

def create_fingers(inner_d, outer_d, finger_to_ring, finger_thickness, finger_spacing):
    finger_radii = []
    r_outer = outer_d / 2 - finger_to_ring
    r_inner_limit = inner_d / 2 + finger_to_ring
    step = finger_thickness + finger_spacing
    current_r = r_outer
    while True:
        r_inner = current_r - finger_thickness
        if r_inner <= r_inner_limit:
            break
        finger_radii.append(current_r)
        current_r -= step
    return finger_radii

def create_fingers_n(inner_diameter, outer_diameter, n_fingers, finger_to_ring, finger_thickness):
    r_outer = outer_diameter / 2
    r_inner = inner_diameter / 2
    r_start = r_outer - finger_to_ring
    r_end   = r_inner + finger_thickness
    if n_fingers <= 0 or r_start <= r_end:
        return []
    if n_fingers == 1:
        return [r_start]
    step = (r_start - r_end) / (n_fingers - 1)
    return [r_start - i * step for i in range(n_fingers)]