import ezdxf
from shapely.geometry import Point
from shapely.ops import unary_union

from src.geometry.circular import create_fingers
from src.config.config import RING_SPACING, EDGE_MARGIN, FINGER_THICKNESS, FINGER_SPACING, FINGER_TO_RING
from src.geometry.bridge import create_cut_sector, get_cut_endpoints, create_exact_bridge, split_bridge_segments, create_middle_curve_bridge_exact
from src.geometry.utils import get_group_center, get_theta, get_cut_angles


# ================= DRAW HELPERS =================

def draw_merged_geometry(msp, merged, layer_name):
    for geom in getattr(merged, "geoms", [merged]):
        coords = list(geom.exterior.coords)

        msp.add_lwpolyline(coords, dxfattribs={"layer": layer_name})

        hatch = msp.add_hatch(color=7)
        hatch.dxf.layer = layer_name
        hatch.paths.add_polyline_path(coords, is_closed=True)

        for interior in geom.interiors:
            hatch.paths.add_polyline_path(list(interior.coords), is_closed=True)


def draw_rings(msp, cx, cy, r_outer, r_inner, theta, cut_angle):
    start_angle, end_angle = get_cut_angles(theta, cut_angle)

    msp.add_arc((cx, cy), r_outer, start_angle, end_angle,
                dxfattribs={"layer": "RINGS", "linetype": "DASHED"})

    p1, p2 = get_cut_endpoints(cx, cy, r_outer, theta, cut_angle)
    msp.add_line(p1, p2, dxfattribs={"layer": "RINGS", "linetype": "DASHED"})

    msp.add_circle((cx, cy), r_inner, dxfattribs={"layer": "RINGS"})


def draw_fingers(msp, cx, cy, r_inner, r_outer, theta, cut_angle, finger_radii):
    for idx, r in enumerate(finger_radii):
        if idx == 0 or idx == 3:
            layer_name = "FINGER_BASE"  # outer 2
        else:
            layer_name = "FINGER_EMITTER"  # middle 2

        r_outer_f = r
        r_inner_f = r - FINGER_THICKNESS

        if r_inner_f <= r_inner:
            continue

        local_angle = cut_angle

        if idx == len(finger_radii) - 2:
            local_angle *= 0.67
        elif idx == len(finger_radii) - 3:
            local_angle *= 0.93

        cut_sector = create_cut_sector(cx, cy, r_outer * 1.5, theta, local_angle)

        outer_poly = Point(cx, cy).buffer(r_outer_f, resolution=128)
        inner_poly = Point(cx, cy).buffer(r_inner_f, resolution=128)

        ring_poly = outer_poly.difference(inner_poly)

        if idx == len(finger_radii) - 1:
            finger_geom = ring_poly
        else:
            finger_geom = ring_poly.difference(cut_sector)

        geom_list = [finger_geom]

        if idx < len(finger_radii) - 1:
            p1_outer, p2_outer = get_cut_endpoints(cx, cy, r_outer_f, theta, local_angle)
            p1_inner, p2_inner = get_cut_endpoints(cx, cy, r_inner_f, theta, local_angle)

            if idx == len(finger_radii) - 2:
                left_bridge, right_bridge, pA_outer, pB_outer, pA_inner, pB_inner = split_bridge_segments(
                    p1_outer, p2_outer,
                    p1_inner, p2_inner,
                    ratio=0.15
                )

                middle_curve = create_middle_curve_bridge_exact(
                    cx, cy,
                    pA_outer, pB_outer,
                    pA_inner, pB_inner
                )

                geom_list.extend([left_bridge, middle_curve, right_bridge])
            else:
                bridge = create_exact_bridge(p1_outer, p2_outer, p1_inner, p2_inner)
                geom_list.append(bridge)

        merged = unary_union(geom_list).buffer(0)
        draw_merged_geometry(msp, merged, layer_name)


