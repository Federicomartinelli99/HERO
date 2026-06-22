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
    df['has_geojson'] = ((df['adm1_pcode'] != "") | (df['adm2_pcode'] != "")).astype(int)

    # Overall score (simple average of keys)
    indicators = ['has_ipc', 'has_acled', 'has_idp', 'has_rainfall', 'has_wfp']
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
    "wfp": "has_wfp"
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
    "wfp": ("wfp_price", "mean")
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
    "avg_completeness_wfp": float(df_adm1['has_wfp'].mean() * 100)
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
        means = [
            'rain_1m_sum', 'rain_1m', 'rain_3m', 'rain_anomaly_1m', 'rain_anomaly_3m', 
            'wfp_price', 'wfp_inflation', 'wfp_obs_count', 'idp_staleness_days'
        ]
        
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

print(f"All country JSON files generated successfully inside {COUNTRIES_OUT_DIR}!")
