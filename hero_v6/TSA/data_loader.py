import os
import pandas as pd
import numpy as np
import config

def load_country_pcodes(country_code):
    """
    Returns a list of unique adm1_pcodes and their names for a given country.
    """
    if not os.path.exists(config.MERGED_PARQUET):
        raise FileNotFoundError(f"Merged parquet not found at {config.MERGED_PARQUET}")
    
    df_merged = pd.read_parquet(config.MERGED_PARQUET)
    country_df = df_merged[df_merged["Country"] == country_code]
    
    # Drop duplicates to get unique adm1_pcodes
    pcodes = country_df[["adm1_pcode", "Level 1"]].dropna().drop_duplicates()
    return list(pcodes.itertuples(index=False, name=None))

def load_and_align_region(country_code, pcode):
    """
    Loads raw data sources, filters for the given region, aligns them to a monthly MS frequency,
    and returns a joined DataFrame with raw NaNs preserved for monitoring.
    """
    # 1. Load WFP prices
    wfp = pd.read_parquet(config.WFP_PARQUET)
    wfp_reg = wfp[(wfp["ISO3"] == country_code) & (wfp["adm1_pcode"] == pcode)].copy()
    wfp_reg["date"] = pd.to_datetime(wfp_reg["date"])
    wfp_monthly = wfp_reg.set_index("date").sort_index()[["wfp_price_mean", "wfp_inflation_mean"]].asfreq("MS")
    
    # 2. Load Rainfall
    rain = pd.read_parquet(config.RAIN_PARQUET)
    rain_reg = rain[rain["PCODE"] == pcode].copy()
    if not rain_reg.empty:
        rain_reg["date"] = pd.to_datetime(rain_reg["date"]).dt.to_period("M").dt.to_timestamp()
        rain_monthly = rain_reg.groupby("date")[["rain_1m", "rain_3m", "rain_anomaly_1m", "rain_anomaly_3m"]].mean().asfreq("MS")
    else:
        # Create empty DataFrame with correct columns if no data
        rain_monthly = pd.DataFrame(columns=["rain_1m", "rain_3m", "rain_anomaly_1m", "rain_anomaly_3m"])
        rain_monthly.index.name = "date"

    # 3. Load ACLED
    acled = pd.read_parquet(config.ACLED_PARQUET)
    acled_reg = acled[acled["admin1_code"] == pcode].copy()
    if not acled_reg.empty:
        acled_reg["date"] = pd.to_datetime(acled_reg["reference_period_start"]).dt.to_period("M").dt.to_timestamp()
        acled_monthly = acled_reg.groupby("date")[["events", "fatalities"]].sum().rename(
            columns={"events": "acled_events", "fatalities": "acled_fatalities"}
        ).asfreq("MS", fill_value=0)
    else:
        acled_monthly = pd.DataFrame(0, index=wfp_monthly.index, columns=["acled_events", "acled_fatalities"])
        acled_monthly.index.name = "date"

    # 4. Load IDP
    idp = pd.read_parquet(config.IDP_PARQUET)
    idp_reg = idp[idp["admin1_code"] == pcode].copy()
    if not idp_reg.empty:
        idp_reg["date"] = pd.to_datetime(idp_reg["reference_period_start"]).dt.to_period("M").dt.to_timestamp()
        # Mean population for duplicate months
        idp_monthly = idp_reg.groupby("date")[["population"]].mean().rename(
            columns={"population": "idp_population"}
        ).asfreq("MS")
    else:
        idp_monthly = pd.DataFrame(columns=["idp_population"])
        idp_monthly.index.name = "date"

    # 5. Load IPC from merged adm1 file
    df_merged = pd.read_parquet(config.MERGED_PARQUET)
    ipc_reg = df_merged[(df_merged["adm1_pcode"] == pcode) & (df_merged["Validity period"] == "current")].copy()
    
    expanded = []
    for _, row in ipc_reg.iterrows():
        m_range = pd.date_range(start=row["From"], end=row["To"], freq="MS")
        for m in m_range:
            expanded.append({"date": m, "ipc_phase_3plus_pct": row["phase_3plus_percentage"]})
            
    if expanded:
        df_ipc = pd.DataFrame(expanded).drop_duplicates(subset=["date"]).set_index("date").sort_index().asfreq("MS")
        df_ipc_filled = df_ipc.ffill().bfill()
    else:
        df_ipc_filled = pd.DataFrame(columns=["ipc_phase_3plus_pct"])
        df_ipc_filled.index.name = "date"

    # Establish full date range from the overlapping period of WFP & IPC to maintain consistency
    # WFP data usually has the widest coverage; we align with WFP index range that has IPC assessments
    start_date = max(wfp_monthly.index.min(), df_ipc_filled.index.min()) if not df_ipc_filled.empty else wfp_monthly.index.min()
    end_date = min(wfp_monthly.index.max(), df_ipc_filled.index.max()) if not df_ipc_filled.empty else wfp_monthly.index.max()
    
    if pd.isna(start_date) or pd.isna(end_date) or start_date > end_date:
        # Fallback to WFP index if join is empty
        full_range = wfp_monthly.index
    else:
        full_range = pd.date_range(start=start_date, end=end_date, freq="MS")

    # Reindex all inputs to the full uniform monthly range
    wfp_monthly = wfp_monthly.reindex(full_range)
    rain_monthly = rain_monthly.reindex(full_range)
    acled_monthly = acled_monthly.reindex(full_range).fillna(0) # ACLED missingness is filled with 0 events
    idp_monthly = idp_monthly.reindex(full_range) # Keep NaNs for monitor
    df_ipc_filled = df_ipc_filled.reindex(full_range).ffill().bfill()

    # Join datasets
    joined = wfp_monthly.join([rain_monthly, acled_monthly, idp_monthly, df_ipc_filled], how="left")
    joined.index.name = "date"
    
    return joined

