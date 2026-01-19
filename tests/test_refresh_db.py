from pathlib import Path
import sqlite3

import weather_cli.process_data as proc
from weather_cli.refresh_db import refresh_database


def _make_mock_zip(path: Path) -> None:
    import zipfile

    content = (
        "valid_time,latitude,longitude,t2m,d2m,tp,ssrd,strd,snowc,u10,v10\n"
        "2000-01-01T00:00:00,57.7,11.97,300.15,280.15,0.1,1.0,2.0,0.0,3.0,4.0\n"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("data.csv", content)


def test_refresh_database_rebuilds_cache(tmp_path):
    data_dir = tmp_path
    target1 = data_dir / "a_US_0.0000_0.0000.zip"
    target1.parent.mkdir(parents=True, exist_ok=True)
    _make_mock_zip(target1)

    target2 = data_dir / "b_US_1.0000_1.0000.zip"
    _make_mock_zip(target2)

    refresh_database(data_dir)

    db_path = data_dir / proc.DB_FILENAME
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT COUNT(DISTINCT name) FROM weather").fetchone()[0]
        assert rows == 2
        countries = conn.execute("SELECT DISTINCT country FROM weather ORDER BY country").fetchall()
        assert [row[0] for row in countries] == ["US"]
