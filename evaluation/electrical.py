import math
from src.config.config import (
    OUTER_DIAMETER, INNER_DIAMETER, WAFER_SIZE, 
    RING_SPACING, EDGE_MARGIN
)
from shapely.geometry import box
from src.core.layout import generate_ring_layout

def calculate_dynamic_wafer():
    # 1. Get current layout from CAD logic
    wafer_geom = box(0, 0, WAFER_SIZE, WAFER_SIZE)
    rings, _, _ = generate_ring_layout(
        wafer_geom, INNER_DIAMETER, OUTER_DIAMETER, RING_SPACING, EDGE_MARGIN
    )
    num_cells = len(rings)
    
    # 2. Geometric Calculations
    r_out = OUTER_DIAMETER / 2
    r_in = INNER_DIAMETER / 2
    area_per_cell_cm2 = (math.pi * (r_out**2 - r_in**2)) / 100
    total_area_cm2 = area_per_cell_cm2 * num_cells
    
    # 3. Scaling Constants (Derived from BC Excel data)
    # Jsc = Total Isc / Total Area from excel (2.27A / 37.32cm2)
    JSC = 0.0609  # Amps per cm2
    FF = 0.6305   # Fill Factor (efficiency of the IV curve)
    
    # 4. Dynamic Voc Calculation 
    # Voc scales with the log of current. If area increases 5x, Voc increases slightly.
    # Baseline: 0.6843V at current area.
    baseline_voc = 0.6843
    if area_per_cell_cm2 > 0:
        # Physics approximation: Voc_new = Voc_old + 0.026 * ln(Area_ratio)
        # If area increases 5x, Voc increases by ~0.04V
        area_ratio = area_per_cell_cm2 / 2.3328 # 2.33 is  current ring area
        dynamic_voc = baseline_voc + (0.02585 * math.log(max(area_ratio, 0.001)))
    else:
        dynamic_voc = 0

    # 5. Result Calculations
    total_isc = total_area_cm2 * JSC
    total_pmpp = total_isc * dynamic_voc * FF
    
    # Voltage and Current at Max Power Point
    # Typically Umpp is ~80% of Voc in BC cells
    dynamic_umpp = dynamic_voc * 0.796 
    total_impp = total_pmpp / dynamic_umpp
    
    # Summary Output
    print(f"--- DYNAMIC ANALYSIS: {num_cells} CELLS ---")
    print(f"Area per Cell:     {area_per_cell_cm2:.4f} cm2")
    print(f"Total Wafer Area:  {total_area_cm2:.4f} cm2")
    print("-" * 35)
    print(f"Wafer Isc:         {total_isc:.4f} A")
    print(f"Wafer Voc (Avg):   {dynamic_voc:.4f} V")
    print(f"Wafer Pmpp:        {total_pmpp:.4f} W")
    print(f"Wafer Impp:        {total_impp:.4f} A")
    print(f"Wafer Umpp:        {dynamic_umpp:.4f} V")
    print(f"Efficiency:        {(total_pmpp/(total_area_cm2*0.1))*100:.2f} %")

if __name__ == "__main__":
    calculate_dynamic_wafer()