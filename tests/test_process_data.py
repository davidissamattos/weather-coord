from pathlib import Path

import pytest

import weather_cli.process_data as proc


def _make_mock_zip(path: Path) -> None:
    import zipfile

    content = (
        "valid_time,latitude,longitude,t2m,d2m,tp,ssrd,strd,snowc,u10,v10\n"
        "2000-01-01T00:00:00,57.7,11.97,300.15,280.15,0.1,1.0,2.0,0.0,3.0,4.0\n"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("data.csv", content)


def test_validate_coordinates_accepts_numbers():
    proc.validate_coordinates(0, 0)
    proc.validate_coordinates("45.0", "-90")


def test_validate_coordinates_rejects_out_of_range():
    with pytest.raises(SystemExit):
        proc.validate_coordinates(100, 0)
    with pytest.raises(SystemExit):
        proc.validate_coordinates(0, 400)


def test_list_downloaded_locations_returns_sorted(tmp_path):
    data_dir = tmp_path
    (data_dir / "b.zip").write_text("b")
    (data_dir / "a.zip").write_text("a")
    items = proc.list_downloaded_locations(data_dir)
    assert [name for name, _ in items] == ["a", "b"]


def test_load_location_timeseries_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        proc.load_location_timeseries(tmp_path, name="missing")


def test_load_location_timeseries_with_mock(tmp_path):
    data_dir = tmp_path
    target = data_dir / "city_0.0000_0.0000.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    _make_mock_zip(target)

    df = proc.load_location_timeseries(data_dir, name="city", dataset_path=target)
    expected_cols = set(proc.CANONICAL_COLUMNS.keys()) | {"latitude", "longitude", "rh_perc", "windspeed_ms"}
    assert expected_cols == set(df.columns)
    assert df.index.name == "timestamp"
    assert df.loc[df.index[0], "temperature_c"] == pytest.approx(27.0, rel=1e-3)
    assert df.loc[df.index[0], "dewpoint_c"] == pytest.approx(7.0, rel=1e-3)
    assert df.loc[df.index[0], "windspeed_ms"] == pytest.approx(5.0, rel=1e-6)
    assert df.loc[df.index[0], "rh_perc"] == pytest.approx(28.1, rel=1e-2)


def test_load_location_timeseries_fixture_contains_all_variables():
    target = Path("tests/data/gothenburg_57.7000_11.9700.zip")
    df = proc.load_location_timeseries(target.parent, name="gothenburg", dataset_path=target)

    expected_cols = set(proc.CANONICAL_COLUMNS.keys()) | {"latitude", "longitude", "rh_perc", "windspeed_ms"}

    assert expected_cols.issubset(set(df.columns))
    assert df.index.name == "timestamp"
    assert not df.empty
