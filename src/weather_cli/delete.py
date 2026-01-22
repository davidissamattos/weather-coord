"""Delete utilities for removing locations from cache and filesystem."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .download import slugify
from .process_data import _db_path, _resolve_cache_key


def delete_location(data_dir: Path, name: str) -> None:
    """Delete a location from both database tables and filesystem.
    
    Args:
        data_dir: Data directory containing the cache
        name: Name of the location to delete
    """
    # Resolve the cache key to get the filename
    filename = _resolve_cache_key(data_dir, name)
    
    # If not in cache, try using the slug directly
    if filename is None:
        filename = slugify(name)
    
    db = _db_path(data_dir)
    deleted_files = 0
    weather_count = 0
    location_count = 0
    
    # Delete from database if it exists
    if db.exists():
        with sqlite3.connect(db) as conn:
            # Get location metadata before deleting
            try:
                location_info = conn.execute(
                    "SELECT name, country FROM locations WHERE filename = ?",
                    (filename,)
                ).fetchone()
            except sqlite3.Error:
                location_info = None
            
            # Delete from both tables
            try:
                weather_count = conn.execute(
                    "DELETE FROM weather WHERE filename = ?",
                    (filename,)
                ).rowcount
                
                location_count = conn.execute(
                    "DELETE FROM locations WHERE filename = ?",
                    (filename,)
                ).rowcount
                
                conn.commit()
            except sqlite3.Error:
                pass
            
            if weather_count > 0 or location_count > 0:
                display_name = location_info[0] if location_info and location_info[0] else filename
                country = location_info[1] if location_info and location_info[1] else "Unknown"
                print(f"Deleted '{display_name}' ({country}) from database ({weather_count} records)")
    
    # Delete file(s) from filesystem
    # Try both with and without coordinates in filename
    patterns = [
        f"{filename}.zip",
        f"{filename}.csv",
        f"{filename}_*.zip",
        f"{filename}_*.csv",
    ]
    
    for pattern in patterns:
        for file_path in data_dir.glob(pattern):
            file_path.unlink()
            print(f"Deleted file: {file_path.name}")
            deleted_files += 1
    
    if deleted_files == 0 and weather_count == 0 and location_count == 0:
        print(f"Location '{name}' was not found.")
