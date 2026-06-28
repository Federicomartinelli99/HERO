import os
import json
import numpy as np
import pandas as pd
from pathlib import Path

# Paths
UI_DIR = Path(__file__).resolve().parent
DATA_OUT_DIR = UI_DIR / "data"
COUNTRIES_OUT_DIR = DATA_OUT_DIR / "countries"
DATA_OUT_DIR.mkdir(parents=True, exist_ok=True)
COUNTRIES_OUT_DIR.mkdir(parents=True, exist_ok=True)

HERO_V6_DIR = UI_DIR.parent
ADM1_PARQUET = HERO_V6_DIR / "data" / "merged" / "merged_adm1_wide.parquet"
ADM2_PARQUET = HERO_V6_DIR / "data" / "merged" / "merged_adm2_wide.parquet"
WFP_PCODE_PARQUET = HERO_V6_DIR / "data" / "raw" / "wfp_with_pcodes.parquet"

print(f"Reading ADM1 from: {ADM1_PARQUET}")
df_adm1 = pd.read_parquet(ADM1_PARQUET)
print(f"Reading ADM2 from: {ADM2_PARQUET}")
df_adm2 = pd.read_parquet(ADM2_PARQUET)

print(f"Reading WFP Market Coordinates from: {WFP_PCODE_PARQUET}")
df_wfp_mkt = pd.read_parquet(WFP_PCODE_PARQUET)

# Standardize columns and fill NaNs
for df in [df_adm1, df_adm2]:
    df['Country'] = df['Country'].astype(str).str.strip().str.upper()
    df['adm1_pcode'] = df['adm1_pcode'].fillna("").astype(str).str.strip()
    df['adm2_pcode'] = df['adm2_pcode'].fillna("").astype(str).str.strip()
    df['Level 1'] = df['Level 1'].fillna("Unknown Admin1").astype(str).str.strip()
    df['Area'] = df['Area'].fillna("Unknown Admin2").astype(str).str.strip()
    df['From'] = df['From'].astype(str)
    df['To'] = df['To'].astype(str)
    df['Validity period'] = df['Validity period'].fillna("unknown").astype(str)

    # Add Year-Quarter based on 'From' date
    df['dt_from'] = pd.to_datetime(df['From'], errors='coerce')
    df['year_quarter'] = df['dt_from'].dt.to_period('Q').astype(str)

# Extract unique markets coordinates per country
print("Extracting market coordinates...")
df_mkt = df_wfp_mkt[['ISO3', 'mkt_name', 'lat', 'lon', 'adm1_pcode', 'adm2_pcode']].dropna(subset=['lat', 'lon']).drop_duplicates(subset=['ISO3', 'mkt_name'])
markets_by_country = {}
for iso3, g in df_mkt.groupby('ISO3'):
    markets_by_country[iso3.upper()] = [
        {
            "name": str(row['mkt_name']),
            "lat": float(row['lat']),
            "lon": float(row['lon']),
            "adm1_pcode": str(row['adm1_pcode']),
            "adm2_pcode": str(row['adm2_pcode'])
        }
        for _, row in g.iterrows()
    ]

# Global country name dictionary
country_names = {}
# Try to extract the location full name for each country code
for df in [df_adm1, df_adm2]:
    for idx, row in df.iterrows():
        c_code = row['Country']
        c_name = row.get('location_name_full', c_code)
        if pd.notna(c_name) and str(c_name).strip() != "" and len(str(c_name)) > 3:
            country_names[c_code] = str(c_name).split(',')[0].strip() # Keep short name

