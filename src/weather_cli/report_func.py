"""Shared plotting and aggregation helpers for reports."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


def _require_datetime_index(df: pd.DataFrame) -> None:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex.")
    if df.empty:
        raise ValueError("No data available for plotting.")


def _daily_aggregate(series: pd.Series, how: str) -> pd.Series:
    """Aggregate a series to daily frequency using provided method."""
    return getattr(series.resample("1D"), how)()


def _resolve_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(f"Missing columns: {', '.join(candidates)}")


def _aggregate_by_day_of_year(series: pd.Series, how: str = "mean") -> pd.DataFrame:
    """Aggregate daily values across years by day-of-year for median/min/max."""
    daily = _daily_aggregate(series, "mean" if how == "mean" else how)
    grouped = daily.groupby([daily.index.month.rename("month"), daily.index.day.rename("day")]).agg(["median", "max", "min"])
    grouped = grouped.reset_index()
    idx = pd.to_datetime(dict(year=2000, month=grouped["month"], day=grouped["day"]))
    grouped.index = idx
    grouped = grouped.sort_index()
    grouped.index.name = "time"
    return grouped[["median", "max", "min"]]


def create_summary_table(df: pd.DataFrame, name: str | None = None) -> go.Figure:
    """Table: count, start/end, min/max (with timestamp), median per variable."""
    _require_datetime_index(df)
    skip = {"latitude", "longitude"}
    rows = []
    for column in df.columns:
        if column in skip:
            continue
        values = df[column].dropna()
        if values.empty:
            continue

        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty:
            continue

        max_val = numeric_values.max()
        min_val = numeric_values.min()
        max_time = numeric_values.idxmax().strftime("%Y-%m-%d %H:%M")
        min_time = numeric_values.idxmin().strftime("%Y-%m-%d %H:%M")
        rows.append(
            [
                column,
                len(numeric_values),
                df.index.min().strftime("%Y-%m-%d %H:%M"),
                df.index.max().strftime("%Y-%m-%d %H:%M"),
                f"{float(numeric_values.median()):.2f}",
                f"{float(max_val):.2f} ({max_time})",
                f"{float(min_val):.2f} ({min_time})",
            ]
        )

    headers = ["Variable", "Points", "Start", "End", "Median", "Max (time)", "Min (time)"]
    columns = list(map(list, zip(*rows))) if rows else [[] for _ in headers]

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(values=headers, fill_color="#1f77b4", font=dict(color="white")),
                cells=dict(values=columns),
            )
        ]
    )
    title = "Summary" if not name else f"Summary ({name})"
    fig.update_layout(title=title)
    return fig


def create_aggregation_info(names: list[str], weights: list[float]) -> go.Figure:
    """Display aggregation metadata before summary table."""
    rows = [[name, f"{w:.3f}"] for name, w in zip(names, weights)]
    headers = ["City", "Weight"]
    columns = list(map(list, zip(*rows))) if rows else [[] for _ in headers]
    fig = go.Figure(
        data=[
            go.Table(
                header=dict(values=headers, fill_color="#444", font=dict(color="white")),
                cells=dict(values=columns),
            )
        ]
    )
    fig.update_layout(title=f"Aggregated {len(names)} cities (median-based)")
    return fig


def create_temperature_band(
    df: pd.DataFrame,
    name: str,
    overall_min: pd.Series | None = None,
    overall_max: pd.Series | None = None,
) -> go.Figure:
    """Daily band plot (median/min/max across years) for temperature."""
    _require_datetime_index(df)
    if "temperature_c" not in df.columns:
        raise ValueError("temperature_c column required for temperature plot.")
    agg = _aggregate_by_day_of_year(df["temperature_c"], how="median")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=agg.index,
            y=agg["min"],
            mode="lines",
            name="Min",
            line=dict(color="rgba(214,39,40,0.45)", width=1.5),
            hovertemplate="%{x|%b %d}<br>Min: %{y:.2f}<extra></extra>",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=agg.index,
            y=agg["max"],
            mode="lines",
            name="Range (min–max)",
            line=dict(color="rgba(214,39,40,0.55)"),
            fill="tonexty",
            fillcolor="rgba(214,39,40,0.10)",
            hovertemplate="%{x|%b %d}<br>Max: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=agg.index,
            y=agg["median"],
            mode="lines",
            name="Median",
            line=dict(color="#1f77b4"),
            hovertemplate="%{x|%b %d}<br>Median: %{y:.2f}<extra></extra>",
        )
    )

    if overall_min is not None:
        fig.add_trace(
            go.Scatter(
                x=overall_min.index,
                y=overall_min,
                mode="lines",
                name="Overall min",
                line=dict(color="#666", dash="dash"),
                hovertemplate="%{x|%b %d}<br>Overall min: %{y:.2f}<extra></extra>",
            )
        )
    if overall_max is not None:
        fig.add_trace(
            go.Scatter(
                x=overall_max.index,
                y=overall_max,
                mode="lines",
                name="Overall max",
                line=dict(color="#111", dash="dash"),
                hovertemplate="%{x|%b %d}<br>Overall max: %{y:.2f}<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"Daily temperature for {name}",
        xaxis_title="Day of year",
        yaxis_title="Temperature (°C)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(tickformat="%b %d")
    return fig


def create_temperature_histogram(df: pd.DataFrame) -> go.Figure:
    """Histogram of hourly temperature values."""
    _require_datetime_index(df)
    if "temperature_c" not in df.columns:
        raise ValueError("temperature_c column required for histogram.")
    values = df["temperature_c"].dropna()
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=values,
            name="temperature_c",
            marker_color="#1f77b4",
            opacity=0.85,
        )
    )
    fig.update_layout(
        title="Hourly temperature distribution",
        xaxis_title="Temperature (°C)",
        yaxis_title="Counts",
        template="plotly_white",
    )
    fig.for_each_trace(lambda t: t.update(hovertemplate="%{x}<br>Count: %{y}<extra></extra>"))
    return fig


def create_daily_radiation_band(
    df: pd.DataFrame,
    name: str,
    solar_overall: tuple[pd.Series, pd.Series] | None = None,
    thermal_overall: tuple[pd.Series, pd.Series] | None = None,
) -> go.Figure:
    """Daily max solar and thermal radiation band plot (median/min/max of daily maxima)."""
    _require_datetime_index(df)
    solar_col = _resolve_column(df, ["surface_solar_radiation_downwards", "surface-solar-radiation-downwards"])
    thermal_col = _resolve_column(df, ["surface_thermal_radiation_downwards", "surface-thermal-radiation-downwards"])

    solar_daily_kw = _daily_aggregate(df[solar_col], "max") / 1000.0
    thermal_daily_kw = _daily_aggregate(df[thermal_col], "max") / 1000.0

    solar_agg = _aggregate_by_day_of_year(solar_daily_kw, how="max")
    thermal_agg = _aggregate_by_day_of_year(thermal_daily_kw, how="max")

    fig = go.Figure()
    # Solar band
    fig.add_trace(
        go.Scatter(
            x=solar_agg.index,
            y=solar_agg["min"],
            mode="lines",
            name="Solar min",
            line=dict(color="rgba(31,119,180,0.35)", width=1.5),
            hovertemplate="%{x|%b %d}<br>Solar min: %{y:.3f}<extra></extra>",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=solar_agg.index,
            y=solar_agg["max"],
            mode="lines",
            name="Solar range",
            line=dict(color="rgba(31,119,180,0.55)"),
            fill="tonexty",
            fillcolor="rgba(31,119,180,0.12)",
            hovertemplate="%{x|%b %d}<br>Solar max: %{y:.3f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=solar_agg.index,
            y=solar_agg["median"],
            mode="lines",
            name="Solar median max",
            line=dict(color="#1f77b4"),
            hovertemplate="%{x|%b %d}<br>Solar median max: %{y:.3f}<extra></extra>",
        )
    )

    # Thermal band
    fig.add_trace(
        go.Scatter(
            x=thermal_agg.index,
            y=thermal_agg["min"],
            mode="lines",
            name="Thermal min",
            line=dict(color="rgba(255,127,14,0.35)", width=1.5),
            hovertemplate="%{x|%b %d}<br>Thermal min: %{y:.3f}<extra></extra>",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=thermal_agg.index,
            y=thermal_agg["max"],
            mode="lines",
            name="Thermal range",
            line=dict(color="rgba(255,127,14,0.55)"),
            fill="tonexty",
            fillcolor="rgba(255,127,14,0.12)",
            hovertemplate="%{x|%b %d}<br>Thermal max: %{y:.3f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=thermal_agg.index,
            y=thermal_agg["median"],
            mode="lines",
            name="Thermal median max",
            line=dict(color="#ff7f0e"),
            hovertemplate="%{x|%b %d}<br>Thermal median max: %{y:.3f}<extra></extra>",
        )
    )

    if solar_overall is not None:
        overall_min, overall_max = solar_overall
        fig.add_trace(
            go.Scatter(
                x=overall_min.index,
                y=overall_min,
                mode="lines",
                name="Solar overall min",
                line=dict(color="#2b303b", dash="dash"),
                hovertemplate="%{x|%b %d}<br>Solar overall min: %{y:.3f}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=overall_max.index,
                y=overall_max,
                mode="lines",
                name="Solar overall max",
                line=dict(color="#0b132b", dash="dash"),
                hovertemplate="%{x|%b %d}<br>Solar overall max: %{y:.3f}<extra></extra>",
            )
        )

    if thermal_overall is not None:
        overall_min, overall_max = thermal_overall
        fig.add_trace(
            go.Scatter(
                x=overall_min.index,
                y=overall_min,
                mode="lines",
                name="Thermal overall min",
                line=dict(color="#6b3b0a", dash="dash"),
                hovertemplate="%{x|%b %d}<br>Thermal overall min: %{y:.3f}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=overall_max.index,
                y=overall_max,
                mode="lines",
                name="Thermal overall max",
                line=dict(color="#3b2005", dash="dash"),
                hovertemplate="%{x|%b %d}<br>Thermal overall max: %{y:.3f}<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"Daily maximum radiation for {name}",
        xaxis_title="Day of year",
        yaxis_title="Radiation (kW/m²)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(tickformat="%b %d")
    return fig


def create_daily_precipitation(
    df: pd.DataFrame,
    name: str,
    overall_min: pd.Series | None = None,
    overall_max: pd.Series | None = None,
) -> go.Figure:
    """Daily total precipitation band across years."""
    _require_datetime_index(df)
    col = _resolve_column(df, ["total_precipitation", "total-precipitation"])

    daily = _daily_aggregate(df[col], "sum") * 1000.0  # m -> mm
    agg = daily.groupby([daily.index.month.rename("month"), daily.index.day.rename("day")]).agg(["median", "max", "min"])
    agg = agg.reset_index()
    idx = pd.to_datetime(dict(year=2000, month=agg["month"], day=agg["day"]))
    agg.index = idx
    agg = agg.sort_index()
    agg.index.name = "time"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=agg.index,
            y=agg["min"],
            mode="lines",
            name="Min",
            line=dict(color="rgba(44,160,44,0.45)", width=1.5),
            hovertemplate="%{x|%b %d}<br>Min: %{y:.2f} mm<extra></extra>",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=agg.index,
            y=agg["max"],
            mode="lines",
            name="Range (min–max)",
            line=dict(color="rgba(44,160,44,0.55)"),
            fill="tonexty",
            fillcolor="rgba(44,160,44,0.10)",
            hovertemplate="%{x|%b %d}<br>Max: %{y:.2f} mm<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=agg.index,
            y=agg["median"],
            mode="lines",
            name="Median",
            line=dict(color="#2ca02c"),
            hovertemplate="%{x|%b %d}<br>Median: %{y:.2f} mm<extra></extra>",
        )
    )

    if overall_min is not None:
        fig.add_trace(
            go.Scatter(
                x=overall_min.index,
                y=overall_min,
                mode="lines",
                name="Overall min",
                line=dict(color="#555", dash="dash"),
                hovertemplate="%{x|%b %d}<br>Overall min: %{y:.2f} mm<extra></extra>",
            )
        )
    if overall_max is not None:
        fig.add_trace(
            go.Scatter(
                x=overall_max.index,
                y=overall_max,
                mode="lines",
                name="Overall max",
                line=dict(color="#222", dash="dash"),
                hovertemplate="%{x|%b %d}<br>Overall max: %{y:.2f} mm<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"Daily total precipitation for {name}",
        xaxis_title="Day of year",
        yaxis_title="Precipitation (mm)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(tickformat="%b %d")
    return fig


def write_static_page(figures: Iterable[go.Figure], output_html: Path, title: str, auto_open: bool = True) -> None:
    """Compose multiple figures into a single static HTML page."""
    figures = list(figures)
    if not figures:
        raise ValueError("No figures provided for rendering.")

    fragments = [pio.to_html(fig, include_plotlyjs=False, full_html=False) for fig in figures]
    html = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{title}</title>
  <script src=\"https://cdn.plot.ly/plotly-2.35.2.min.js\"></script>
</head>
<body>
  <h1>{title}</h1>
  {body}
</body>
</html>""".format(title=title, body="\n".join(fragments))

    output_html.write_text(html, encoding="utf-8")
    if auto_open:
        import webbrowser

        webbrowser.open(output_html.as_uri())
    print(f"Opened report at {output_html}")
