import math
import ezdxf
import geom
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


# ================= CONTACT PAD =================

CONTACT_PAD_LAYER_COUNTER = 0


def draw_contact_pad_from_geom(msp, merged, doc,
                                reference_override=None,
                                skip_theta=None,
                                skip_half_angle=0.0,
                                ring_cx=None,
                                ring_cy=None):
    """
    reference_override : (x, y) used instead of polygon centroid for the
                         inward-normal check.  Needed for the middle-curve
                         bridge whose centroid sits on the wrong side of the
                         bulging inner arc.
    skip_theta / skip_half_angle / ring_cx / ring_cy :
                         skip pads whose angle from ring_cx,ring_cy falls
                         within (skip_theta ± skip_half_angle) degrees.
    """
    global CONTACT_PAD_LAYER_COUNTER

    size    = FINGER_THICKNESS
    half    = size / 2
    spacing = size * 4

    # Safety: use only the largest polygon when unary_union fragments into a
    # MultiPolygon so we never draw duplicate pad rows.
    all_geoms = list(getattr(merged, "geoms", [merged]))
    primary   = max(all_geoms, key=lambda g: g.area)

    for geom in [primary]:

        layer_name = f"CONTACT_PAD_{CONTACT_PAD_LAYER_COUNTER}"
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=7)
        CONTACT_PAD_LAYER_COUNTER += 1

        line   = geom.exterior
        length = line.length
        d      = 0

        while d < length:

            p      = line.interpolate(d)
            p_next = line.interpolate(min(d + 0.01, length))

            x,  y  = p.x,      p.y
            x2, y2 = p_next.x, p_next.y

            # ---- angular skip -----------------------------------------------
            if (skip_theta is not None
                    and ring_cx is not None
                    and skip_half_angle > 0):
                pt_angle    = (math.degrees(
                    math.atan2(y - ring_cy, x - ring_cx)) + 360) % 360
                skip_center = (skip_theta + 360) % 360
                diff = (pt_angle - skip_center + 180) % 360 - 180  # in (−180, 180]
                if abs(diff) <= skip_half_angle:
                    d += spacing
                    continue
            # -----------------------------------------------------------------

            dx = x2 - x
            dy = y2 - y
            l  = math.hypot(dx, dy)

            if l == 0:
                d += spacing
                continue

            ux = dx / l
            uy = dy / l

            nx = -uy
            ny =  ux

            # Reference point for the inside/outside test
            if reference_override is not None:
                ref_x, ref_y = reference_override
            else:
                ref_x = geom.centroid.x
                ref_y = geom.centroid.y

            vx = ref_x - x
            vy = ref_y - y

            if nx * vx + ny * vy < 0:
                nx = -nx
                ny = -ny

            px = x + nx * (FINGER_THICKNESS / 2)
            py = y + ny * (FINGER_THICKNESS / 2)

            rot   = math.atan2(dy, dx)
            cos_r = math.cos(rot)
            sin_r = math.sin(rot)

            square = []
            for dx_, dy_ in [(-half, -half), ( half, -half),
                              ( half,  half), (-half,  half), (-half, -half)]:
                rx = px + dx_ * cos_r - dy_ * sin_r
                ry = py + dx_ * sin_r + dy_ * cos_r
                square.append((rx, ry))

            msp.add_lwpolyline(square, dxfattribs={"layer": layer_name})
            d += spacing


# ================= FINGERS =================

