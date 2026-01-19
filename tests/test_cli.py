from pathlib import Path
from contextlib import contextmanager

import pandas as pd
import pytest

from weather_cli.cli import Weather


def test_dataset_path_includes_params(tmp_path):
    cli = Weather(workspace=tmp_path)
    path = cli._dataset_path("Gothenburg", "SE", 1.0, 2.0)
    assert str(path).endswith("gothenburg_SE_1.00_2.00.zip")


def test_download_skips_existing(tmp_path, monkeypatch):
    cli = Weather(workspace=tmp_path)
    existing = cli._dataset_path("Gothenburg", "SE", 1.0, 2.0)
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("dummy")

    called = {"downloads": 0}

    def fake_download(*args, **kwargs):
        called["downloads"] += 1

    monkeypatch.setattr("weather_cli.cli.download_timeseries", fake_download)

    cli.download(name="Gothenburg", country="SE", lat=1.0, lon=2.0)
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
    monkeypatch.setattr("weather_cli.cli.get_cached_location_timeseries", lambda *args, **kwargs: fake_df)

    cli.save("City", output=None)
    csv_path = tmp_path / ".weather_era5" / "city.csv"
    assert csv_path.exists()
    text = csv_path.read_text()
    assert "temperature_c" in text and "wind" in text
    assert "timestamp" in text.splitlines()[0]


def test_report_calls_renderer(tmp_path, monkeypatch):
    cli = Weather(workspace=tmp_path)

    fake_df = pd.DataFrame({"temperature_c": [1.0]}, index=pd.to_datetime(["2020-01-01"]))
    monkeypatch.setattr("weather_cli.cli.get_cached_location_timeseries", lambda *args, **kwargs: fake_df)

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


def test_report_shows_spinner_for_aggregate(tmp_path, monkeypatch, capsys):
    cli = Weather(workspace=tmp_path)

    def fake_render(dfs, names, weights, output_html, auto_open=True):
        called["dfs"] = dfs
        output_html.write_text("ok")

    called = {}

    @contextmanager
    def fake_spinner(message, interval=0.1):
        called["message"] = message
        yield

    monkeypatch.setattr("weather_cli.cli.render_aggregate_report", fake_render)
    monkeypatch.setattr("weather_cli.cli.get_cached_location_timeseries", lambda data_dir, name: pd.DataFrame())
    monkeypatch.setattr("weather_cli.cli._spinner", fake_spinner)

    cli.report(name="A,B", open_browser=False)

    assert called["message"].startswith("Generating aggregated data report")


def test_refresh_database_command(tmp_path, monkeypatch):
    cli = Weather(workspace=tmp_path)

    called = {}

    def fake_refresh(data_dir):
        called["data_dir"] = data_dir

    @contextmanager
    def fake_spinner(message, interval=0.1):
        called["message"] = message
        yield

    monkeypatch.setattr("weather_cli.cli.refresh_database", fake_refresh)
    monkeypatch.setattr("weather_cli.cli._spinner", fake_spinner)

    cli.refresh_database()

    assert called["data_dir"] == cli.data_dir
    assert called["message"] == "Refreshing database..."


def test_report_accepts_tuple_names(tmp_path, monkeypatch):
    cli = Weather(workspace=tmp_path)

    called = {}

    def fake_render(dfs, names, weights, output_html, auto_open=True):
        called["names"] = names
        called["weights"] = weights
        called["dfs_len"] = len(dfs)
        called["output_html"] = output_html
        output_html.write_text("ok")

    monkeypatch.setattr("weather_cli.cli.render_aggregate_report", fake_render)
    monkeypatch.setattr("weather_cli.cli.get_cached_location_timeseries", lambda data_dir, name: pd.DataFrame())

    cli.report(name=("Gothenburg", "Oslo"), open_browser=False)

    assert called["names"] == ["Gothenburg", "Oslo"]
    assert called["weights"] == [0.5, 0.5]
    assert called["output_html"].name == "gothenburg-oslo.html"
    assert called["dfs_len"] == 2


def test_report_accepts_tuple_weights(tmp_path, monkeypatch):
    cli = Weather(workspace=tmp_path)

    called = {}

    def fake_render(dfs, names, weights, output_html, auto_open=True):
        called["names"] = names
        called["weights"] = weights
        called["output_html"] = output_html
        output_html.write_text("ok")

    monkeypatch.setattr("weather_cli.cli.render_aggregate_report", fake_render)
    monkeypatch.setattr("weather_cli.cli.get_cached_location_timeseries", lambda data_dir, name: pd.DataFrame())

    cli.report(name=("A", "B"), weights=("2", "1"), open_browser=False)

    assert called["names"] == ["A", "B"]
    assert called["weights"] == [pytest.approx(2 / 3), pytest.approx(1 / 3)]
    assert called["output_html"].name == "a-b.html"