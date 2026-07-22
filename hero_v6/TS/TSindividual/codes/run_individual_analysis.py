import os
import sys

# Ensure codes directory is in path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from . import config
from . import data_utils
from . import time_series_exploration as tse
from . import frontier_techniques as ft
from . import national_analysis as na

def main():
    print("=========================================================")
    print("   HERO Individual Time Series Analysis - Benchmark AFG  ")
    print("=========================================================")
    
    # 1. Load data
    try:
        print("\nLoading datasets...")
        afg_df = data_utils.load_afg_main_data()
        wfp_df = data_utils.load_afg_wfp_data()
        boundaries_gdf = data_utils.load_afg_boundaries()
        print("Data loaded successfully.")
    except Exception as e:
        print(f"Error loading data: {e}")
        return
        
    results_dir = config.OUTPUT_DIR
    print(f"Results will be saved in: {results_dir}")
    
    # 2. Run Phase 3: Time Series Exploration
    print("\n--- Running Phase 3: Time Series Exploration ---")
    
    # Task 3.1: Stationarity & STL
    tse.run_stationarity_and_stl(afg_df, results_dir)
    
    # Task 3.2: Cross Correlation
    tse.run_cross_correlation(afg_df, results_dir)
    
    # Task 3.3: Matrix Profile
    tse.run_matrix_profile(afg_df, results_dir)
    
    # Task 3.4: Shapelets
    tse.run_shapelets(afg_df, results_dir)
    
    # Task 3.5: Feature extraction (tsfresh)
    catch22_df = tse.run_tsfresh_feature_extraction(afg_df, results_dir)
    
    # Task 3.6: Dynamic clustering (DTW & NCD)
    tse.run_dynamic_clustering(afg_df, results_dir, boundaries_gdf)
    
    # 3. Run Phase 6: Frontier Techniques
    print("\n--- Running Phase 6: Frontier Techniques ---")
    
    # Task 6.2: Spatial Autocorrelation (Moran's I & LISA)
    ft.run_spatial_autocorrelation(afg_df, results_dir, boundaries_gdf)
    
    # Task 6.4: Spatial Outliers (DBSCAN)
    ft.run_spatial_outliers(afg_df, results_dir, boundaries_gdf, catch22_df)
    
    # Task 7.0: National level analysis
    na.run_national_analysis(afg_df)
    
    print("\n=========================================================")
    print("   Analysis Completed Successfully for Afghanistan Benchmark! ")
    print("=========================================================")

if __name__ == "__main__":
    main()
