from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

from weather_cli import report


def sample_df():
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "temperature_c": [0.0, 1.0, 2.0, 3.0, 4.0],
            "surface-solar-radiation-downwards": [10, 20, 30, 40, 50],
            "surface-thermal-radiation-downwards": [5, 6, 7, 8, 9],
            "total-precipitation": [0.1, 0.0, 0.2, 0.0, 0.3],
        },
        index=idx,
    )


def test_create_summary_table():
    df = sample_df()
    fig = report.create_summary_table(df)
    assert isinstance(fig, go.Figure)
    assert any(isinstance(tr, go.Table) for tr in fig.data)
    headers = fig.data[0].header.values
    assert "Mean" in headers


def test_temperature_climatology_band():
    df = sample_df()
    fig = report.create_temperature_climatology(df, "Site")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 3  # min band, max band, mean line


def test_temperature_histogram():
    df = sample_df()
    fig = report.create_temperature_histogram(df)
    assert isinstance(fig, go.Figure)
    assert any(isinstance(tr, go.Histogram) for tr in fig.data)


def test_daily_radiation_max():
    df = sample_df()
    fig = report.create_daily_radiation_max(df, "Site")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2  # solar + thermal


def test_daily_precipitation_band():
    df = sample_df()
    fig = report.create_daily_precipitation(df, "Site")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 3  # min, max (band), mean


def test_write_static_page(tmp_path, monkeypatch):
    fig = go.Figure(data=[go.Scatter(x=[1], y=[1])])
    out = tmp_path / "report.html"

    monkeypatch.setattr(report.webbrowser, "open", lambda *_args, **_kwargs: None)
    report.write_static_page([fig], out, title="Test Report", auto_open=True)

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "Test Report" in content


def test_render_report(tmp_path, monkeypatch):
    df = sample_df()
    out = tmp_path / "report.html"
    monkeypatch.setattr(report.webbrowser, "open", lambda *_args, **_kwargs: None)
    report.render_report(df, name="City", output_html=out, auto_open=True)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "Summary" in content
