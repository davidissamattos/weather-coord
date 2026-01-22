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

    processed = 0
    skipped = 0
    for name_slug, path in datasets:
        result = cache_location_timeseries(data_dir, name_slug, dataset_path=path)
        if result is not None:
            processed += 1
        else:
            skipped += 1
    
    print(f"Refreshed database at {db}")
    print(f"Processed: {processed}, Skipped (invalid/empty): {skipped}")
