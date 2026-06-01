"""
fetch.py — Pull IPC, ACLED, and IDP data from HDX HAPI in one global pass per theme.

Each theme is fetched once with no location_code (all countries), filtered to the
configured COUNTRIES, and saved as data/raw/{theme}.parquet.
Resume-safe: skips a theme whose file already exists.

Usage:
    python fetch.py
"""

import os
import time
import requests
import pandas as pd

from config import (
    COUNTRIES, DATE_FROM, THEMES,
    APP_NAME, EMAIL, APP_IDENTIFIER,
    API_BASE, API_VER, LIMIT, TIMEOUT, PAUSE,
    RAW_DIR, raw_file, PARQUET_ENGINE,
)


def get_app_id():
    if APP_IDENTIFIER:
        return APP_IDENTIFIER
    url = f"{API_BASE}/{API_VER}/encode_app_identifier"
    r = requests.get(url, params={"application": APP_NAME, "email": EMAIL}, timeout=TIMEOUT)
    r.raise_for_status()
    body = r.json()
    for k in ("encoded_app_identifier", "app_identifier", "identifier"):
        if k in body:
            print(f"[auth] token via '{k}'")
            return body[k]
    raise KeyError(f"Unexpected encode response keys: {list(body)}")


def fetch_all(theme, app_id, **params):
    url = f"{API_BASE}/{API_VER}/{theme}"
    base = {"output_format": "json", "app_identifier": app_id, "limit": LIMIT}
    base.update({k: v for k, v in params.items() if v is not None})
    rows, offset = [], 0
    while True:
        r = requests.get(url, params=dict(base, offset=offset), timeout=TIMEOUT)
        if r.status_code == 404:
            raise RuntimeError(f"404 on {url} — check theme name in config.py")
        r.raise_for_status()
        data = r.json().get("data", [])
        rows.extend(data)
        print(f"      ...{len(rows):,} rows", end="\r")
        if len(data) < LIMIT:
            break
        offset += LIMIT
        time.sleep(PAUSE)
    return pd.DataFrame(rows)


def fetch_theme(theme_key, app_id):
    out = raw_file(theme_key)
    if os.path.exists(out):
        print(f"  {theme_key:5s}: skipped (exists)")
        return

    # Global pull — no location_code, all countries from DATE_FROM onward.
    df = fetch_all(THEMES[theme_key], app_id, reference_period_start_min=DATE_FROM)

    if df.empty:
        print(f"  {theme_key:5s}: empty response")
        return

    # Filter client-side to the configured countries.
    df = df[df["location_code"].isin(COUNTRIES)].reset_index(drop=True)

    # Across countries, identifier columns (admin/location codes) arrive as a mix of
    # ints and strings, which pyarrow can't serialize. Pin object columns to string.
    obj_cols = df.select_dtypes(include="object").columns
    df[obj_cols] = df[obj_cols].astype("string")

    df.to_parquet(out, index=False, engine=PARQUET_ENGINE)
    n_countries = df["location_code"].nunique()
    print(f"  {theme_key:5s}: {len(df):,} rows across {n_countries} countries -> {os.path.basename(out)}")


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    app_id = get_app_id()

    print(f"Fetching {len(THEMES)} themes globally, filtering to {len(COUNTRIES)} countries "
          f"(from {DATE_FROM})...\n")

    for theme_key in THEMES:
        fetch_theme(theme_key, app_id)

    print("\nDone. Raw files in:", RAW_DIR)


if __name__ == "__main__":
    main()
