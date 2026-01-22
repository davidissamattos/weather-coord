"""
CLI wiring for the weather ERA5 tool.

Business logic lives in download.py, process_data.py, and report.py; this module only handles argument parsing and orchestration.
"""
from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
from collections.abc import Sequence
from pathlib import Path
from itertools import cycle

import fire

from .download import DATA_FOLDER_NAME, bulk_download_from_csv, download_single_location, download_timeseries, slugify
from .report_aggregate import render_aggregate_report
from .list import list_downloads
from .process_data import get_cached_location_timeseries
from .refresh_db import refresh_database
from .report import render_report
from .delete import delete_location

__all__ = ["Weather", "main"]


@contextmanager
def _spinner(message: str, interval: float = 0.1):
    """Display a lightweight rotating spinner while work is running."""
    stream = sys.stdout
    stop_event = threading.Event()
    spinner = cycle("|/-\\")

    def spin() -> None:
        while not stop_event.is_set():
            stream.write(f"\r{message} {next(spinner)}")
            stream.flush()
            time.sleep(interval)

    thread = threading.Thread(target=spin, daemon=True)
    stream.write(f"{message} ")
    stream.flush()
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join()
        stream.write("\r" + " " * (len(message) + 2) + "\r")
        stream.flush()
        print(f"{message} done.")


class Weather:
    def __init__(self, workspace: Path | None = None) -> None:
        # default to the user's home directory for cache unless overridden
        self.workspace = Path(workspace) if workspace else Path.home()
        self.data_dir = self.workspace / DATA_FOLDER_NAME
        self.data_dir.mkdir(exist_ok=True)

    def configure(self, token: str, url: str = "https://cds.climate.copernicus.eu/api") -> None:
        """
        Write the CDS/ADS API token to the user's home directory (.cdsapirc).

        Example: weather configure --token my_token
        For ADS users, pass the ADS URL via --url.
        """

        token = token.strip()
        if not token:
            raise SystemExit("Token cannot be empty.")

        target = Path.home() / ".cdsapirc"
        content = f"url: {url}\nkey: {token}\n"
        target.write_text(content, encoding="utf-8")
        try:
            target.chmod(0o600)
        except (OSError, NotImplementedError):
            pass

        print(f"Wrote CDS/ADS token to {target}")

    def download(
        self,
        name: str,
        lat: float | None = None,
        lon: float | None = None,
        country: str | None = None,
        find_city: str | None = None,
        find_country: str | None = None,
        bulk: bool = False,
        csv: str | None = None,
        max_workers: int = 5,
        dry_run: bool = False,
    ) -> None:
        """
        Download ERA5-Land time-series (2016-2025) for a single point with fixed variables.

        Examples:
            - Manual coordinates + country: weather download --name Gothenburg --country Sweden --lat 57.7 --lon 11.97
            - Coordinates only (reverse geocode country): weather download --name Gothenburg --lat 57.7 --lon 11.97
            - Fully geocoded: weather download --name Gothenburg --find-city Gothenburg --find-country Sweden
            - Bulk from CSV: weather download --bulk --csv ./cities.csv --max-workers 5
        """

        if bulk:
            if not csv:
                raise SystemExit("--csv is required when using --bulk")
            csv_path = Path(csv)
            with _spinner("Downloading bulk data..."):
                bulk_download_from_csv(self.data_dir, csv_path, max_workers=max_workers, dry_run=dry_run)
            return
        with _spinner("Downloading data..."):
            download_single_location(
                data_dir=self.data_dir,
                name=name,
                lat=lat,
                lon=lon,
                country=country,
                find_city=find_city,
                find_country=find_country,
            )

    def save(
        self,
        name: str,
        output: str | None = None,
    ) -> None:
        """
        Save the downloaded time-series for a named location to CSV.

        Example: weather save --name Gothenburg --output ./gothenburg.csv
        """
        with _spinner("Saving the data to csv..."):
            df = get_cached_location_timeseries(self.data_dir, name=name)
            out_path = Path(output) if output else self.data_dir / f"{slugify(name)}.csv"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(out_path, index=True, index_label="timestamp")
        print(f"Saved data to {out_path}")

    def report(
        self,
        name: str | Sequence[str],
        open_browser: bool = True,
        weights: str | Sequence[str] | None = None,
    ) -> None:
        """
        Generate HTML report (plots + summary) for one or more named locations.
        """
        with _spinner("Generating report..."):
            def _parse_items(raw: str | Sequence[str] | None) -> list[str]:
                if raw is None:
                    return []
                if isinstance(raw, str):
                    return [part.strip() for part in raw.split(",") if part.strip()]
                parts: list[str] = []
                for item in raw:
                    parts.extend([part.strip() for part in str(item).split(",") if part.strip()])
                return parts

            names = _parse_items(name)
            if not names:
                raise SystemExit("At least one name must be provided.")

            parsed_weights = _parse_items(weights)
            if len(names) > 1 or parsed_weights:
                if parsed_weights and len(parsed_weights) != len(names):
                    raise SystemExit("Weights count must match number of cities.")
                if not parsed_weights:
                    weight_vals = [1.0] * len(names)
                else:
                    weight_vals = [float(w) for w in parsed_weights]
                total = sum(weight_vals)
                if not total:
                    raise SystemExit("Weights must sum to a positive value.")
                weight_vals = [w / total for w in weight_vals]

                agg_slug = slugify("-".join(names))
                plot_path = self.data_dir / f"{agg_slug}.html"
                dfs = [get_cached_location_timeseries(self.data_dir, name=n) for n in names]
                render_aggregate_report(dfs, names, weight_vals, output_html=plot_path, auto_open=open_browser)
                print(f"Saved aggregated plot to {plot_path}")
                return

            df = get_cached_location_timeseries(self.data_dir, name=names[0])
            plot_path = self.data_dir / f"{slugify(names[0])}.html"
            render_report(df, name=names[0], output_html=plot_path, auto_open=open_browser)
            print(f"Saved plot to {plot_path}")

    def list(self, filter: str | None = None) -> None:
        """List downloaded locations.
        
        Args:
            filter: Optional filter expression (e.g., "country=SE and lat > 60")
        """
        with _spinner("Getting available data..."):
            list_downloads(self.data_dir, filter_str=filter)

    def refresh_database(self) -> None:
        """Rebuild the sqlite cache from all downloaded datasets."""
        with _spinner("Refreshing database..."):
            refresh_database(self.data_dir)

    def delete(self, name: str) -> None:
        """Delete a location from cache and filesystem.
        
        Args:
            name: Name of the location to delete
            
        Example: weather delete --name Gothenburg
        """
        delete_location(self.data_dir, name)

    def _dataset_path(self, name: str, country_code: str, lat: float, lon: float) -> Path:
        """Internal helper kept for test compatibility."""
        return self.data_dir / f"{slugify(name)}_{country_code}_{lat:.2f}_{lon:.2f}.zip"


def main(argv: Sequence[str] | None = None) -> None:
    """Entrypoint used by the console script."""
    command = list(argv) if argv is not None else sys.argv[1:]
    fire.Fire(Weather, command=command)


if __name__ == "__main__":
    main()