def draw_fingers(doc, msp, cx, cy, r_inner, r_outer,
                 theta, cut_angle, finger_radii):

    for idx, r in enumerate(finger_radii):

        # ============================================================
        # Finger layer
        # ============================================================

        if idx == 0 or idx == 3:
            layer_name = "FINGER_BASE"
        else:
            layer_name = "FINGER_EMITTER"

        r_outer_f = r
        r_inner_f = r - FINGER_THICKNESS

        if r_inner_f <= r_inner:
            continue

        # ============================================================
        # Local cut angle
        # ============================================================

        local_angle = cut_angle

        if idx == len(finger_radii) - 2:
            local_angle *= 0.67
        elif idx == len(finger_radii) - 3:
            local_angle *= 0.93

        # ============================================================
        # Ring geometry
        # ============================================================

        cut_sector = create_cut_sector(
            cx,
            cy,
            r_outer * 1.5,
            theta,
            local_angle
        )

        outer_poly = Point(cx, cy).buffer(
            r_outer_f,
            resolution=128
        )

        inner_poly = Point(cx, cy).buffer(
            r_inner_f,
            resolution=128
        )

        ring_poly = outer_poly.difference(inner_poly)

        if idx == len(finger_radii) - 1:
            finger_geom = ring_poly
        else:
            finger_geom = ring_poly.difference(cut_sector)

        geom_list = [finger_geom]

        middle_curve = None

        # ============================================================
        # Bridges
        # ============================================================

        if idx < len(finger_radii) - 1:

            p1_outer, p2_outer = get_cut_endpoints(
                cx, cy,
                r_outer_f,
                theta,
                local_angle
            )

            p1_inner, p2_inner = get_cut_endpoints(
                cx, cy,
                r_inner_f,
                theta,
                local_angle
            )

            # --------------------------------------------------------
            # Middle curved bridge
            # --------------------------------------------------------

            if idx == len(finger_radii) - 2:

                (
                    left_bridge,
                    right_bridge,
                    pA_outer,
                    pB_outer,
                    pA_inner,
                    pB_inner
                ) = split_bridge_segments(
                    p1_outer,
                    p2_outer,
                    p1_inner,
                    p2_inner,
                    ratio=0.15
                )

                middle_curve = create_middle_curve_bridge_exact(
                    cx,
                    cy,
                    pA_outer,
                    pB_outer,
                    pA_inner,
                    pB_inner
                )

                geom_list.extend([
                    left_bridge,
                    middle_curve,
                    right_bridge
                ])

            # --------------------------------------------------------
            # Normal bridge
            # --------------------------------------------------------

            else:

                bridge = create_exact_bridge(
                    p1_outer,
                    p2_outer,
                    p1_inner,
                    p2_inner
                )

                geom_list.append(bridge)

        # ============================================================
        # Merge geometry
        # ============================================================

        merged = unary_union(geom_list).buffer(0)

        # ============================================================
        # Draw geometry
        # ============================================================

        draw_merged_geometry(
            msp,
            merged,
            layer_name
        )

        # ================================================================
        # Contact pads
        # ================================================================

        if layer_name == "FINGER_BASE":

            # ============================================================
            # BASE fingers
            # ============================================================

            # Keep original behaviour unchanged.
            # These fingers already generate correct contact-pad geometry.
            draw_contact_pad_from_geom(msp, merged, doc)

        else:

            # ============================================================
            # EMITTER fingers
            # ============================================================

            # Tiny healing buffer.
            #
            # The analytical bridge endpoints do not land exactly on the
            # polygonized ring vertices produced by Point(...).buffer(...).
            # That can fragment the union into tiny MultiPolygon pieces,
            # producing duplicated near-parallel contact-pad rows.
            #
            # The tiny outward/inward buffer forces all touching pieces to
            # merge into one clean polygon while preserving geometry.
            MERGE_TOL = 1e-4

            merged_for_pads = (
                merged
                .buffer(MERGE_TOL)
                .buffer(-MERGE_TOL)
            )

            # ============================================================
            # INNER emitter
            # ============================================================

            if idx == len(finger_radii) - 2:

                # --------------------------------------------------------
                # Main pad path
                # --------------------------------------------------------
                #
                # This now correctly follows:
                #
                #   outer arc
                #       ->
                #   split bridge
                #       ->
                #   middle bridge
                #       ->
                #   split bridge
                #       ->
                #   outer arc
                #
                # while avoiding the duplicated emitter rows.
                draw_contact_pad_from_geom(
                    msp,
                    merged_for_pads,
                    doc
                )

                # --------------------------------------------------------
                # Middle curved bridge pads
                # --------------------------------------------------------
                #
                # No separate middle-curve pad drawing.
                #
                # merged_for_pads already correctly traces the bridge
                # geometry itself. Removing the explicit middle_curve
                # drawing prevents pads from appearing on the short
                # side walls of the bridge section.

            # ============================================================
            # OUTER emitter
            # ============================================================

            else:

                # --------------------------------------------------------
                # Bridge opening skip zone
                # --------------------------------------------------------
                #
                # The outer emitter arc naturally continues through the
                # angular opening occupied by the INNER emitter bridge
                # complex:
                #
                #   left_bridge
                #       +
                #   middle_curve
                #       +
                #   right_bridge
                #
                # That causes pads to cross directly through the bridge
                # geometry instead of stopping at the bridge walls.
                #
                # We therefore apply an angular skip region centered at
                # theta whose width exactly matches the inner-emitter
                # bridge opening.
                #
                # This makes the pads:
                #
                #   stop before first wall
                #       ->
                #   skip the bridge opening
                #       ->
                #   continue after second wall
                #
                # without altering any other geometry.
                local_angle_2 = cut_angle * 0.67

                # Half-angle from theta to each bridge wall.
                skip_half = local_angle_2 / 2

                draw_contact_pad_from_geom(
                    msp,
                    merged_for_pads,
                    doc,

                    skip_theta=theta,
                    skip_half_angle=skip_half,

                    ring_cx=cx,
                    ring_cy=cy,
                )


