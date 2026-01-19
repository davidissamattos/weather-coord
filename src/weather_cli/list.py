"""Listing helpers for cached ERA5-Land point datasets."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .process_data import _db_path


def _format_table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def fmt(row: list[str]) -> str:
        return " | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))

    header_line = fmt(headers)
    separator = "-+-".join("-" * w for w in widths)
    body = [fmt(row) for row in rows]
    return "\n".join([header_line, separator, *body])


def _friendly_name(filename: str, name: str | None) -> str:
    if name and name.strip() and name.strip().lower() != filename.strip().lower():
        return name
    base = filename.split("_")[0] if "_" in filename else filename
    human = base.replace("-", " ").strip()
    return human.title() if human else filename


def _list_cached_locations(data_dir: Path) -> list[tuple[str, str, str, str]]:
    db = _db_path(data_dir)
    if not db.exists():
        return []

    with sqlite3.connect(db) as conn:
        try:
            rows = conn.execute(
                """
                SELECT
                    filename,
                    name,
                    COALESCE(country, '-') AS country,
                    MIN(latitude) AS latitude,
                    MIN(longitude) AS longitude
                FROM weather
                GROUP BY filename, country
                ORDER BY COALESCE(name, filename)
                """
            ).fetchall()
        except sqlite3.Error:
            return []

    def _fmt_coord(value: float | None) -> str:
        if value is None:
            return "-"
        try:
            return f"{float(value):.4f}"
        except (TypeError, ValueError):
            return "-"

    results = []
    for filename, name, country, lat, lon in rows:
        display = _friendly_name(filename, name)
        results.append((display, country or "-", _fmt_coord(lat), _fmt_coord(lon)))
    return results


def list_downloads(data_dir: Path) -> list[tuple[str, str, str, str]]:
    """Return and print cached datasets as a CLI table."""
    items = _list_cached_locations(data_dir)
    if not items:
        print("No cached datasets found. Run 'weather refresh-database' after downloading data.")
        return []

    rows: list[list[str]] = []
    for name, country, lat, lon in items:
        rows.append([name, country, lat, lon])

    table = _format_table(rows, headers=["Name", "Country", "Lat", "Lon"])
    print(table)
    return items