# Fallback for country codes
default_names = {
    "AFG": "Afghanistan", "AGO": "Angola", "BDI": "Burundi", "BEN": "Benin", "BFA": "Burkina Faso",
    "BGD": "Bangladesh", "CAF": "Central African Republic", "CIV": "Côte d'Ivoire", "CMR": "Cameroon",
    "COD": "Democratic Republic of the Congo", "CPV": "Cabo Verde", "DJI": "Djibouti", "DOM": "Dominican Republic",
    "ECU": "Ecuador", "ETH": "Ethiopia", "GHA": "Ghana", "GIN": "Guinea", "GMB": "Gambia", "GNB": "Guinea-Bissau",
    "GTM": "Guatemala", "HND": "Honduras", "HTI": "Haiti", "KEN": "Kenya", "LBN": "Lebanon", "LBR": "Liberia",
    "LSO": "Lesotho", "MDG": "Madagascar", "MLI": "Mali", "MOZ": "Mozambique", "MRT": "Mauritania",
    "MWI": "Malawi", "NAM": "Namibia", "NER": "Niger", "NGA": "Nigeria", "PAK": "Pakistan", "PSE": "Palestine",
    "SDN": "Sudan", "SEN": "Senegal", "SLE": "Sierra Leone", "SLV": "El Salvador", "SOM": "Somalia",
    "SSD": "South Sudan", "SWZ": "Eswatini", "TCD": "Chad", "TGO": "Togo", "TLS": "Timor-Leste",
    "TZA": "Tanzania", "UGA": "Uganda", "YEM": "Yemen", "ZAF": "South Africa", "ZMB": "Zambia", "ZWE": "Zimbabwe"
}
for code, name in default_names.items():
    if code not in country_names:
        country_names[code] = name

# Define completeness helper
def compute_completeness(df, country_col, period_col, level_name):
    # Binary flags for availability
    df['has_ipc'] = df['phase_3plus_percentage'].notnull().astype(int)
    df['has_acled'] = df['acled_total_events'].notnull().astype(int)
    df['has_idp'] = df['idp_population'].notnull().astype(int)
    df['has_rainfall'] = df['rain_1m'].notnull().astype(int)
    df['has_wfp'] = df['wfp_price'].notnull().astype(int)
    df['has_ndvi'] = df['ndvi_vim'].notnull().astype(int) if 'ndvi_vim' in df.columns else 0
    df['has_gdelt'] = df['gdelt_verbal_coop_events'].notnull().astype(int) if 'gdelt_verbal_coop_events' in df.columns else 0
    df['has_geojson'] = ((df['adm1_pcode'] != "") | (df['adm2_pcode'] != "")).astype(int)

    # Overall score (simple average of keys)
    indicators = ['has_ipc', 'has_acled', 'has_idp', 'has_rainfall', 'has_wfp', 'has_ndvi', 'has_gdelt']
    df['avail_score'] = df[indicators].mean(axis=1) * 100

    # Group by Country and Year-Quarter to get averages
    grouped = df.groupby([country_col, period_col])
    
    # We want completeness to be the percentage of rows having the data (mean of binary indicators * 100)
    completeness = grouped[indicators].mean() * 100
    # But avail_score is already scaled between 0 and 100, so we just take its average directly!
    completeness['avail_score'] = grouped['avail_score'].mean()
    
    # Reset index and return
    return completeness.reset_index()

print("Calculating completeness matrices...")
comp_adm1 = compute_completeness(df_adm1, 'Country', 'year_quarter', 'adm1')
comp_adm2 = compute_completeness(df_adm2, 'Country', 'year_quarter', 'adm2')

# Get full time ranges and country list
all_quarters = sorted(list(set(df_adm1['year_quarter'].unique()).union(df_adm2['year_quarter'].unique())))
all_countries = sorted(list(set(df_adm1['Country'].unique()).union(df_adm2['Country'].unique())))

print(f"Total Quarters: {len(all_quarters)} ({all_quarters[0]} to {all_quarters[-1]})")
print(f"Total Countries: {len(all_countries)}")

# Pre-build heatmaps structure
heatmaps = {
    "adm1": {},
    "adm2": {}
}

metrics_map = {
    "overall": "avail_score",
    "ipc": "has_ipc",
    "acled": "has_acled",
    "idp": "has_idp",
    "rainfall": "has_rainfall",
    "wfp": "has_wfp",
    "ndvi": "has_ndvi",
    "gdelt": "has_gdelt"
}

for lvl, df_comp in [("adm1", comp_adm1), ("adm2", comp_adm2)]:
    for metric_key, col in metrics_map.items():
        # Create a pivot table country x quarter
        pivot = df_comp.pivot(index="Country", columns="year_quarter", values=col)
        # Reindex to ensure all countries and quarters exist
        pivot = pivot.reindex(index=all_countries, columns=all_quarters)
        
        # Replace NaN with None for JSON encoding
        z_data = pivot.where(pd.notna(pivot), None).values.tolist()
        
        # Save this
        heatmaps[lvl][metric_key] = {
            "x": all_quarters,
            "y": [country_names.get(c, c) for c in all_countries],
            "y_codes": all_countries,
            "z": z_data
        }

