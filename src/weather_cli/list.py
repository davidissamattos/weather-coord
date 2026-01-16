"""Listing helpers for downloaded ERA5-Land point datasets."""
from __future__ import annotations

from pathlib import Path

from .process_data import list_downloaded_locations


def list_downloads(data_dir: Path) -> list[tuple[str, Path]]:
    """Return and print downloaded dataset names and file names (with lat/lon slug)."""
    items = list_downloaded_locations(data_dir)
    if not items:
        print("No datasets downloaded yet.")
        return items

    for name, path in items:
        print(f"{name} -> {path.name}")
    return items
