"""Bulk-download ERA5 datasets from a CSV list of cities.

CSV columns required (header names are case-insensitive and trimmed):
    name,country,lat,lon

Example:
    python bulk_download.py --csv ../Downloads/top_cities_combined.csv --max-workers 5
"""
from __future__ import annotations

import argparse
import csv
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        if reader.fieldnames is None:
            raise SystemExit("CSV is missing a header row.")

        # Normalize headers
        header_map = {name.strip().lower(): name for name in reader.fieldnames}
        required = {"name", "country", "lat", "lon"}
        if not required.issubset(header_map):
            missing = required - set(header_map)
            raise SystemExit(f"CSV missing required columns: {', '.join(sorted(missing))}")

        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({key: row[header_map[key]].strip() for key in required})
        return rows


def _build_command(entry: dict[str, str]) -> list[str]:
    return [
        "weather",
        "download",
        "--name",
        entry["name"],
        "--country",
        entry["country"],
        "--lat",
        entry["lat"],
        "--lon",
        entry["lon"],
    ]


def _run_command(cmd: Iterable[str]) -> tuple[list[str], int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return list(cmd), proc.returncode, proc.stdout, proc.stderr


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk download ERA5 data from a CSV list of cities.")
    parser.add_argument("--csv", required=True, type=Path, help="Path to CSV with name,country,lat,lon columns")
    parser.add_argument("--max-workers", type=int, default=5, help="Maximum parallel downloads (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    args = parser.parse_args()

    rows = _read_rows(args.csv)
    if not rows:
        print("No rows found in CSV; nothing to do.")
        return

    commands = [_build_command(row) for row in rows]

    if args.dry_run:
        for cmd in commands:
            print("DRY RUN:", " ".join(cmd))
        return

    print(f"Starting downloads for {len(commands)} cities with up to {args.max_workers} workers...")
    results: list[tuple[list[str], int, str, str]] = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_map = {executor.submit(_run_command, cmd): cmd for cmd in commands}
        for future in as_completed(future_map):
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover - safety net for unexpected errors
                cmd = future_map[future]
                print(f"Command {' '.join(cmd)} failed with exception: {exc}")

    failures = [(cmd, code, out, err) for cmd, code, out, err in results if code != 0]
    if failures:
        print(f"Completed with {len(failures)} failure(s):")
        for cmd, code, out, err in failures:
            print("-", " ".join(cmd))
            print("  exit code:", code)
            if out:
                print("  stdout:", out.strip())
            if err:
                print("  stderr:", err.strip())
    else:
        print("All downloads finished successfully.")


if __name__ == "__main__":
    main()