# Compute value heatmaps (actual parameters over time)
print("Calculating value matrices...")
value_metrics = {
    "ipc": ("phase_3plus_percentage", "mean"),
    "acled": ("acled_total_events", "sum"),
    "idp": ("idp_population", "sum"),
    "rainfall": ("rain_1m", "mean"),
    "wfp": ("wfp_price", "mean"),
    "ndvi": ("ndvi_vim", "mean"),
    "gdelt": ("gdelt_material_conflict_events", "sum")
}
value_heatmaps = {}
for m_key, (col, agg_fn) in value_metrics.items():
    grouped = df_adm1.groupby(['Country', 'year_quarter'])[col].agg(agg_fn).reset_index()
    pivot = grouped.pivot(index="Country", columns="year_quarter", values=col)
    pivot = pivot.reindex(index=all_countries, columns=all_quarters)
    z_data = pivot.where(pd.notna(pivot), None).values.tolist()
    
    value_heatmaps[m_key] = {
        "x": all_quarters,
        "y": [country_names.get(c, c) for c in all_countries],
        "y_codes": all_countries,
        "z": z_data
    }

# Compute overall country completeness averages for rankings
country_averages = {}
for code in all_countries:
    c_df1 = df_adm1[df_adm1['Country'] == code]
    c_df2 = df_adm2[df_adm2['Country'] == code]
    
    score1 = c_df1['avail_score'].mean() if not c_df1.empty else 0.0
    score2 = c_df2['avail_score'].mean() if not c_df2.empty else 0.0
    
    overall_score = (score1 + score2) / 2 if (not c_df1.empty and not c_df2.empty) else (score1 if not c_df1.empty else score2)
    
    country_averages[code] = {
        "code": code,
        "name": country_names.get(code, code),
        "score_adm1": float(score1) if pd.notna(score1) else 0.0,
        "score_adm2": float(score2) if pd.notna(score2) else 0.0,
        "score_overall": float(overall_score) if pd.notna(overall_score) else 0.0
    }

# Helper to serialize numpy types
def clean_val(v):
    if isinstance(v, (np.floating, float)):
        return float(v) if not (np.isnan(v) or np.isinf(v)) else None
    elif isinstance(v, (np.integer, int)):
        return int(v)
    elif isinstance(v, dict):
        return {k: clean_val(x) for k, x in v.items()}
    elif isinstance(v, list):
        return [clean_val(x) for x in v]
    elif pd.isna(v):
        return None
    else:
        return v

def clean_dict(d):
    return {k: clean_val(v) for k, v in d.items()}

# Compute global summary metrics
global_stats = {
    "total_rows_adm1": int(len(df_adm1)),
    "total_rows_adm2": int(len(df_adm2)),
    "countries_count": len(all_countries),
    "avg_completeness_ipc": float(df_adm1['has_ipc'].mean() * 100),
    "avg_completeness_acled": float(df_adm1['has_acled'].mean() * 100),
    "avg_completeness_idp": float(df_adm1['has_idp'].mean() * 100),
    "avg_completeness_rainfall": float(df_adm1['has_rainfall'].mean() * 100),
    "avg_completeness_wfp": float(df_adm1['has_wfp'].mean() * 100),
    "avg_completeness_ndvi": float(df_adm1['has_ndvi'].mean() * 100) if 'has_ndvi' in df_adm1.columns else 0.0,
    "avg_completeness_gdelt": float(df_adm1['has_gdelt'].mean() * 100) if 'has_gdelt' in df_adm1.columns else 0.0
}

# Write global summary JSON
global_summary = {
    "stats": global_stats,
    "countries": sorted(list(country_averages.values()), key=lambda x: x["name"]),
    "heatmaps": heatmaps,
    "value_heatmaps": value_heatmaps
}

global_summary = clean_val(global_summary)

with open(DATA_OUT_DIR / "global_summary.json", "w", encoding="utf-8") as f:
    json.dump(global_summary, f, ensure_ascii=False, indent=2)
print("Saved global_summary.json")

