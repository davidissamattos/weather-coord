"""Listing helpers for cached ERA5-Land point datasets."""
from __future__ import annotations

import re
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


def _parse_filter(filter_str: str) -> str:
    """Convert user-friendly filter to SQL WHERE clause.
    
    Supports:
    - country=SE
    - lat > 60
    - lon < 12
    - name contains Stockholm
    - and/or operators
    
    Returns SQL WHERE clause (without WHERE keyword).
    """
    if not filter_str or not filter_str.strip():
        return ""
    
    # Normalize spacing around operators
    normalized = filter_str.strip()
    
    # Map field names to SQL columns (use aggregated values from GROUP BY)
    field_map = {
        "name": "name",
        "country": "country",
        "lat": "latitude",
        "latitude": "latitude",
        "lon": "longitude",
        "longitude": "longitude",
    }
    
    # Replace 'contains' with LIKE
    def replace_contains(match):
        field = match.group(1).strip().lower()
        value = match.group(2).strip()
        if field not in field_map:
            raise ValueError(f"Unknown field: {field}")
        sql_field = field_map[field]
        # Remove quotes if present
        value = value.strip('"\"')
        return f"{sql_field} LIKE '%{value}%'"
    
    normalized = re.sub(r'(\w+)\s+contains\s+([\w"]+)', replace_contains, normalized, flags=re.IGNORECASE)
    
    # Replace field names with SQL columns
    def replace_field(match):
        field = match.group(1).lower()
        if field not in field_map:
            raise ValueError(f"Unknown field: {field}")
        return field_map[field]
    
    # Replace comparison operators
    normalized = re.sub(r'\b(name|country|lat|latitude|lon|longitude)\b', replace_field, normalized, flags=re.IGNORECASE)
    
    # Replace logical operators
    normalized = re.sub(r'\band\b', 'AND', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\bor\b', 'OR', normalized, flags=re.IGNORECASE)
    
    # Add quotes around string values for = operator (country=SE -> country='SE')
    def quote_string_values(match):
        field = match.group(1)
        op = match.group(2)
        value = match.group(3).strip()
        # If value is not a number and not already quoted, quote it
        if not value.replace('.', '', 1).replace('-', '', 1).isdigit() and not value.startswith("'"):
            value = f"'{value}'"
        return f"{field} {op} {value}"
    
    normalized = re.sub(r'(\w+)\s*(=|!=|<>)\s*([^\s\']+)', quote_string_values, normalized)
    
    return normalized


def _friendly_name(filename: str, name: str | None) -> str:
    if name and name.strip() and name.strip().lower() != filename.strip().lower():
        return name
    base = filename.split("_")[0] if "_" in filename else filename
    human = base.replace("-", " ").strip()
    return human.title() if human else filename


def _list_cached_locations(data_dir: Path, filter_str: str | None = None) -> list[tuple[str, str, str, str]]:
    db = _db_path(data_dir)
    if not db.exists():
        return []

    base_query = """
        SELECT
            filename,
            name,
            COALESCE(country, '-') AS country,
            latitude,
            longitude
        FROM locations
    """
    
    if filter_str:
        try:
            where_clause = _parse_filter(filter_str)
            if where_clause:
                base_query += f" WHERE {where_clause}"
        except (ValueError, sqlite3.Error) as exc:
            raise SystemExit(f"Invalid filter: {exc}") from exc
    
    base_query += " ORDER BY country, name ASC"

    with sqlite3.connect(db) as conn:
        try:
            rows = conn.execute(base_query).fetchall()
        except sqlite3.Error as exc:
            raise SystemExit(f"Filter query error: {exc}") from exc

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


def list_downloads(data_dir: Path, filter_str: str | None = None) -> list[tuple[str, str, str, str]]:
    """Return and print cached datasets as a CLI table."""
    items = _list_cached_locations(data_dir, filter_str=filter_str)
    if not items:
        if filter_str:
            print("No cached datasets match the filter.")
        else:
            print("No cached datasets found. Run 'weather refresh-database' after downloading data.")
        return []

    rows: list[list[str]] = []
    for name, country, lat, lon in items:
        rows.append([name, country, lat, lon])

    table = _format_table(rows, headers=["Name", "Country", "Lat", "Lon"])
    print(f"\n{table}")
    return items
