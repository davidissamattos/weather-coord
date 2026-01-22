"""Tests for delete functionality."""
import sqlite3
from pathlib import Path

import pytest

from weather_cli import process_data
from weather_cli.delete import delete_location


def test_delete_location_removes_from_database(tmp_path):
    """Test that delete removes entries from both database tables."""
    data_dir = tmp_path
    db_path = data_dir / "weather.sqlite"
    
    # Setup database with test data
    with sqlite3.connect(db_path) as conn:
        process_data._ensure_table(conn)
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg", "SE", "2024-01-01T00:00:00", 57.7000, 11.9000),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg", "SE", 57.7000, 11.9000),
        )
        conn.commit()
    
    # Verify data exists
    with sqlite3.connect(db_path) as conn:
        weather_count = conn.execute("SELECT COUNT(*) FROM weather WHERE filename = ?", ("gothenburg",)).fetchone()[0]
        location_count = conn.execute("SELECT COUNT(*) FROM locations WHERE filename = ?", ("gothenburg",)).fetchone()[0]
        assert weather_count == 1
        assert location_count == 1
    
    # Delete location
    delete_location(data_dir, "Gothenburg")
    
    # Verify data is removed
    with sqlite3.connect(db_path) as conn:
        weather_count = conn.execute("SELECT COUNT(*) FROM weather WHERE filename = ?", ("gothenburg",)).fetchone()[0]
        location_count = conn.execute("SELECT COUNT(*) FROM locations WHERE filename = ?", ("gothenburg",)).fetchone()[0]
        assert weather_count == 0
        assert location_count == 0


def test_delete_location_removes_files(tmp_path):
    """Test that delete removes downloaded files from filesystem."""
    data_dir = tmp_path
    db_path = data_dir / "weather.sqlite"
    
    # Setup database
    with sqlite3.connect(db_path) as conn:
        process_data._ensure_table(conn)
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("gothenburg", "Gothenburg", "SE", 57.7000, 11.9000),
        )
        conn.commit()
    
    # Create test files
    file1 = data_dir / "gothenburg.zip"
    file2 = data_dir / "gothenburg_SE_57.70_11.97.zip"
    file1.write_text("dummy data")
    file2.write_text("dummy data")
    
    assert file1.exists()
    assert file2.exists()
    
    # Delete location
    delete_location(data_dir, "Gothenburg")
    
    # Verify files are removed
    assert not file1.exists()
    assert not file2.exists()


def test_delete_nonexistent_location(tmp_path, capsys):
    """Test that deleting non-existent location doesn't crash."""
    data_dir = tmp_path
    db_path = data_dir / "weather.sqlite"
    
    with sqlite3.connect(db_path) as conn:
        process_data._ensure_table(conn)
    
    delete_location(data_dir, "NonExistent")
    
    captured = capsys.readouterr()
    assert "not found" in captured.out.lower()


def test_delete_location_by_display_name(tmp_path):
    """Test that delete works with display name lookup."""
    data_dir = tmp_path
    db_path = data_dir / "weather.sqlite"
    
    # Setup with different filename and display name
    with sqlite3.connect(db_path) as conn:
        process_data._ensure_table(conn)
        conn.execute(
            "INSERT INTO weather (filename, name, country, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("gothenburg_SE_57.70_11.97", "Gothenburg Display", "SE", "2024-01-01T00:00:00", 57.7000, 11.9000),
        )
        conn.execute(
            "INSERT INTO locations (filename, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("gothenburg_SE_57.70_11.97", "Gothenburg Display", "SE", 57.7000, 11.9000),
        )
        conn.commit()
    
    # Delete by display name
    delete_location(data_dir, "Gothenburg Display")
    
    # Verify deletion
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM locations WHERE filename = ?", ("gothenburg_SE_57.70_11.97",)).fetchone()[0]
        assert count == 0
