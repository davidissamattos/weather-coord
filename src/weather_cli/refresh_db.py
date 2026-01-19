"""Database refresh utilities for cached weather data."""
from __future__ import annotations

from pathlib import Path

from .process_data import _db_path, cache_location_timeseries, list_downloaded_locations


def refresh_database(data_dir: Path) -> None:
    """Rebuild the sqlite cache from all downloaded datasets."""
    db = _db_path(data_dir)
    if db.exists():
        db.unlink()

    datasets = list_downloaded_locations(data_dir)
    if not datasets:
        print("No datasets found to refresh.")
        return

    for name_slug, path in datasets:
        cache_location_timeseries(data_dir, name_slug, dataset_path=path)
    print(f"Refreshed database at {db}")
