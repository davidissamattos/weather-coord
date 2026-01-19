"""Plotting orchestrator for single-location ERA5 reports."""
from __future__ import annotations

from pathlib import Path
import webbrowser

import pandas as pd

from .report_func import (
    create_daily_precipitation,
    create_daily_radiation_band,
    create_summary_table,
    create_temperature_band,
    create_temperature_histogram,
    write_static_page,
)


def render_report(df: pd.DataFrame, name: str, output_html: Path, auto_open: bool = True) -> None:
    """Build report with targeted figures for fixed-variable dataset."""
    figures = [
        create_summary_table(df, name=name),
        create_temperature_band(df, name),
        create_temperature_histogram(df),
        create_daily_radiation_band(df, name),
        create_daily_precipitation(df, name),
    ]

    write_static_page(
        figures,
        output_html=output_html,
        title=f"ERA5 data for {name}",
        auto_open=auto_open,
    )
