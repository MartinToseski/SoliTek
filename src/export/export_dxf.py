import math
import ezdxf
from shapely.geometry import Point
from shapely.ops import unary_union

from src.geometry.circular import create_fingers, create_fingers_n
from src.config.config import RING_SPACING, EDGE_MARGIN, FINGER_THICKNESS, FINGER_SPACING, FINGER_TO_RING, PAD_LENGTH, \
    PAD_WIDTH, PAD_GAP
from src.geometry.bridge import create_cut_sector, get_cut_endpoints, create_exact_bridge, split_bridge_segments, \
    create_middle_curve_bridge_exact
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

def draw_contact_pad_from_geom(msp, merged, doc,
                               reference_override=None,
                               skip_theta=None,
                               skip_half_angle=0.0,
                               ring_cx=None,
                               ring_cy=None,
                               skip_radial_walls=False,  # NEW
                               max_radius=None):  # NEW
    """
    skip_radial_walls : when True (and ring_cx/cy are given), any segment whose
                        tangent direction is within ~25° of the radial direction
                        (dot-product > 0.9) is skipped.  This removes the short
                        perpendicular side-wall segments of the middle bridge
                        without touching arcs or the top outer edge.
    max_radius        : when given (and ring_cx/cy are given), pads for points
                        further than this radius from the ring centre are skipped.
                        Used to restrict the separate middle-curve draw to its
                        inner arc only (r ≤ r_inner_f), preventing duplicate pads
                        on the outer top edge that merged_for_pads already covers.
    """

    PAD_ALONG = PAD_LENGTH  # length along the finger path
    PAD_ACROSS = PAD_WIDTH  # width across the finger path
    half_along = PAD_ALONG / 2  # 0.125 mm
    half_across = PAD_ACROSS / 2  # 0.0075 mm
    spacing = PAD_LENGTH + PAD_GAP

    all_geoms = list(getattr(merged, "geoms", [merged]))
    primary = max(all_geoms, key=lambda g: g.area)

    for geom in [primary]:

        layer_name = "CONTACT_PAD"

        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=7)

        line = geom.exterior
        length = line.length
        d = 0

        while d < length:

            p = line.interpolate(d)
            p_next = line.interpolate(min(d + 0.01, length))

            x, y = p.x, p.y
            x2, y2 = p_next.x, p_next.y

            # ---- angular skip ------------------------------------------
            if (skip_theta is not None
                    and ring_cx is not None
                    and skip_half_angle > 0):
                pt_angle = (math.degrees(
                    math.atan2(y - ring_cy, x - ring_cx)) + 360) % 360
                skip_center = (skip_theta + 360) % 360
                diff = (pt_angle - skip_center + 180) % 360 - 180
                if abs(diff) <= skip_half_angle:
                    d += spacing
                    continue

            # ---- radius ceiling (inner-arc-only draws) -----------------
            if max_radius is not None and ring_cx is not None:
                if math.hypot(x - ring_cx, y - ring_cy) > max_radius + 1e-6:
                    d += spacing
                    continue

            dx = x2 - x
            dy = y2 - y
            l = math.hypot(dx, dy)

            if l == 0:
                d += spacing
                continue

            ux = dx / l
            uy = dy / l

            # ---- radial wall filter ------------------------------------
            # Segments connecting the outer-ring level to the bridge top
            # (pA_outer→outer_A and outer_B→pB_outer) run along the radial
            # direction.  Detect them by their high dot-product with the
            # outward radius vector and skip them.
            if skip_radial_walls and ring_cx is not None:
                r_pt = math.hypot(x - ring_cx, y - ring_cy)
                if r_pt > 0:
                    rdot = abs(ux * (x - ring_cx) / r_pt
                               + uy * (y - ring_cy) / r_pt)
                    if rdot > 0.9:
                        d += spacing
                        continue

            nx = -uy
            ny = ux

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

            px = x + nx * half_across
            py = y + ny * half_across

            rot = math.atan2(dy, dx)
            cos_r = math.cos(rot)
            sin_r = math.sin(rot)

            rect = []
            for dx_, dy_ in [(-half_along, -half_across),
                             (half_along, -half_across),
                             (half_along, half_across),
                             (-half_along, half_across),
                             (-half_along, -half_across)]:
                rx = px + dx_ * cos_r - dy_ * sin_r
                ry = py + dx_ * sin_r + dy_ * cos_r
                rect.append((rx, ry))
            msp.add_lwpolyline(rect, dxfattribs={"layer": layer_name})
            d += spacing


