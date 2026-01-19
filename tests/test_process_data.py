from pathlib import Path

import pytest
import sqlite3

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

    df = proc.cache_location_timeseries(data_dir, name="city", dataset_path=target)
    expected_cols = set(proc.CANONICAL_COLUMNS.keys()) | {
        "latitude",
        "longitude",
        "country",
        "rh_perc",
        "heat_index_c",
        "heat_index_classification",
        "windspeed_ms",
    }
    assert expected_cols == set(df.columns)
    assert df.index.name == "timestamp"
    assert df.loc[df.index[0], "temperature_c"] == pytest.approx(27.0, rel=1e-3)
    assert df.loc[df.index[0], "dewpoint_c"] == pytest.approx(7.0, rel=1e-3)
    assert df.loc[df.index[0], "windspeed_ms"] == pytest.approx(5.0, rel=1e-6)
    assert df.loc[df.index[0], "rh_perc"] == pytest.approx(28.1, rel=1e-2)
    assert df.loc[df.index[0], "heat_index_c"] > 0
    assert df.loc[df.index[0], "heat_index_classification"] in {
        "Normal",
        "Caution",
        "Extreme Caution",
        "Danger",
        "Extreme Danger",
    }


def test_cached_lookup_accepts_friendly_name(tmp_path):
    data_dir = tmp_path
    target = data_dir / "gothenburg_SE_57.70_11.97.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    _make_mock_zip(target)

    proc.cache_location_timeseries(data_dir, name=target.stem, dataset_path=target)

    df = proc.get_cached_location_timeseries(data_dir, name="gothenburg")
    assert not df.empty


def test_load_location_timeseries_fixture_contains_all_variables():
    target = Path("tests/data/gothenburg_SE_57.70_11.97.zip")
    df = proc.cache_location_timeseries(target.parent, name="gothenburg", dataset_path=target)

    expected_cols = set(proc.CANONICAL_COLUMNS.keys()) | {
        "latitude",
        "longitude",
        "rh_perc",
        "heat_index_c",
        "heat_index_classification",
        "windspeed_ms",
    }

    assert expected_cols.issubset(set(df.columns))
    assert df.index.name == "timestamp"
    assert not df.empty


def test_compute_heat_index_and_classification():
    hi = proc.compute_hi_f(20.0, 50.0)
    assert hi == pytest.approx(67.4, rel=1e-3)
    hi_c = (hi - 32.0) / 1.8
    assert hi_c == pytest.approx(19.6667, rel=1e-3)

    assert proc._classify_heat_index(75) == "Normal"
    assert proc._classify_heat_index(85) == "Caution"
    assert proc._classify_heat_index(95) == "Extreme Caution"
    assert proc._classify_heat_index(110) == "Danger"
    assert proc._classify_heat_index(130) == "Extreme Danger"


def test_load_uses_cache_after_first_read(tmp_path, monkeypatch):
    data_dir = tmp_path
    target = data_dir / "city_US_0.0000_0.0000.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    _make_mock_zip(target)

    # First load processes and caches
    df1 = proc.cache_location_timeseries(data_dir, name="city", dataset_path=target)
    assert not df1.empty
    db_path = data_dir / proc.DB_FILENAME
    assert db_path.exists()

    # Second load should hit cache; make archive unreadable to ensure cache is used
    def boom(_path):
        raise AssertionError("Should not read archive when cache exists")

    monkeypatch.setattr(proc, "_read_csv_archive", boom)
    df2 = proc.get_cached_location_timeseries(data_dir, name="city")
    assert not df2.empty
    assert set(df1.columns) == set(df2.columns)


def test_refresh_database_rebuilds_cache(tmp_path):
    data_dir = tmp_path
    # create two datasets
    target1 = data_dir / "a_US_0.0000_0.0000.zip"
    target1.parent.mkdir(parents=True, exist_ok=True)
    _make_mock_zip(target1)

    target2 = data_dir / "b_US_1.0000_1.0000.zip"
    _make_mock_zip(target2)
