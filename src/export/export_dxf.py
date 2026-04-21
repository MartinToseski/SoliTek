import ezdxf
import math
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from src.geometry.circular import create_fingers
from src.config.config import (
    RING_SPACING, EDGE_MARGIN,
    FINGER_THICKNESS, FINGER_SPACING, FINGER_TO_RING
)

# ================= HELPERS =================

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


# ================= MAIN =================

def export_dxf(boundary, rings, inner_diameter, outer_diameter,
               actual_margin_x, actual_margin_y, filename):

    doc = ezdxf.new()
    doc.units = ezdxf.units.MM

    doc.header["$LTSCALE"] = 1.0
    doc.header["$PSLTSCALE"] = 1

    msp = doc.modelspace()

    # ===== DIM STYLE =====
    dimstyle = doc.dimstyles.new("EZ_DIM") if "EZ_DIM" not in doc.dimstyles else doc.dimstyles.get("EZ_DIM")
    dimstyle.dxf.dimdec = 4
    dimstyle.dxf.dimzin = 0

    # ===== LINETYPE =====
    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[0.5, 0.25, -0.25])

    # ===== LAYERS =====
    doc.layers.add("WAFER", color=1, linetype="DASHED")
    doc.layers.add("RINGS", color=1, linetype="DASHED")
    doc.layers.add("FINGERS", color=7)
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

    # ===== WAFER WIDTH =====
    msp.add_linear_dim(
        base=(minx, miny - OFFSET),
        p1=(minx, miny),
        p2=(maxx, miny),
        dimstyle="EZ_DIM",
        dxfattribs={"layer": "DIMS"}
    ).render()

    finger_radii = create_fingers(inner_diameter, outer_diameter)

    # ================= LOOP =================
    for i, ring_data in enumerate(rings):
        cx, cy = ring_data["center"]

        r_outer = outer_diameter / 2
        r_inner = inner_diameter / 2

        gx, gy = get_group_center(cx, cy, pitch)
        theta = get_theta(cx, cy, gx, gy)

        # ===== OUTER RING =====
        start_angle, end_angle = get_cut_angles(theta, cut_angle)

        msp.add_arc((cx, cy), r_outer, start_angle, end_angle,
                    dxfattribs={"layer": "RINGS", "linetype": "DASHED"})

        p1, p2 = get_cut_endpoints(cx, cy, r_outer, theta, cut_angle)
        msp.add_line(p1, p2, dxfattribs={"layer": "RINGS", "linetype": "DASHED"})

        # ===== INNER RING =====
        msp.add_circle((cx, cy), r_inner, dxfattribs={"layer": "RINGS"})

        # ===== FINGERS =====
        for idx, r in enumerate(finger_radii):
            r_outer_f = r
            r_inner_f = r - FINGER_THICKNESS

            if r_inner_f <= r_inner:
                continue

            local_angle = cut_angle

            if idx == len(finger_radii) - 2:
                local_angle *= 0.75
            elif idx == len(finger_radii) - 3:
                local_angle *= 0.95

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

                bridge = create_exact_bridge(p1_outer, p2_outer, p1_inner, p2_inner)
                geom_list.append(bridge)

            merged = unary_union(geom_list).buffer(0)

            for geom in getattr(merged, "geoms", [merged]):
                coords = list(geom.exterior.coords)

                msp.add_lwpolyline(coords, dxfattribs={"layer": "FINGERS"})

                hatch = msp.add_hatch(color=7)
                hatch.paths.add_polyline_path(coords, is_closed=True)

                for interior in geom.interiors:
                    hatch.paths.add_polyline_path(list(interior.coords), is_closed=True)

        # ===== DIMENSIONS =====
        if i == 0:
            ring_left = cx - r_outer
            ring_bottom = cy - r_outer

            msp.add_linear_dim((minx - OFFSET - 30, cy), (minx, cy), (ring_left, cy),
                               dimstyle="EZ_DIM", dxfattribs={"layer": "DIMS"}).render()

            msp.add_linear_dim((cx, miny - OFFSET - 40), (cx, miny), (cx, ring_bottom),
                               angle=90, dimstyle="EZ_DIM", dxfattribs={"layer": "DIMS"}).render()

            # ✅ FIXED DIAMETER CALLS
            msp.add_diameter_dim(center=(cx, cy), mpoint=(cx, cy - r_outer),
                                 dimstyle="EZ_DIM", dxfattribs={"layer": "DIMS"}).render()

            msp.add_diameter_dim(center=(cx, cy), mpoint=(cx - r_inner, cy),
                                 dimstyle="EZ_DIM", dxfattribs={"layer": "DIMS"}).render()

        # ===== CONSTANTS PANEL =====
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

    doc.saveas(f"data/{filename}.dxf")
    print("DXF file saved!")