# ================= FINGERS =================

def draw_fingers(doc, msp, cx, cy, r_inner, r_outer,
                 theta, cut_angle, finger_radii):
    for idx, r in enumerate(finger_radii):

        # ============================================================
        # Finger layer — alternating polarity for interdigitated contacts
        # For 4 fingers: 0=BASE, 1=EMITTER, 2=EMITTER, 3=BASE (original)
        # For n fingers: alternate BASE/EMITTER (interdigitated)
        # ============================================================

        if len(finger_radii) == 4:
            # Original behavior for standard 4-finger design
            if idx == 0 or idx == 3:
                layer_name = "FINGER_BASE"
            else:
                layer_name = "FINGER_EMITTER"
        else:
            # Interdigitated pattern for any finger count
            layer_name = "FINGER_BASE" if idx % 2 == 0 else "FINGER_EMITTER"

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
            #
            # Some BASE rings occasionally remain as fragmented MultiPolygons
            # after unary_union(...).buffer(0). In those cases the exterior of
            # the largest polygon incorrectly exposes the INNER cut arc:
            #
            #   outer arc
            #       +
            #   bridge
            #       +
            #   inner cut arc   <-- duplicate pad source
            #
            # producing a second near-parallel pad row offset inward by:
            #
            #   FINGER_THICKNESS
            #
            # The same tiny heal already used successfully for EMITTER fingers
            # fixes this topology issue here as well.
            #
            # IMPORTANT:
            # - draw_merged_geometry still uses the original `merged`
            # - only the pad sampling geometry is healed
            # - no geometry changes occur in the exported DXF itself
            #
            # This forces the ring + bridge into one clean polygon whose
            # exterior contains only:
            #
            #   outer arc -> bridge -> outer arc
            #
            # eliminating the stray inner-arc duplicate pads.
            MERGE_TOL = 1e-4

            merged_for_pads = (
                merged
                .buffer(MERGE_TOL)
                .buffer(-MERGE_TOL)
            )

            draw_contact_pad_from_geom(
                msp,
                merged_for_pads,
                doc
            )

        else:

            # ============================================================
            # EMITTER fingers
            # ============================================================

            # Geometry healing buffer.
            #
            # Ensures bridge/ring unions become one clean polygon so the
            # exterior path follows:
            #
            #   arc -> bridge walls -> middle bridge -> bridge walls -> arc
            #
            # without duplicate rows caused by fragmented MultiPolygons.
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
                # Main merged exterior pads
                # --------------------------------------------------------

                draw_contact_pad_from_geom(
                    msp,
                    merged_for_pads,
                    doc,

                    skip_radial_walls=True,

                    ring_cx=cx,
                    ring_cy=cy,
                )

                # --------------------------------------------------------
                # Inner curved bridge pads
                # --------------------------------------------------------

                if middle_curve is not None:
                    bridge_ref = (
                        cx
                        + (r_outer_f + 6 * FINGER_THICKNESS)
                        * math.cos(math.radians(theta)),

                        cy
                        + (r_outer_f + 6 * FINGER_THICKNESS)
                        * math.sin(math.radians(theta)),
                    )

                    draw_contact_pad_from_geom(
                        msp,
                        middle_curve,
                        doc,

                        reference_override=bridge_ref,

                        skip_radial_walls=True,

                        max_radius=r_inner_f,

                        ring_cx=cx,
                        ring_cy=cy,
                    )

            # ============================================================
            # OUTER emitter
            # ============================================================

            else:

                # --------------------------------------------------------
                # Outer emitter:
                # arc -> split bridge -> gap -> split bridge -> arc
                # --------------------------------------------------------
                #
                # merged_for_pads preserves the actual bridge chord
                # geometry so pads correctly follow the straight split
                # bridge sections instead of tracing a pure circular arc.
                #
                # The middle bridge opening begins at:
                #
                #   pA_outer / pB_outer
                #
                # not at:
                #
                #   p1_outer / p2_outer
                #
                # split_bridge_segments(..., ratio=0.15) places:
                #
                #   pA_outer / pB_outer
                #
                # at:
                #
                #   theta ± 0.35 * local_angle_2
                #
                # Therefore:
                #
                #   skip_half = 0.35 * local_angle_2
                #
                # removes ONLY the actual middle bridge opening while
                # allowing pads to continue much closer toward the
                # bridge section boundaries.
                #
                # This removes the visible dead angular margin between:
                #
                #   split bridge pads
                #       and
                #   middle bridge opening
                #
                # without affecting any other geometry or pad logic.
                local_angle_2 = cut_angle * 0.67

                # Exact middle bridge opening half-span.
                skip_half = 0.35 * local_angle_2

                draw_contact_pad_from_geom(
                    msp,
                    merged_for_pads,
                    doc,

                    skip_theta=theta,
                    skip_half_angle=skip_half,

                    ring_cx=cx,
                    ring_cy=cy,

                    skip_radial_walls=True,
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
               actual_margin_x, actual_margin_y, filename, n_fingers=None):
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

    nx = len(set(r["center"][0] for r in rings))
    ny = len(set(r["center"][1] for r in rings))

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

    if n_fingers is not None:
        finger_radii = create_fingers_n(inner_diameter, outer_diameter, n_fingers)
    else:
        finger_radii = create_fingers(inner_diameter, outer_diameter)

    for i, ring_data in enumerate(rings):
        cx, cy = ring_data["center"]

        r_outer = outer_diameter / 2
        r_inner = inner_diameter / 2

        wafer_center_x = (minx + maxx) / 2
        wafer_center_y = (miny + maxy) / 2

        gx, gy = get_group_center(
            cx,
            cy,
            pitch,
            wafer_center_x,
            wafer_center_y,
            nx,
            ny,
        )

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