# Load raw datasets for high-resolution country-specific tabs
print("Loading raw datasets for high-resolution exports...")
df_raw_ipc = pd.read_parquet(HERO_V6_DIR / "data" / "raw" / "ipc.parquet") if (HERO_V6_DIR / "data" / "raw" / "ipc.parquet").exists() else None
df_raw_acled = pd.read_parquet(HERO_V6_DIR / "data" / "raw" / "acled.parquet") if (HERO_V6_DIR / "data" / "raw" / "acled.parquet").exists() else None
df_raw_idp = pd.read_parquet(HERO_V6_DIR / "data" / "raw" / "idp.parquet") if (HERO_V6_DIR / "data" / "raw" / "idp.parquet").exists() else None
df_raw_rainfall = pd.read_parquet(HERO_V6_DIR / "data" / "raw" / "rainfall.parquet") if (HERO_V6_DIR / "data" / "raw" / "rainfall.parquet").exists() else None
df_raw_ndvi = pd.read_parquet(HERO_V6_DIR / "data" / "raw" / "wfp_ndvi.parquet") if (HERO_V6_DIR / "data" / "raw" / "wfp_ndvi.parquet").exists() else None
df_raw_wfp_prices = pd.read_parquet(HERO_V6_DIR / "data" / "raw" / "wfp_consolidated_single_market.parquet") if (HERO_V6_DIR / "data" / "raw" / "wfp_consolidated_single_market.parquet").exists() else None

