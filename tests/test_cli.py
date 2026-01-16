from pathlib import Path

import pandas as pd
import pytest

from weather_cli.cli import Weather


def test_dataset_path_includes_params(tmp_path):
    cli = Weather(workspace=tmp_path)
    path = cli._dataset_path("Gothenburg", 1.0, 2.0)
    assert str(path).endswith("gothenburg_1.0000_2.0000.zip")


def test_download_skips_existing(tmp_path, monkeypatch):
    cli = Weather(workspace=tmp_path)
    existing = cli._dataset_path("Gothenburg", 1.0, 2.0)
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("dummy")

    called = {"downloads": 0}

    def fake_download(*args, **kwargs):
        called["downloads"] += 1

    monkeypatch.setattr("weather_cli.cli.download_timeseries", fake_download)

    cli.download(name="Gothenburg", lat=1.0, lon=2.0)
    # Should skip because file exists
    assert called["downloads"] == 0


def test_save_saves_combined_csv(tmp_path, monkeypatch):
    cli = Weather(workspace=tmp_path)

    fake_df = pd.DataFrame(
        {
            "temperature_c": [1.0],
            "wind": [2.0],
        },
        index=pd.to_datetime(["2020-01-01"]),
    )
    monkeypatch.setattr("weather_cli.cli.load_location_timeseries", lambda *args, **kwargs: fake_df)

    cli.save("City", output=None)
    csv_path = tmp_path / ".weather_era5" / "city.csv"
    assert csv_path.exists()
    text = csv_path.read_text()
    assert "temperature_c" in text and "wind" in text
    assert "timestamp" in text.splitlines()[0]


def test_report_calls_renderer(tmp_path, monkeypatch):
    cli = Weather(workspace=tmp_path)

    fake_df = pd.DataFrame({"temperature_c": [1.0]}, index=pd.to_datetime(["2020-01-01"]))
    monkeypatch.setattr("weather_cli.cli.load_location_timeseries", lambda *args, **kwargs: fake_df)

    called = {}

    def fake_render(df, name, output_html, auto_open):
        called["df"] = df
        called["name"] = name
        output_html.write_text("ok")

    monkeypatch.setattr("weather_cli.cli.render_report", fake_render)

    cli.report("City")
    html_path = tmp_path / ".weather_era5" / "city.html"
    assert html_path.exists()
    assert called["name"] == "City"