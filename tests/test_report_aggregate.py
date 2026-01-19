from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from weather_cli.report_aggregate import _aggregate_numeric_frames, render_aggregate_report


def make_city(temp_shift: float) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    return pd.DataFrame(
        {
            "temperature_c": np.array([0, 1, 2, 3], dtype=float) + temp_shift,
            "surface_solar_radiation_downwards": [10, 20, 30, 40],
            "surface_thermal_radiation_downwards": [5, 6, 7, 8],
            "total_precipitation": [0.1, 0.2, 0.0, 0.3],
            "heat_index_c": np.array([5, 6, 7, 8], dtype=float) + temp_shift,
        },
        index=idx,
    )


def test_aggregate_numeric_frames_weighted_median():
    dfs = [make_city(0.0), make_city(10.0)]
    agg_df, overall_min, overall_max = _aggregate_numeric_frames(dfs, [0.8, 0.2])

    assert "temperature_c" in agg_df.columns
    # weighted median of [0,10] with weights [.8,.2] is 0.0
    assert agg_df.iloc[0]["temperature_c"] == pytest.approx(0.0)
    assert overall_min["temperature_c"].iloc[0] == 0.0
    assert overall_max["temperature_c"].iloc[0] == 10.0
    # classification rebuilt
    assert "heat_index_classification" in agg_df.columns


def test_render_aggregate_report(tmp_path, monkeypatch):
    out = tmp_path / "agg.html"
    monkeypatch.setattr("weather_cli.report_aggregate.write_static_page", lambda *args, **kwargs: None)

    dfs = [make_city(0.0), make_city(1.0)]
    render_aggregate_report(dfs, ["Gothenburg", "Oslo"], [0.5, 0.5], output_html=out, auto_open=False)


def test_render_aggregate_report_adds_city_summaries(tmp_path, monkeypatch):
    summary_calls = []

    def fake_summary(df, name=None):
        summary_calls.append(name)
        return go.Figure()

    # stub unrelated figures to keep focus
    monkeypatch.setattr("weather_cli.report_aggregate.create_summary_table", fake_summary)
    monkeypatch.setattr("weather_cli.report_aggregate.create_temperature_histogram", lambda *a, **k: go.Figure())
    monkeypatch.setattr("weather_cli.report_aggregate.create_temperature_band", lambda *a, **k: go.Figure())
    monkeypatch.setattr("weather_cli.report_aggregate.create_daily_radiation_band", lambda *a, **k: go.Figure())
    monkeypatch.setattr("weather_cli.report_aggregate.create_daily_precipitation", lambda *a, **k: go.Figure())
    monkeypatch.setattr("weather_cli.report_aggregate.create_aggregation_info", lambda *a, **k: go.Figure())
    monkeypatch.setattr("weather_cli.report_aggregate.write_static_page", lambda *a, **k: None)

    out = tmp_path / "agg.html"
    dfs = [make_city(0.0), make_city(1.0)]
    render_aggregate_report(dfs, ["Gothenburg", "Oslo"], [0.5, 0.5], output_html=out, auto_open=False)

    # Expect one per city plus an aggregated summary
    assert summary_calls[:2] == ["Gothenburg", "Oslo"]
    assert any(name == "Aggregated" for name in summary_calls)


def test_precip_overall_uses_daily_totals(tmp_path, monkeypatch):
    idx = pd.date_range("2020-01-01", periods=2, freq="D")

    def make_precip(vals):
        return pd.DataFrame(
            {
                "temperature_c": [0.0, 0.0],
                "surface_solar_radiation_downwards": [0.0, 0.0],
                "surface_thermal_radiation_downwards": [0.0, 0.0],
                "total_precipitation": vals,
                "heat_index_c": [0.0, 0.0],
            },
            index=idx,
        )

    cities = {
        "A": make_precip([0.001, 0.002]),  # 1 mm, 2 mm
        "B": make_precip([0.005, 0.003]),  # 5 mm, 3 mm
    }

    dfs = [cities["A"], cities["B"]]
    captured = {}

    def fake_precip(fig_df, name, overall_min, overall_max):
        captured["overall_min"] = overall_min
        captured["overall_max"] = overall_max
        return go.Figure()

    # stub out other renderers to keep test focused
    monkeypatch.setattr("weather_cli.report_aggregate.create_aggregation_info", lambda *a, **k: None)
    monkeypatch.setattr("weather_cli.report_aggregate.create_summary_table", lambda *a, **k: None)
    monkeypatch.setattr("weather_cli.report_aggregate.create_temperature_histogram", lambda *a, **k: None)
    monkeypatch.setattr("weather_cli.report_aggregate.create_temperature_band", lambda *a, **k: None)
    monkeypatch.setattr("weather_cli.report_aggregate.create_daily_radiation_band", lambda *a, **k: None)
    monkeypatch.setattr("weather_cli.report_aggregate.create_daily_precipitation", fake_precip)
    monkeypatch.setattr("weather_cli.report_aggregate.write_static_page", lambda *a, **k: None)

    out = tmp_path / "agg.html"
    render_aggregate_report(dfs, ["A", "B"], [0.5, 0.5], output_html=out, auto_open=False)

    overall_min = captured["overall_min"]
    overall_max = captured["overall_max"]

    assert list(overall_min.values) == [1.0, 2.0]
    assert list(overall_max.values) == [5.0, 3.0]