def export_square_cell_dxf(rects, filename, busbars_rects, cells_rects, contacts_rects, dicing_rects, insulation_rects,
                           ablation_rects, wafer):
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()

    doc.header["$LUNITS"] = 2
    doc.header["$LUPREC"] = 4

    doc.layers.add("FINGERS", color=1)
    doc.layers.add("BUSBARS", color=3)
    doc.layers.add("CELLS", color=5)
    doc.layers.add("WAFER", color=1)
    doc.layers.add("CONTACT_PADS", color=7)
    doc.layers.add("DICING", color=30)
    doc.layers.add("INSULATION", color=2)
    doc.layers.add("ABLATION", color=4)

    for r in rects:
        coords = list(r["geometry"].exterior.coords)
        msp.add_lwpolyline(coords, close=True, dxfattribs={"layer": "FINGERS"})

    for geom in busbars_rects:
        for g in getattr(geom, "geoms", [geom]):
            msp.add_lwpolyline(list(g.exterior.coords), close=True, dxfattribs={"layer": "BUSBARS"})

    for cell in cells_rects:
        msp.add_lwpolyline(list(cell.exterior.coords), close=True, dxfattribs={"layer": "CELLS"})

    for c in contacts_rects:
        msp.add_lwpolyline(list(c.exterior.coords), close=True, dxfattribs={"layer": "CONTACT_PADS"})

    for start, end in dicing_rects:
        msp.add_line(start, end, dxfattribs={"layer": "DICING"})

    for rect in insulation_rects:
        msp.add_lwpolyline(list(rect.exterior.coords), close=True, dxfattribs={"layer": "INSULATION"})

    for rect in ablation_rects:
        for g in getattr(rect, "geoms", [rect]):
            msp.add_lwpolyline(list(g.exterior.coords), close=True, dxfattribs={"layer": "ABLATION"})

    msp.add_lwpolyline(list(wafer.exterior.coords), close=True, dxfattribs={"layer": "WAFER"})

    doc.saveas(f"data/{filename}.dxf")
    print("DXF file saved!")