# ================= DIMENSIONS =================

def draw_dimensions(msp, cx, cy, r_outer, r_inner, minx, miny, maxy, OFFSET, finger_radii, rings):
    ring_left = cx - r_outer
    ring_bottom = cy - r_outer

    msp.add_linear_dim((minx - OFFSET - 30, cy), (minx, cy), (ring_left, cy),
                       dimstyle="EZ_DIM", dxfattribs={"layer": "DIMS"}).render()

    msp.add_linear_dim((cx, miny - OFFSET - 40), (cx, miny), (cx, ring_bottom),
                       angle=90, dimstyle="EZ_DIM", dxfattribs={"layer": "DIMS"}).render()

    msp.add_diameter_dim(center=(cx, cy), mpoint=(cx, cy - r_outer),
                         dimstyle="EZ_DIM", dxfattribs={"layer": "DIMS"}).render()

    msp.add_diameter_dim(center=(cx, cy), mpoint=(cx - r_inner, cy),
                         dimstyle="EZ_DIM", dxfattribs={"layer": "DIMS"}).render()

    if len(finger_radii) >= 1:
        first_r = finger_radii[0]

        msp.add_linear_dim((cx, maxy + OFFSET + 10),
                           (cx + r_outer, cy),
                           (cx + first_r, cy),
                           dimstyle="EZ_DIM",
                           dxfattribs={"layer": "DIMS"}).render()

    if len(finger_radii) >= 2:
        r1 = finger_radii[0]
        r2 = finger_radii[1]
        inner_r1 = r1 - FINGER_THICKNESS

        msp.add_linear_dim((cx, maxy + OFFSET),
                           (cx + inner_r1, cy),
                           (cx + r2, cy),
                           dimstyle="EZ_DIM",
                           dxfattribs={"layer": "DIMS"}).render()

    if len(rings) > 1:
        cx2, cy2 = rings[1]["center"]

        msp.add_linear_dim((cx, maxy + OFFSET + 20),
                           (cx + r_outer, cy),
                           (cx2 - r_outer, cy),
                           dimstyle="EZ_DIM",
                           dxfattribs={"layer": "DIMS"}).render()

    if len(finger_radii) >= 1:
        r = finger_radii[0]

        msp.add_linear_dim((cx, maxy + OFFSET + 40),
                           (cx + r, cy),
                           (cx + r - FINGER_THICKNESS, cy),
                           dimstyle="EZ_DIM",
                           dxfattribs={"layer": "DIMS"}).render()


# ================= CONSTANTS =================

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
    doc.layers.add("CONTACT_PAD", color=7)

    OFFSET = 25
    cut_angle = 30
    pitch = outer_diameter + RING_SPACING

    minx, miny, maxx, maxy = boundary.bounds

    # WAFER
    msp.add_lwpolyline([(minx, miny), (maxx, miny), (maxx, maxy),
                        (minx, maxy), (minx, miny)],
                       dxfattribs={"layer": "WAFER"})

    msp.add_linear_dim(base=(minx, miny - OFFSET),
                       p1=(minx, miny),
                       p2=(maxx, miny),
                       dimstyle="EZ_DIM",
                       dxfattribs={"layer": "DIMS"}).render()

    finger_radii = create_fingers(inner_diameter, outer_diameter)

    for i, ring_data in enumerate(rings):
        cx, cy = ring_data["center"]

        r_outer = outer_diameter / 2
        r_inner = inner_diameter / 2

        gx, gy = get_group_center(cx, cy, pitch)
        theta = get_theta(cx, cy, gx, gy)

        draw_rings(msp, cx, cy, r_outer, r_inner, theta, cut_angle)
        draw_fingers(doc, msp, cx, cy, r_inner, r_outer, theta, cut_angle, finger_radii)

        if i == 0:
            draw_dimensions(msp, cx, cy, r_outer, r_inner,
                            minx, miny, maxy, OFFSET,
                            finger_radii, rings)

    draw_constants_panel(msp, minx, maxx, maxy,
                         outer_diameter, inner_diameter,
                         actual_margin_x, actual_margin_y)

    doc.saveas(f"data/{filename}.dxf")
    print("DXF file saved!")