"""Aggregate multi-city ERA5 reports."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from .process_data import _classify_heat_index
from .report_func import (
    _aggregate_by_day_of_year,
    create_aggregation_info,
    create_daily_precipitation,
    create_daily_radiation_band,
    create_summary_table,
    create_temperature_band,
    create_temperature_histogram,
    write_static_page,
)


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    if values.size == 0:
        return np.nan
    order = np.argsort(values)
    vals = values[order]
    w = weights[order]
    w = w / w.sum()
    cdf = np.cumsum(w)
    return vals[np.searchsorted(cdf, 0.5)]


def _aggregate_numeric_frames(dfs: list[pd.DataFrame], weights: list[float]) -> tuple[pd.DataFrame, dict[str, pd.Series], dict[str, pd.Series]]:
    exclude_cols = {"latitude", "longitude"}
    numeric_sets = [set(df.select_dtypes(include=[np.number]).columns) - exclude_cols for df in dfs]
    common_cols = set.intersection(*numeric_sets)
    if not common_cols:
        raise SystemExit("No common numeric columns to aggregate across cities.")

    combined_index = pd.DatetimeIndex(sorted(set().union(*[df.index for df in dfs])))
    agg_df = pd.DataFrame(index=combined_index)
    overall_min: dict[str, pd.Series] = {}
    overall_max: dict[str, pd.Series] = {}

    weight_arr = np.asarray(weights, dtype=float)

    for col in sorted(common_cols):
        series_list = [df[col].reindex(combined_index) for df in dfs]
        combined = pd.concat(series_list, axis=1)
        overall_min[col] = combined.min(axis=1)
        overall_max[col] = combined.max(axis=1)

        def agg_row(row: pd.Series) -> float:
            vals = row.to_numpy(dtype=float)
            mask = ~np.isnan(vals)
            if not mask.any():
                return np.nan
            return _weighted_median(vals[mask], weight_arr[mask])

        agg_df[col] = combined.apply(agg_row, axis=1)

    agg_df.index.name = "timestamp"

    # Rebuild classification from aggregated heat index if present
    if "heat_index_c" in agg_df.columns:
        hi_f = agg_df["heat_index_c"] * 1.8 + 32.0
        agg_df["heat_index_classification"] = [
            _classify_heat_index(val) if not np.isnan(val) else np.nan for val in hi_f
        ]

    return agg_df, overall_min, overall_max


def _prepare_overall_daily(series: pd.Series, how: str, which: str) -> pd.Series:
    """Aggregate overall min/max to day-of-year series for dashed overlays."""
    agg = _aggregate_by_day_of_year(series, how=how)
    return agg[which]


def render_aggregate_report(
    dfs: Sequence[pd.DataFrame],
    names: Sequence[str],
    weights: Sequence[float],
    output_html: Path,
    auto_open: bool = True,
) -> None:
    if len(names) != len(weights) or len(names) != len(dfs):
        raise SystemExit("Weights must match number of cities and dataframes.")
    if not np.isclose(sum(weights), 1.0, atol=1e-6):
        raise SystemExit("Weights must sum to 1.0")
    agg_df, overall_min, overall_max = _aggregate_numeric_frames(dfs, list(weights))

    # One summary table per city plus aggregated summary.
    city_summaries = [create_summary_table(df, name=n) for n, df in zip(names, dfs)]

    figures: list = []
    figures.append(create_aggregation_info(list(names), list(weights)))
    figures.extend(city_summaries)
    figures.append(create_summary_table(agg_df, name="Aggregated"))
    figures.append(create_temperature_histogram(agg_df))

    overall_temp_min = overall_temp_max = None
    if "temperature_c" in overall_min and "temperature_c" in overall_max:
        overall_temp_min = _prepare_overall_daily(overall_min["temperature_c"], how="min", which="min")
        overall_temp_max = _prepare_overall_daily(overall_max["temperature_c"], how="max", which="max")
    figures.append(
        create_temperature_band(
            agg_df,
            name=", ".join(names),
            overall_min=overall_temp_min,
            overall_max=overall_temp_max,
        )
    )

    solar_overall = thermal_overall = None
    if "surface_solar_radiation_downwards" in overall_min or "surface-solar-radiation-downwards" in overall_min:
        solar_key = "surface_solar_radiation_downwards" if "surface_solar_radiation_downwards" in overall_min else "surface-solar-radiation-downwards"
        solar_overall = (
            _prepare_overall_daily(overall_min[solar_key] / 1000.0, how="min", which="min"),
            _prepare_overall_daily(overall_max[solar_key] / 1000.0, how="max", which="max"),
        )
    if "surface_thermal_radiation_downwards" in overall_min or "surface-thermal-radiation-downwards" in overall_min:
        thermal_key = "surface_thermal_radiation_downwards" if "surface_thermal_radiation_downwards" in overall_min else "surface-thermal-radiation-downwards"
        thermal_overall = (
            _prepare_overall_daily(overall_min[thermal_key] / 1000.0, how="min", which="min"),
            _prepare_overall_daily(overall_max[thermal_key] / 1000.0, how="max", which="max"),
        )
    figures.append(
        create_daily_radiation_band(
            agg_df,
            name=", ".join(names),
            solar_overall=solar_overall,
            thermal_overall=thermal_overall,
        )
    )

    overall_precip_min = overall_precip_max = None
    if "total_precipitation" in overall_min or "total-precipitation" in overall_min:
        precip_key = "total_precipitation" if "total_precipitation" in overall_min else "total-precipitation"

        # Use daily sums per city, then derive overall min/max of those daily totals.
        daily_totals = []
        for df in dfs:
            if precip_key not in df.columns:
                continue
            daily_totals.append(df[precip_key].resample("1D").sum() * 1000.0)  # m -> mm

        if daily_totals:
            combined_daily = pd.concat(daily_totals, axis=1, join="outer")
            per_day_min = combined_daily.min(axis=1)
            per_day_max = combined_daily.max(axis=1)
            overall_precip_min = _aggregate_by_day_of_year(per_day_min, how="min")[["min"]].squeeze()
            overall_precip_max = _aggregate_by_day_of_year(per_day_max, how="max")[["max"]].squeeze()

    figures.append(
        create_daily_precipitation(
            agg_df,
            name=", ".join(names),
            overall_min=overall_precip_min,
            overall_max=overall_precip_max,
        )
    )

    write_static_page(
        figures,
        output_html=output_html,
        title=f"Aggregated ERA5 data for {', '.join(names)}",
        auto_open=auto_open,
    )