def draw_dimensions(msp, cx, cy, r_outer, r_inner, minx, miny, maxy, OFFSET, finger_radii, rings):
    ring_left = cx - r_outer
    ring_bottom = cy - r_outer

    msp.add_linear_dim(
        (minx - OFFSET - 30, cy),
        (minx, cy),
        (ring_left, cy),
        dimstyle="EZ_DIM",
        dxfattribs={"layer": "DIMS"}
    ).render()

    msp.add_linear_dim(
        (cx, miny - OFFSET - 40),
        (cx, miny),
        (cx, ring_bottom),
        angle=90,
        dimstyle="EZ_DIM",
        dxfattribs={"layer": "DIMS"}
    ).render()

    msp.add_diameter_dim(
        center=(cx, cy),
        mpoint=(cx, cy - r_outer),
        dimstyle="EZ_DIM",
        dxfattribs={"layer": "DIMS"}
    ).render()

    msp.add_diameter_dim(
        center=(cx, cy),
        mpoint=(cx - r_inner, cy),
        dimstyle="EZ_DIM",
        dxfattribs={"layer": "DIMS"}
    ).render()

    if len(finger_radii) >= 1:
        first_r = finger_radii[0]

        msp.add_linear_dim(
            base=(cx, maxy + OFFSET + 10),
            p1=(cx + r_outer, cy),
            p2=(cx + first_r, cy),
            dimstyle="EZ_DIM",
            dxfattribs={"layer": "DIMS"}
        ).render()

    if len(finger_radii) >= 2:
        r1 = finger_radii[0]
        r2 = finger_radii[1]
        inner_r1 = r1 - FINGER_THICKNESS

        msp.add_linear_dim(
            base=(cx, maxy + OFFSET),
            p1=(cx + inner_r1, cy),
            p2=(cx + r2, cy),
            dimstyle="EZ_DIM",
            dxfattribs={"layer": "DIMS"}
        ).render()

    if len(rings) > 1:
        cx2, cy2 = rings[1]["center"]

        msp.add_linear_dim(
            base=(cx, maxy + OFFSET + 20),
            p1=(cx + r_outer, cy),
            p2=(cx2 - r_outer, cy),
            dimstyle="EZ_DIM",
            dxfattribs={"layer": "DIMS"}
        ).render()

    if len(finger_radii) >= 1:
        r = finger_radii[0]

        msp.add_linear_dim(
            base=(cx, maxy + OFFSET + 40),
            p1=(cx + r, cy),
            p2=(cx + r - FINGER_THICKNESS, cy),
            dimstyle="EZ_DIM",
            dxfattribs={"layer": "DIMS"}
        ).render()


def draw_constants_panel(msp, minx, maxx, maxy, outer_diameter, inner_diameter, actual_margin_x, actual_margin_y):
    text_x = maxx + 60
    text_y = maxy

    constants = [
        f"WAFER_SIZE = {(maxx - minx):.4f}",
        f"OUTER_DIAMETER = {outer_diameter:.4f}",
        f"INNER_DIAMETER = {inner_diameter:.4f}",
        f"RING_SPACING = {RING_SPACING:.4f}",
        f"MIN_EDGE_MARGIN = {EDGE_MARGIN:.4f}",
        f"ACTUAL_MARGIN_X = {actual_margin_x:.4f}",
        f"ACTUAL_MARGIN_Y = {actual_margin_y:.4f}",
        f"FINGER_THICKNESS = {FINGER_THICKNESS:.4f}",
        f"FINGER_SPACING = {FINGER_SPACING:.4f}",
        f"FINGER_TO_RING = {FINGER_TO_RING:.4f}",
    ]

    for j, line in enumerate(constants):
        txt = msp.add_text(line, dxfattribs={"height": 3, "layer": "DIMS", "color": 3})
        txt.dxf.insert = (text_x, text_y - j * 5)


# ================= MAIN =================

def export_dxf(boundary, rings, inner_diameter, outer_diameter,
               actual_margin_x, actual_margin_y, filename):

    doc = ezdxf.new()
    doc.units = ezdxf.units.MM

    doc.header["$LTSCALE"] = 1.0
    doc.header["$PSLTSCALE"] = 1

    msp = doc.modelspace()

    dimstyle = doc.dimstyles.new("EZ_DIM") if "EZ_DIM" not in doc.dimstyles else doc.dimstyles.get("EZ_DIM")
    dimstyle.dxf.dimdec = 4
    dimstyle.dxf.dimzin = 0

    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[0.5, 0.25, -0.25])

    doc.layers.add("WAFER", color=1, linetype="DASHED")
    doc.layers.add("RINGS", color=1, linetype="DASHED")
    doc.layers.add("FINGER_BASE", color=7)
    doc.layers.add("FINGER_EMITTER", color=7)
    doc.layers.add("DIMS", color=3)

    OFFSET = 25
    cut_angle = 30
    pitch = outer_diameter + RING_SPACING

    minx, miny, maxx, maxy = boundary.bounds

    # ===== WAFER =====
    msp.add_lwpolyline(
        [(minx, miny), (maxx, miny), (maxx, maxy),
         (minx, maxy), (minx, miny)],
        dxfattribs={"layer": "WAFER"}
    )

    msp.add_linear_dim(
        base=(minx, miny - OFFSET),
        p1=(minx, miny),
        p2=(maxx, miny),
        dimstyle="EZ_DIM",
        dxfattribs={"layer": "DIMS"}
    ).render()

    finger_radii = create_fingers(inner_diameter, outer_diameter)

    for i, ring_data in enumerate(rings):
        cx, cy = ring_data["center"]

        r_outer = outer_diameter / 2
        r_inner = inner_diameter / 2

        gx, gy = get_group_center(cx, cy, pitch)
        theta = get_theta(cx, cy, gx, gy)

        draw_rings(msp, cx, cy, r_outer, r_inner, theta, cut_angle)
        draw_fingers(msp, cx, cy, r_inner, r_outer, theta, cut_angle, finger_radii)

        if i == 0:
            draw_dimensions(msp, cx, cy, r_outer, r_inner,
                            minx, miny, maxy, OFFSET,
                            finger_radii, rings)

    draw_constants_panel(msp, minx, maxx, maxy,
                         outer_diameter, inner_diameter,
                         actual_margin_x, actual_margin_y)

    doc.saveas(f"data/{filename}.dxf")
    print("DXF file saved!")