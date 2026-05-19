from flask import Flask, request, jsonify, send_file
from evaluation.optimizer import DesignOptimizer
import dataclasses
from src.core.layout import generate_ring_layout
from src.export.export_dxf import export_dxf, export_square_cell_dxf
from shapely.geometry import box
import os

from config.config import *

import src.geometry.square.ablation as ablation
import src.geometry.square.busbars as busbars
import src.geometry.square.cells as cells
import src.geometry.square.contact_pads as contact_pads
import src.geometry.square.dicing as dicing
import src.geometry.square.fingers as fingers
import src.geometry.square.insulation as insulation
import src.geometry.square.wafer as wafer
from src.geometry.square.generate import generate_square_cell

app = Flask(__name__, static_folder="static")

@app.route("/")
def index():
    return app.send_static_file("design_optimizer.html")

@app.route("/search", methods=["POST"])
def search():
    params = request.get_json()
    search_params = {
        "shape":                    params.get("shape", "ring"),
        "outer_radius_mm":          params.get("outer_diameter", OUTER_DIAMETER) / 2,
        "inner_radius_mm":          params.get("inner_diameter", INNER_DIAMETER) / 2,
        "priority":                 params.get("priority", "efficiency"),
        "temperature":              params.get("temperature", 25.0),
        "irradiance":               params.get("irradiance", 1000.0),
        "n_results":                params.get("n_results", 5),
        # square params passed through
        "sq_finger_amount":         params.get("sq_finger_amount",         sq_finger_amount),
        "sq_finger_width":          params.get("sq_finger_width",          sq_finger_width),
        "sq_finger_distance":       params.get("sq_finger_distance",       sq_finger_distance),
        "sq_finger_block_distance": params.get("sq_finger_block_distance", sq_finger_block_distance),
        "sq_contact_w":             params.get("sq_contact_w",             sq_contact_w),
        "sq_contact_h":             params.get("sq_contact_h",             sq_contact_h),
        "sq_contact_gap_x":         params.get("sq_contact_gap_x",         sq_contact_gap_x),
        "sq_contact_gap_y":         params.get("sq_contact_gap_y",         sq_contact_gap_y),
    }
    opt = DesignOptimizer()
    results = opt.search(**search_params)
    return jsonify([dataclasses.asdict(r) for r in results])

@app.route("/generate-dxf", methods=["POST"])
def generate_dxf():
    data   = request.get_json()
    shape  = data.get("shape", "ring")
    n_fingers = data.get("n_fingers")

    os.makedirs("data", exist_ok=True)

    if shape == "square":
        wafer_size = data.get("wafer_size", WAFER_SIZE)
        wafer_box = box(0, 0, wafer_size, wafer_size)

        finger_width    = data.get("sq_finger_width",          sq_finger_width)
        finger_distance = data.get("sq_finger_distance",        sq_finger_distance)
        blk_distance    = data.get("sq_finger_block_distance",  sq_finger_block_distance)
        contact_w       = data.get("sq_contact_w",              sq_contact_w)
        contact_h       = data.get("sq_contact_h",              sq_contact_h)
        contact_gap_x   = data.get("sq_contact_gap_x",          sq_contact_gap_x)
        contact_gap_y   = data.get("sq_contact_gap_y",          sq_contact_gap_y)
        finger_amt      = data.get("sq_finger_amount",          sq_finger_amount)

        rects, busbars_rects, cells_rects, contacts_rects, \
        dicing_rects, insulation_rects, ablation_rects, wafer_rect = generate_square_cell(
            fingers.RowGridParams(sq_finger_block_line_amount, sq_finger_block_line_distance),
            fingers.FingerBlockRowParams(sq_finger_block_amount_line, blk_distance),
            fingers.FingerBlockParams(finger_amt, finger_width, sq_finger_height, finger_distance),
            busbars.BusbarParams(
                sq_top_busbar_top_d, sq_bottom_busbar_bottom_d,
                sq_top_busbar_left_d, sq_top_busbar_right_d,
                sq_bottom_busbar_left_d, sq_bottom_busbar_right_d,
                sq_top_busbar_protrusion_w, sq_top_busbar_protrusion_h,
            ),
            cells.CellParams(sq_cell_w_margin, sq_cell_h_margin),
            contact_pads.ContactParams(
                contact_w, contact_h,
                contact_gap_x, contact_gap_y,
                sq_contact_margin_x, sq_contact_margin_y,
            ),
            dicing.DicingParams(sq_dicing_protrusion_x, sq_dicing_protrusion_y),
            insulation.InsulationParams(
                sq_insulation_w, sq_insulation_h, sq_insulation_protrusion,
                sq_insulation_h_margin, sq_insulation_gap, sq_insulation_inset,
            ),
            ablation.AblationParams(
                sq_ablation_w, sq_ablation_h, sq_ablation_gap,
                sq_ablation_x_margin, sq_ablation_wafer_margin,
            ),
            wafer.WaferParams(sq_wafer_w_margin, sq_wafer_h_margin, sq_wafer_corner_w),
        )

        export_square_cell_dxf(
            rects=rects,
            filename="square",
            busbars_rects=busbars_rects,
            cells_rects=cells_rects,
            contacts_rects=contacts_rects,
            dicing_rects=dicing_rects,
            insulation_rects=insulation_rects,
            ablation_rects=ablation_rects,
            wafer=wafer_rect,
        )

        dxf_path = os.path.abspath("data/square.dxf")
        if not os.path.exists(dxf_path):
            return jsonify({"error": f"File not written. CWD: {os.getcwd()}"}), 500
        return send_file(dxf_path, as_attachment=True, download_name=f"square_{finger_amt}f.dxf")

    # --- ring (unchanged) ---
    wafer_size       = data.get("wafer_size",       WAFER_SIZE)
    inner_diameter   = data.get("inner_diameter",   INNER_DIAMETER)
    outer_diameter   = data.get("outer_diameter",   OUTER_DIAMETER)
    ring_spacing     = data.get("ring_spacing",     RING_SPACING)
    edge_margin      = data.get("edge_margin",      EDGE_MARGIN)
    fingers_per_ring = data.get("fingers_per_ring", FINGERS_PER_RING)
    finger_thickness = data.get("finger_thickness", FINGER_THICKNESS)
    finger_spacing   = data.get("finger_spacing",   FINGER_SPACING)
    finger_to_ring   = data.get("finger_to_ring",   FINGER_TO_RING)
    pad_width        = data.get("pad_width",         PAD_WIDTH)
    pad_length       = data.get("pad_length",        PAD_LENGTH)
    pad_gap          = data.get("pad_gap",           PAD_GAP)
    wafer_box = box(0, 0, wafer_size, wafer_size)
    rings, margin_x, margin_y = generate_ring_layout(
        wafer_box, inner_diameter, outer_diameter, ring_spacing, edge_margin
    )
    export_dxf(
        wafer_box, rings,
        inner_diameter, outer_diameter,
        margin_x, margin_y,
        "ring",
        n_fingers=n_fingers,
        fingers_per_ring=fingers_per_ring,
        finger_thickness=finger_thickness,
        finger_spacing=finger_spacing,
        finger_to_ring=finger_to_ring,
        pad_width=pad_width,
        pad_length=pad_length,
        pad_gap=pad_gap,
    )
    dxf_path = os.path.abspath("data/ring.dxf")
    if not os.path.exists(dxf_path):
        return jsonify({"error": f"File not written. CWD: {os.getcwd()}"}), 500
    return send_file(dxf_path, as_attachment=True, download_name=f"ring_{n_fingers}f.dxf")

if __name__ == "__main__":
    app.run(debug=True)