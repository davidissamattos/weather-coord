import sqlite3

from weather_cli import process_data
from weather_cli.list import list_downloads


def test_list_downloads_outputs_and_returns(tmp_path, capsys):
    data_dir = tmp_path
    db_path = data_dir / "weather.sqlite"
    with sqlite3.connect(db_path) as conn:
        process_data._ensure_table(conn)
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg", "SE", "2024-01-01T00:00:00", 57.7000, 11.9000),
        )
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("oslo", "Oslo", "NO", "2024-01-01T00:00:00", 59.9139, 10.7522),
        )
        conn.commit()

    items = list_downloads(data_dir)
    captured = capsys.readouterr().out.splitlines()

    assert len(items) == 2
    header = captured[0].strip()
    assert header.startswith("Name") and "Country" in header and "Local Path" not in header

    body = "\n".join(captured)
    assert "Gothenburg" in body and "SE" in body and "57.7000" in body and "11.9000" in body
    assert "Oslo" in body and "NO" in body and "59.9139" in body and "10.7522" in body

    assert items == [
        ("Gothenburg", "SE", "57.7000", "11.9000"),
        ("Oslo", "NO", "59.9139", "10.7522"),
    ]


def test_list_downloads_prefers_db_metadata(tmp_path, capsys):
    data_dir = tmp_path

    db_path = data_dir / "weather.sqlite"
    with sqlite3.connect(db_path) as conn:
        process_data._ensure_table(conn)
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg Display", "SE", "2024-01-01T00:00:00", 57.7089, 11.9746),
        )
        conn.commit()

    list_downloads(data_dir)
    body = capsys.readouterr().out

    assert "Gothenburg Display" in body
    assert "SE" in body  # pulled from DB, not filename
    assert "57.7089" in body
    assert "11.9746" in body


def test_list_downloads_humanizes_filename_when_name_missing(tmp_path, capsys):
    data_dir = tmp_path

    db_path = data_dir / "weather.sqlite"
    with sqlite3.connect(db_path) as conn:
        process_data._ensure_table(conn)
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("gothenburg_SE_57.70_11.97", None, "SE", "2024-01-01T00:00:00", 57.7089, 11.9746),
        )
        conn.commit()

    list_downloads(data_dir)
    body = capsys.readouterr().out

    assert "Gothenburg" in body  # humanized from filename
    assert "gothenburg_SE_57.70_11.97" not in body
