import sqlite3

from weather_cli import process_data
from weather_cli.list import list_downloads, _parse_filter


def test_parse_filter_country_equality():
    result = _parse_filter("country=SE")
    assert result == "country = 'SE'"


def test_parse_filter_numeric_comparison():
    result = _parse_filter("lat > 60")
    assert result == "latitude > 60"
    
    result = _parse_filter("lon < 12")
    assert result == "longitude < 12"


def test_parse_filter_combined_and():
    result = _parse_filter("country=SE and lat > 60")
    assert "country = 'SE'" in result
    assert "AND" in result
    assert "latitude > 60" in result


def test_parse_filter_combined_or():
    result = _parse_filter("country=SE or country=NO")
    assert "country = 'SE'" in result
    assert "OR" in result
    assert "country = 'NO'" in result


def test_parse_filter_contains():
    result = _parse_filter("name contains Stockholm")
    assert "name LIKE '%Stockholm%'" in result


def test_parse_filter_empty():
    result = _parse_filter("")
    assert result == ""
    
    result = _parse_filter(None)
    assert result == ""


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
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg", "SE", 57.7000, 11.9000),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("oslo", "Oslo", "NO", 59.9139, 10.7522),
        )
        conn.commit()

    items = list_downloads(data_dir)
    captured = capsys.readouterr().out.splitlines()

    assert len(items) == 2
    # Filter out empty lines
    non_empty = [line for line in captured if line.strip()]
    header = non_empty[0].strip()
    assert header.startswith("Name") and "Country" in header and "Local Path" not in header

    body = "\n".join(captured)
    assert "Gothenburg" in body and "SE" in body and "57.7000" in body and "11.9000" in body
    assert "Oslo" in body and "NO" in body and "59.9139" in body and "10.7522" in body

    # Results are sorted by country, then name
    assert set(items) == {
        ("Gothenburg", "SE", "57.7000", "11.9000"),
        ("Oslo", "NO", "59.9139", "10.7522"),
    }


def test_list_downloads_prefers_db_metadata(tmp_path, capsys):
    data_dir = tmp_path

    db_path = data_dir / "weather.sqlite"
    with sqlite3.connect(db_path) as conn:
        process_data._ensure_table(conn)
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg Display", "SE", "2024-01-01T00:00:00", 57.7089, 11.9746),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg Display", "SE", 57.7089, 11.9746),
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
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("gothenburg_SE_57.70_11.97", None, "SE", 57.7089, 11.9746),
        )
        conn.commit()

    list_downloads(data_dir)
    body = capsys.readouterr().out

    assert "Gothenburg" in body  # humanized from filename
    assert "gothenburg_SE_57.70_11.97" not in body


def test_list_downloads_with_country_filter(tmp_path, capsys):
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
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("stockholm", "Stockholm", "SE", "2024-01-01T00:00:00", 59.3293, 18.0686),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg", "SE", 57.7000, 11.9000),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("oslo", "Oslo", "NO", 59.9139, 10.7522),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("stockholm", "Stockholm", "SE", 59.3293, 18.0686),
        )
        conn.commit()

    items = list_downloads(data_dir, filter_str="country=SE")
    captured = capsys.readouterr().out

    assert len(items) == 2
    assert ("Gothenburg", "SE", "57.7000", "11.9000") in items
    assert ("Stockholm", "SE", "59.3293", "18.0686") in items
    assert "Oslo" not in captured


def test_list_downloads_with_latitude_filter(tmp_path, capsys):
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
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("stockholm", "Stockholm", "SE", "2024-01-01T00:00:00", 59.3293, 18.0686),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg", "SE", 57.7000, 11.9000),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("oslo", "Oslo", "NO", 59.9139, 10.7522),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("stockholm", "Stockholm", "SE", 59.3293, 18.0686),
        )
        conn.commit()

    items = list_downloads(data_dir, filter_str="lat > 59")
    captured = capsys.readouterr().out

    assert len(items) == 2
    assert ("Oslo", "NO", "59.9139", "10.7522") in items
    assert ("Stockholm", "SE", "59.3293", "18.0686") in items
    assert "Gothenburg" not in captured


def test_list_downloads_with_combined_filter(tmp_path, capsys):
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
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("stockholm", "Stockholm", "SE", "2024-01-01T00:00:00", 59.3293, 18.0686),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg", "SE", 57.7000, 11.9000),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("oslo", "Oslo", "NO", 59.9139, 10.7522),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("stockholm", "Stockholm", "SE", 59.3293, 18.0686),
        )
        conn.commit()

    items = list_downloads(data_dir, filter_str="country=SE and lat > 58")
    captured = capsys.readouterr().out

    assert len(items) == 1
    assert ("Stockholm", "SE", "59.3293", "18.0686") in items
    assert "Gothenburg" not in captured
    assert "Oslo" not in captured


def test_list_downloads_with_name_contains_filter(tmp_path, capsys):
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
            ("stockholm", "Stockholm", "SE", "2024-01-01T00:00:00", 59.3293, 18.0686),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg", "SE", 57.7000, 11.9000),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("stockholm", "Stockholm", "SE", 59.3293, 18.0686),
        )
        conn.commit()

    items = list_downloads(data_dir, filter_str="name contains holm")
    captured = capsys.readouterr().out

    assert len(items) == 1
    assert ("Stockholm", "SE", "59.3293", "18.0686") in items
    assert "Gothenburg" not in captured


def test_list_downloads_no_match_returns_empty(tmp_path, capsys):
    data_dir = tmp_path
    db_path = data_dir / "weather.sqlite"
    with sqlite3.connect(db_path) as conn:
        process_data._ensure_table(conn)
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg", "SE", "2024-01-01T00:00:00", 57.7000, 11.9000),
        )
        conn.commit()

    items = list_downloads(data_dir, filter_str="country=NO")
    captured = capsys.readouterr().out

    assert len(items) == 0
    assert "No cached datasets match the filter" in captured

