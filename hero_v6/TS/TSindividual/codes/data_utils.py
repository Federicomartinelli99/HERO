import os
import pandas as pd
import geopandas as gpd
from . import config

def load_afg_main_data():
    """
    Loads the main wide imputed dataset and filters it for Afghanistan (AFG).
    Ensures that the date column is parsed and sorted chronologically per province.
    """
    if not os.path.exists(config.DATASET_PATH):
        raise FileNotFoundError(f"Main dataset not found at: {config.DATASET_PATH}")
        
    df = pd.read_parquet(config.DATASET_PATH)
    
    # Filter for Afghanistan (AFG)
    afg_df = df[df["Country"] == config.COUNTRY].copy()
    
    # Convert date to datetime
    afg_df["reference_period_end"] = pd.to_datetime(afg_df["reference_period_end"])
    
    # Sort chronologically by Level 1 (Province) and date
    afg_df = afg_df.sort_values(by=["Level 1", "reference_period_end"])
    
    return afg_df

def load_afg_wfp_data():
    """
    Loads raw WFP price data and filters it for Afghanistan.
    """
    if not os.path.exists(config.WFP_PATH):
        raise FileNotFoundError(f"WFP raw data not found at: {config.WFP_PATH}")
        
    df = pd.read_parquet(config.WFP_PATH)
    
    # Filter for Afghanistan
    afg_wfp = df[df["ISO3"] == config.COUNTRY].copy()
    
    # Parse date and sort
    afg_wfp["date"] = pd.to_datetime(afg_wfp["date"])
    afg_wfp = afg_wfp.sort_values(by=["mkt_name", "date"])
    
    return afg_wfp

def load_afg_boundaries():
    """
    Loads the GeoJSON boundaries for Afghanistan Admin 1.
    """
    if not os.path.exists(config.GEOJSON_PATH):
        raise FileNotFoundError(f"GeoJSON boundaries not found at: {config.GEOJSON_PATH}")
        
    gdf = gpd.read_file(config.GEOJSON_PATH)
    return gdf