# Write country-level JSON files
print("Generating country-specific JSON files...")
for code in all_countries:
    c_df_adm1 = df_adm1[df_adm1['Country'] == code].copy()
    c_df_adm2 = df_adm2[df_adm2['Country'] == code].copy()

    # Get admin lists
    adm1_list = []
    if not c_df_adm1.empty:
        adm1_list = c_df_adm1[['adm1_pcode', 'Level 1']].drop_duplicates().to_dict(orient='records')
        adm1_list = [{"pcode": r['adm1_pcode'], "name": r['Level 1']} for r in adm1_list if r['adm1_pcode'] != ""]

    adm2_list = []
    if not c_df_adm2.empty:
        c_df_adm2['adm1_pcode'] = c_df_adm2['adm1_pcode'].fillna("")
        adm2_list = c_df_adm2[['adm2_pcode', 'Area', 'adm1_pcode']].drop_duplicates().to_dict(orient='records')
        adm2_list = [{"pcode": r['adm2_pcode'], "name": r['Area'], "parent_pcode": r['adm1_pcode']} for r in adm2_list if r['adm2_pcode'] != ""]

    # Helper function to aggregate trends for a dataframe
    def aggregate_trends(df, group_col):
        if df.empty:
            return []
        
        ipc_cols = [c for c in df.columns if 'phase_' in c and c.endswith('_number')]
        other_sums = [
            'acled_total_events', 'acled_total_fatalities', 'idp_population',
            'acled_civilian_targeting_events', 'acled_demonstration_events', 'acled_political_violence_events',
            'acled_civilian_targeting_fatalities', 'acled_demonstration_fatalities', 'acled_political_violence_fatalities'
        ]
        gdelt_quads = ['verbal_coop', 'material_coop', 'verbal_conflict', 'material_conflict']
        for q in gdelt_quads:
            other_sums.append(f'gdelt_{q}_events')
            other_sums.append(f'gdelt_{q}_mentions')
            
        means = [
            'rain_1m_sum', 'rain_1m', 'rain_3m', 'rain_anomaly_1m', 'rain_anomaly_3m', 
            'wfp_price', 'wfp_inflation', 'wfp_obs_count', 'idp_staleness_days',
            'ndvi_vim', 'ndvi_viq'
        ]
        for q in gdelt_quads:
            means.append(f'gdelt_{q}_tone')
        
        grouped = df.groupby(group_col)
        
        trends = []
        for name_keys, g in grouped:
            from_dt, to_dt, val_p = name_keys
            
            row = {
                "from": str(from_dt),
                "to": str(to_dt),
                "period": str(val_p),
                "rows_count": len(g)
            }
            
            # WFP metadata
            if 'wfp_mapping_method' in g.columns:
                methods = g['wfp_mapping_method'].dropna().unique().tolist()
                row['wfp_mapping_method'] = str(methods[0]) if methods else "unknown"
                
            # IDP metadata
            if 'idp_assessment_type' in g.columns:
                types = g['idp_assessment_type'].dropna().unique().tolist()
                row['idp_assessment_type'] = ", ".join([str(t) for t in types]) if types else "unknown"
            if 'idp_reporting_round' in g.columns:
                rounds = g['idp_reporting_round'].dropna().unique().tolist()
                row['idp_reporting_round'] = ", ".join([str(r) for r in rounds]) if rounds else "unknown"
            
            # Sums
            for col in ipc_cols + other_sums:
                if col in g.columns:
                    val = g[col].sum()
                    row[col] = float(val) if pd.notna(val) else None
            
            # Weighted IPC percentages
            total_pop = row.get('phase_all_number', 0)
            if total_pop and total_pop > 0:
                for col in ipc_cols:
                    phase_name = col.replace('_number', '_percentage')
                    row[phase_name] = float((row[col] / total_pop) * 100)
            else:
                for col in [c for c in df.columns if 'phase_' in c and c.endswith('_percentage')]:
                    val = g[col].mean()
                    row[col] = float(val) if pd.notna(val) else None

            # Means
            for col in means:
                if col in g.columns:
                    val = g[col].mean()
                    row[col] = float(val) if pd.notna(val) else None
                    
            trends.append(row)
            
        trends = sorted(trends, key=lambda x: x["from"])
        return trends

    # Aggregations
    national_trends_adm1 = aggregate_trends(c_df_adm1, ['From', 'To', 'Validity period'])
    national_trends_adm2 = aggregate_trends(c_df_adm2, ['From', 'To', 'Validity period'])
    
    adm1_trends = {}
    if not c_df_adm1.empty:
        for pcode, g_pcode in c_df_adm1.groupby('adm1_pcode'):
            if pcode != "":
                adm1_trends[pcode] = aggregate_trends(g_pcode, ['From', 'To', 'Validity period'])
                
    adm2_trends = {}
    if not c_df_adm2.empty:
        for pcode, g_pcode in c_df_adm2.groupby('adm2_pcode'):
            if pcode != "":
                adm2_trends[pcode] = aggregate_trends(g_pcode, ['From', 'To', 'Validity period'])

    # Build country output
    country_data = {
        "code": code,
        "name": country_names.get(code, code),
        "adm1_units": adm1_list,
        "adm2_units": adm2_list,
        "trends": {
            "adm1": national_trends_adm1,
            "adm2": national_trends_adm2
        },
        "regions": {
            "adm1": adm1_trends,
            "adm2": adm2_trends
        },
        "markets": markets_by_country.get(code, [])
    }
    
    country_data = clean_dict(country_data)
    
    with open(COUNTRIES_OUT_DIR / f"{code}.json", "w", encoding="utf-8") as f:
        json.dump(country_data, f, ensure_ascii=False)

    # ── GENERATE RAW HIGH-RESOLUTION DATASETS ──
    # 1. IPC Raw
    if df_raw_ipc is not None:
        ipc_c = df_raw_ipc[df_raw_ipc['location_code'] == code].copy()
        raw_ipc_data = {"national": [], "regions": {"adm1": {}, "adm2": {}}}
        if not ipc_c.empty:
            def process_ipc_group(df_g, spatial_key=None):
                grp_cols = ['reference_period_start', 'reference_period_end', 'ipc_type']
                if spatial_key:
                    grp_cols.append(spatial_key)
                grouped = df_g.groupby(grp_cols)
                res = []
                for keys, g in grouped:
                    if spatial_key:
                        p_start, p_end, i_type, sp_val = keys
                    else:
                        p_start, p_end, i_type = keys
                    
                    row = {
                        "from": str(p_start),
                        "to": str(p_end),
                        "type": str(i_type)
                    }
                    total_pop = 0
                    p3plus = 0
                    for p in ['1', '2', '3', '4', '5']:
                        val = g[g['ipc_phase'] == p]['population_in_phase'].sum()
                        row[f"phase_{p}"] = float(val) if pd.notna(val) else 0.0
                        total_pop += val
                        if p in ['3', '4', '5']:
                            p3plus += val
                    
                    row["phase_3plus"] = float(p3plus)
                    row["phase_all"] = float(total_pop)
                    row["phase_3plus_percentage"] = float((p3plus / total_pop) * 100) if total_pop > 0 else 0.0
                    res.append(row)
                return sorted(res, key=lambda x: x["from"])

            raw_ipc_data["national"] = process_ipc_group(ipc_c)
            for pcode, g_pcode in ipc_c.groupby('admin1_code'):
                if pcode:
                    raw_ipc_data["regions"]["adm1"][pcode] = process_ipc_group(g_pcode, 'admin1_code')
            for pcode, g_pcode in ipc_c.groupby('admin2_code'):
                if pcode:
                    raw_ipc_data["regions"]["adm2"][pcode] = process_ipc_group(g_pcode, 'admin2_code')

        with open(COUNTRIES_OUT_DIR / f"{code}_raw_ipc.json", "w", encoding="utf-8") as f:
            json.dump(clean_val(raw_ipc_data), f, ensure_ascii=False)

    # 2. ACLED Raw
    if df_raw_acled is not None:
        acled_c = df_raw_acled[df_raw_acled['location_code'] == code].copy()
        raw_acled_data = {"national": [], "regions": {"adm1": {}, "adm2": {}}}
        if not acled_c.empty:
            def process_acled_group(df_g, spatial_key=None):
                grp_cols = ['reference_period_start', 'reference_period_end']
                if spatial_key:
                    grp_cols.append(spatial_key)
                grouped = df_g.groupby(grp_cols)
                res = []
                for keys, g in grouped:
                    if spatial_key:
                        p_start, p_end, sp_val = keys
                    else:
                        p_start, p_end = keys
                    
                    row = {
                        "from": str(p_start),
                        "to": str(p_end),
                        "total_events": int(g['events'].sum()),
                        "total_fatalities": float(g['fatalities'].sum())
                    }
                    for et in ['civilian_targeting', 'demonstrations', 'political_violence']:
                        et_g = g[g['event_type'] == et]
                        row[f"{et}_events"] = int(et_g['events'].sum())
                        row[f"{et}_fatalities"] = float(et_g['fatalities'].sum())
                    res.append(row)
                return sorted(res, key=lambda x: x["from"])

            raw_acled_data["national"] = process_acled_group(acled_c)
            for pcode, g_pcode in acled_c.groupby('admin1_code'):
                if pcode:
                    raw_acled_data["regions"]["adm1"][pcode] = process_acled_group(g_pcode, 'admin1_code')
            for pcode, g_pcode in acled_c.groupby('admin2_code'):
                if pcode:
                    raw_acled_data["regions"]["adm2"][pcode] = process_acled_group(g_pcode, 'admin2_code')

        with open(COUNTRIES_OUT_DIR / f"{code}_raw_acled.json", "w", encoding="utf-8") as f:
            json.dump(clean_val(raw_acled_data), f, ensure_ascii=False)

    # 3. IDP Raw
    if df_raw_idp is not None:
        idp_c = df_raw_idp[df_raw_idp['location_code'] == code].copy()
        raw_idp_data = {"national": [], "regions": {"adm1": {}, "adm2": {}}}
        if not idp_c.empty:
            def process_idp_group(df_g, spatial_key=None):
                grp_cols = ['reference_period_start', 'reference_period_end', 'reporting_round', 'assessment_type']
                if spatial_key:
                    grp_cols.append(spatial_key)
                grouped = df_g.groupby(grp_cols)
                res = []
                for keys, g in grouped:
                    if spatial_key:
                        p_start, p_end, r_round, a_type, sp_val = keys
                    else:
                        p_start, p_end, r_round, a_type = keys
                    
                    res.append({
                        "from": str(p_start),
                        "to": str(p_end),
                        "round": int(r_round),
                        "type": str(a_type),
                        "population": float(g['population'].sum())
                    })
                return sorted(res, key=lambda x: x["from"])

            raw_idp_data["national"] = process_idp_group(idp_c)
            for pcode, g_pcode in idp_c.groupby('admin1_code'):
                if pcode:
                    raw_idp_data["regions"]["adm1"][pcode] = process_idp_group(g_pcode, 'admin1_code')
            for pcode, g_pcode in idp_c.groupby('admin2_code'):
                if pcode:
                    raw_idp_data["regions"]["adm2"][pcode] = process_idp_group(g_pcode, 'admin2_code')

        with open(COUNTRIES_OUT_DIR / f"{code}_raw_idp.json", "w", encoding="utf-8") as f:
            json.dump(clean_val(raw_idp_data), f, ensure_ascii=False)

    # 4. Rainfall Raw (CHIRPS)
    if df_raw_rainfall is not None:
        rain_c = df_raw_rainfall[df_raw_rainfall['ISO3'] == code].copy()
        raw_rain_data = {"national": [], "regions": {"adm1": {}, "adm2": {}}}
        if not rain_c.empty:
            def process_rain_group(df_g):
                grouped = df_g.groupby('date')
                res = []
                for date, g in grouped:
                    res.append({
                        "date": str(date.date()) if hasattr(date, 'date') else str(date)[:10],
                        "rain_1m": float(g['rain_1m'].mean()) if pd.notna(g['rain_1m'].mean()) else None,
                        "rain_3m": float(g['rain_3m'].mean()) if pd.notna(g['rain_3m'].mean()) else None,
                        "rain_anomaly_1m": float(g['rain_anomaly_1m'].mean()) if pd.notna(g['rain_anomaly_1m'].mean()) else None,
                        "rain_anomaly_3m": float(g['rain_anomaly_3m'].mean()) if pd.notna(g['rain_anomaly_3m'].mean()) else None
                    })
                return sorted(res, key=lambda x: x["date"])

            raw_rain_data["national"] = process_rain_group(rain_c)
            for pcode, g_pcode in rain_c.groupby('PCODE'):
                if pcode:
                    adm_lvl = int(g_pcode['adm_level'].iloc[0])
                    lvl_key = "adm1" if adm_lvl == 1 else "adm2"
                    raw_rain_data["regions"][lvl_key][pcode] = process_rain_group(g_pcode)

        with open(COUNTRIES_OUT_DIR / f"{code}_raw_rainfall.json", "w", encoding="utf-8") as f:
            json.dump(clean_val(raw_rain_data), f, ensure_ascii=False)

    # 5. NDVI Raw
    if df_raw_ndvi is not None:
        ndvi_c = df_raw_ndvi[df_raw_ndvi['country_iso3'] == code].copy()
        raw_ndvi_data = {"national": [], "regions": {"adm1": {}, "adm2": {}}}
        if not ndvi_c.empty:
            def process_ndvi_group(df_g):
                grouped = df_g.groupby('date')
                res = []
                for date, g in grouped:
                    res.append({
                        "date": str(date.date()) if hasattr(date, 'date') else str(date)[:10],
                        "vim": float(g['vim'].mean()) if pd.notna(g['vim'].mean()) else None,
                        "vim_avg": float(g['vim_avg'].mean()) if pd.notna(g['vim_avg'].mean()) else None,
                        "viq": float(g['viq'].mean()) if pd.notna(g['viq'].mean()) else None
                    })
                return sorted(res, key=lambda x: x["date"])

            raw_ndvi_data["national"] = process_ndvi_group(ndvi_c)
            for pcode, g_pcode in ndvi_c.groupby('PCODE'):
                if pcode:
                    adm_lvl = int(g_pcode['adm_level'].iloc[0])
                    lvl_key = "adm1" if adm_lvl == 1 else "adm2"
                    raw_ndvi_data["regions"][lvl_key][pcode] = process_ndvi_group(g_pcode)

        with open(COUNTRIES_OUT_DIR / f"{code}_raw_ndvi.json", "w", encoding="utf-8") as f:
            json.dump(clean_val(raw_ndvi_data), f, ensure_ascii=False)

        # 6. WFP Raw Markets Prices
        raw_wfp_data = {"markets": {}}
        if df_raw_wfp_prices is not None:
            wfp_c = df_raw_wfp_prices[df_raw_wfp_prices['ISO3'] == code].copy()
            if not wfp_c.empty:
                for mkt_name, g_mkt in wfp_c.groupby('mkt_name'):
                    if mkt_name:
                        g_mkt = g_mkt.sort_values('DATES')
                        raw_wfp_data["markets"][mkt_name] = [
                            {
                                "date": str(row['DATES'])[:10],
                                "price_index": float(row['o_food_price_index']) if pd.notna(row['o_food_price_index']) else None,
                                "inflation": float(row['inflation_food_price_index']) if pd.notna(row['inflation_food_price_index']) else None
                            }
                            for _, row in g_mkt.iterrows()
                        ]
        with open(COUNTRIES_OUT_DIR / f"{code}_raw_markets.json", "w", encoding="utf-8") as f:
            json.dump(clean_val(raw_wfp_data), f, ensure_ascii=False)

print(f"All country JSON files generated successfully inside {COUNTRIES_OUT_DIR}!")
