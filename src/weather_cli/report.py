"""Plotting helpers for ERA5 point time-series reports."""
from __future__ import annotations

import webbrowser
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
    """Aggregate daily values across years by day-of-year for mean/min/max."""
    daily = _daily_aggregate(series, "mean" if how == "mean" else how)
    grouped = daily.groupby([daily.index.month.rename("month"), daily.index.day.rename("day")]).agg(["mean", "max", "min"])
    grouped = grouped.reset_index()
    idx = pd.to_datetime(dict(year=2000, month=grouped["month"], day=grouped["day"]))
    grouped.index = idx
    grouped = grouped.sort_index()
    grouped.index.name = "time"
    return grouped[["mean", "max", "min"]]


def create_summary_table(df: pd.DataFrame) -> go.Figure:
    """Table: count, start/end, min/max (with timestamp), mean, median per variable."""
    _require_datetime_index(df)
    rows = []
    for column in df.columns:
        values = df[column].dropna()
        if values.empty:
            continue
        max_val = values.max()
        min_val = values.min()
        max_time = values.idxmax().strftime("%Y-%m-%d %H:%M")
        min_time = values.idxmin().strftime("%Y-%m-%d %H:%M")
        rows.append(
            [
                column,
                len(values),
                df.index.min().strftime("%Y-%m-%d %H:%M"),
                df.index.max().strftime("%Y-%m-%d %H:%M"),
                f"{float(values.mean()):.2f}",
                f"{float(values.median()):.2f}",
                f"{float(max_val):.2f} ({max_time})",
                f"{float(min_val):.2f} ({min_time})",
            ]
        )

    headers = ["Variable", "Points", "Start", "End", "Mean", "Median", "Max (time)", "Min (time)"]
    columns = list(map(list, zip(*rows))) if rows else [[] for _ in headers]

    fig = go.Figure(
        data=
        [
            go.Table(
                header=dict(values=headers, fill_color="#1f77b4", font=dict(color="white")),
                cells=dict(values=columns),
            )
        ]
    )
    fig.update_layout(title="Summary")
    return fig


def create_temperature_climatology(df: pd.DataFrame, name: str) -> go.Figure:
    """Daily band plot (mean/min/max across years) for temperature."""
    _require_datetime_index(df)
    if "temperature_c" not in df.columns:
        raise ValueError("temperature_c column required for temperature plot.")
    agg = _aggregate_by_day_of_year(df["temperature_c"], how="mean")

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
            y=agg["mean"],
            mode="lines",
            name="Mean",
            line=dict(color="#1f77b4"),
            hovertemplate="%{x|%b %d}<br>Mean: %{y:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"Temperature daily climatology for {name}",
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


def create_daily_radiation_max(df: pd.DataFrame, name: str) -> go.Figure:
    """Daily max solar and thermal radiation line plot."""
    _require_datetime_index(df)
    solar_col = _resolve_column(df, ["surface_solar_radiation_downwards", "surface-solar-radiation-downwards"])
    thermal_col = _resolve_column(df, ["surface_thermal_radiation_downwards", "surface-thermal-radiation-downwards"])

    solar_daily = _daily_aggregate(df[solar_col], "max")
    thermal_daily = _daily_aggregate(df[thermal_col], "max")

    solar_agg = _aggregate_by_day_of_year(solar_daily, how="max")
    thermal_agg = _aggregate_by_day_of_year(thermal_daily, how="max")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=solar_agg.index,
            y=solar_agg["mean"],
            mode="lines",
            name="Solar (daily max mean)",
            line=dict(color="#1f77b4"),
            hovertemplate="%{x|%b %d}<br>Solar mean max: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=thermal_agg.index,
            y=thermal_agg["mean"],
            mode="lines",
            name="Thermal (daily max mean)",
            line=dict(color="#ff7f0e"),
            hovertemplate="%{x|%b %d}<br>Thermal mean max: %{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Daily max radiation climatology for {name}",
        xaxis_title="Day of year",
        yaxis_title="W/m²",
        template="plotly_white",
        hovermode="x unified",
    )
    fig.update_xaxes(tickformat="%b %d")
    return fig


def create_daily_precipitation(df: pd.DataFrame, name: str) -> go.Figure:
    """Daily total precipitation with climatological band across years."""
    _require_datetime_index(df)
    col = _resolve_column(df, ["total_precipitation", "total-precipitation"])

    daily = _daily_aggregate(df[col], "sum")
    agg = daily.groupby([daily.index.month.rename("month"), daily.index.day.rename("day")]).agg(["mean", "max", "min"])
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
            hovertemplate="%{x|%b %d}<br>Min: %{y:.3f}<extra></extra>",
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
            hovertemplate="%{x|%b %d}<br>Max: %{y:.3f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=agg.index,
            y=agg["mean"],
            mode="lines",
            name="Mean",
            line=dict(color="#2ca02c"),
            hovertemplate="%{x|%b %d}<br>Mean: %{y:.3f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"Daily total precipitation climatology for {name}",
        xaxis_title="Day of year",
        yaxis_title="Precipitation (m)",
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
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
</head>
<body>
  <h1>{title}</h1>
  {body}
</body>
</html>""".format(title=title, body="\n".join(fragments))

    output_html.write_text(html, encoding="utf-8")
    if auto_open:
        webbrowser.open(output_html.as_uri())
    print(f"Opened report at {output_html}")


def render_report(df: pd.DataFrame, name: str, output_html: Path, auto_open: bool = True) -> None:
    """Build report with targeted figures for fixed-variable dataset."""
    figures: list[go.Figure] = []
    figures.append(create_summary_table(df))
    figures.append(create_temperature_climatology(df, name))
    figures.append(create_temperature_histogram(df))
    figures.append(create_daily_radiation_max(df, name))
    figures.append(create_daily_precipitation(df, name))

    write_static_page(
        figures,
        output_html=output_html,
        title=f"ERA5 data for {name}",
        auto_open=auto_open,
    )
