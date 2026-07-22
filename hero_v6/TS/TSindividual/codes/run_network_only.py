import os
import sys

# Ensure codes directory is in path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from . import config
from . import data_utils
from . import frontier_techniques as ft

def main():
    print("=========================================================")
    print("   Starting WFP Market Network Analysis (AFG & Global)    ")
    print("=========================================================")
    
    try:
        print("\nLoading data...")
        wfp_df = data_utils.load_afg_wfp_data()
        boundaries_gdf = data_utils.load_afg_boundaries()
        print("Data loaded successfully.")
    except Exception as e:
        print(f"Error loading data: {e}")
        return
        
    results_dir = config.OUTPUT_DIR
    print(f"Results will be saved in: {results_dir}")
    
    # Task 6.1: WFP Market Network Analysis
    ft.run_wfp_network_analysis(wfp_df, results_dir, boundaries_gdf)
    
    print("\n=========================================================")
    print("   Market Network Analysis Completed!                   ")
    print("=========================================================")

if __name__ == "__main__":
    main()