def load_and_align_national(country_code):
    """
    Aggregates all provincial series of a country to a national level.
    ACLED and IDP variables are summed, while others are averaged.
    """
    regions = load_country_pcodes(country_code)
    valid_dfs = []
    
    for pcode, name in regions:
        try:
            df = load_and_align_region(country_code, pcode)
            if len(df) >= 24: # Only include regions with enough historical data
                valid_dfs.append(df)
        except Exception as e:
            print(f"Skipping region {name} ({pcode}) in national aggregation: {e}")
            
    if not valid_dfs:
        raise ValueError(f"No valid regional dataframes found for country: {country_code}")
        
    # Find common date range (datetime index intersection)
    common_idx = valid_dfs[0].index
    for df in valid_dfs[1:]:
        common_idx = common_idx.intersection(df.index)
        
    # Reindex all valid dataframes to this common timeline
    aligned_dfs = [df.reindex(common_idx) for df in valid_dfs]
    
    # Perform aggregation
    national_df = pd.DataFrame(index=common_idx)
    national_df.index.name = "date"
    
    # Sum variables
    sum_cols = ["acled_events", "acled_fatalities", "idp_population"]
    # Mean variables
    mean_cols = [
        "wfp_price_mean", "wfp_inflation_mean", 
        "rain_1m", "rain_3m", "rain_anomaly_1m", "rain_anomaly_3m", 
        "ipc_phase_3plus_pct"
    ]
    
    # Compute sum
    for col in sum_cols:
        col_series = [df[col].fillna(0.0) if col in df.columns else pd.Series(0.0, index=common_idx) for df in aligned_dfs]
        national_df[col] = sum(col_series)
        
    # Compute mean
    for col in mean_cols:
        col_dfs = [df[col] for df in aligned_dfs if col in df.columns]
        if col_dfs:
            national_df[col] = pd.concat(col_dfs, axis=1).mean(axis=1)
        else:
            national_df[col] = np.nan
            
    return national_df
