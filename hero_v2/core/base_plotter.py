"""
hero_v2.core.base_plotter
==========================
Classe base per le visualizzazioni del progetto H.E.R.O.
Definisce palette di colori, stili comuni e utility grafiche condivise.
"""

from abc import ABC
import pandas as pd
import numpy as np
import altair as alt
from typing import Tuple

class BasePlotter(ABC):
    """
    Fornisce la base estetica e funzionale per tutti i moduli grafici.
    Uniforma palette di colori e stili grafici Altair e Plotly.
    """

    # --- Palette Colori Premium H.E.R.O. ---
    HERO_COLORS = {
        "primary": "#1e3a8a",       # Deep Blue
        "secondary": "#0f766e",     # Teal
        "accent": "#f59e0b",        # Amber
        "danger": "#dc2626",        # Red
        "success": "#16a34a",       # Green
        "neutral_dark": "#1f2937",  # Dark Slate
        "neutral_light": "#f3f4f6", # Light Gray
        "neutral_mid": "#9ca3af",   # Muted Gray
        "up_trend": "#16a34a",      # Green for improvements (e.g. price drops or high rainfall)
        "down_trend": "#dc2626",    # Red for issues (e.g. price spikes or droughts)
    }

    @staticmethod
    def configure_altair_theme(chart: alt.Chart) -> alt.Chart:
        """Applica la configurazione estetica uniforme H.E.R.O. ai grafici Altair."""
        return chart.configure_view(
            stroke=None
        ).configure_axis(
            grid=True,
            gridColor="#e5e7eb",
            gridWidth=0.6,
            labelColor="#4b5563",
            titleColor="#1f2937",
            labelFont="Inter, Roboto, sans-serif",
            titleFont="Inter, Roboto, sans-serif",
            labelFontSize=10,
            titleFontSize=11,
            titlePadding=10
        ).configure_title(
            font="Inter, Roboto, sans-serif",
            fontSize=14,
            fontWeight="bold",
            color="#111827",
            anchor="start",
            subtitleFont="Inter, Roboto, sans-serif",
            subtitleFontSize=11,
            subtitleColor="#6b7280",
            subtitlePadding=5
        ).configure_legend(
            labelFont="Inter, Roboto, sans-serif",
            titleFont="Inter, Roboto, sans-serif",
            labelColor="#4b5563",
            titleColor="#1f2937",
            labelFontSize=10,
            titleFontSize=11
        )

    @staticmethod
    def safe_bubble_size(series: pd.Series, min_size: float = 6.0, max_size: float = 28.0) -> pd.Series:
        """
        Normalizza una serie di valori numerici (anche negativi o con outlier)
        in dimensioni per marker/bolle strettamente positive.
        """
        x = series.abs()
        xmin = x.min()
        xmax = x.max()

        if pd.isna(xmin) or xmin == xmax:
            return pd.Series(np.repeat((min_size + max_size) / 2, len(series)), index=series.index)

        return min_size + (x - xmin) / (xmax - xmin) * (max_size - min_size)

    @staticmethod
    def robust_quantiles(series: pd.Series) -> Tuple[float, float]:
        """Calcola gli estremi robusti (5° e 95° percentile) ignorando outlier estremi."""
        q1 = float(series.quantile(0.05))
        q2 = float(series.quantile(0.95))
        if q1 == q2:
            q1 = float(series.min()) if pd.notna(series.min()) else 0.0
            q2 = float(series.max()) if pd.notna(series.max()) else 1.0
        return q1, q2
