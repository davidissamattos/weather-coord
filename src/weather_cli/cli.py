"""
CLI wiring for the weather ERA5 tool.

Business logic lives in download.py, process_data.py, and report.py; this module only handles argument parsing and orchestration.
"""
from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import fire

from .download import DATA_FOLDER_NAME, download_timeseries, slugify
from .list import list_downloads
from .process_data import load_location_timeseries, validate_coordinates
from .report import render_report

__all__ = ["Weather", "main"]


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

    def _dataset_path(self, name: str, lat: float, lon: float) -> Path:
        return self.data_dir / f"{slugify(name)}_{lat:.4f}_{lon:.4f}.zip"

    def download(
        self,
        name: str,
        lat: float,
        lon: float,
    ) -> None:
        """
        Download ERA5-Land time-series (2016-2025) for a single point with fixed variables.

        Example: weather download --name Gothenburg --lat 57.7 --lon 11.9
        """

        validate_coordinates(lat, lon)
        ds_path = self._dataset_path(name, lat, lon)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if ds_path.exists():
            print(f"Skipping {name}: already present at {ds_path}")
            return
        download_timeseries(ds_path, lat=lat, lon=lon)
        print("Download complete.")

    def save(
        self,
        name: str,
        output: str | None = None,
    ) -> None:
        """
        Save the downloaded time-series for a named location to CSV.

        Example: weather save --name Gothenburg --output ./gothenburg.csv
        """

        df = load_location_timeseries(self.data_dir, name=name)

        out_path = Path(output) if output else self.data_dir / f"{slugify(name)}.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=True, index_label="timestamp")
        print(f"Saved data to {out_path}")

    def report(
        self,
        name: str,
        open_browser: bool = True,
    ) -> None:
        """
        Generate HTML report (plots + summary) for a named location.
        """

        df = load_location_timeseries(self.data_dir, name=name)
        plot_path = self.data_dir / f"{slugify(name)}.html"
        render_report(df, name=name, output_html=plot_path, auto_open=open_browser)
        print(f"Saved plot to {plot_path}")

    def list(self) -> None:
        """List downloaded locations."""
        list_downloads(self.data_dir)


def main(argv: Sequence[str] | None = None) -> None:
    """Entrypoint used by the console script."""
    command = list(argv) if argv is not None else sys.argv[1:]
    fire.Fire(Weather, command=command)


if __name__ == "__main__":
    main()
