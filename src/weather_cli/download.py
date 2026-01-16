"""Download helpers for ERA5 land point time-series data."""
from __future__ import annotations

from pathlib import Path
from typing import List

try:
    import cdsapi
except ImportError:  # pragma: no cover - depends on runtime environment
    cdsapi = None

DATA_FOLDER_NAME = ".weather_era5"
VARIABLES: list[str] = [
    "2m_dewpoint_temperature",
    "2m_temperature",
    "total_precipitation",
    "surface_solar_radiation_downwards",
    "surface_thermal_radiation_downwards",
    "surface_pressure",
    "snow_cover",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
]
DATE_RANGE = "2016-01-01/2025-12-31"
DATASET = "reanalysis-era5-land-timeseries"


def slugify(value: str) -> str:
    """Convert a name to a filesystem-friendly slug."""
    return "-".join(value.strip().lower().split()) or "dataset"


def ensure_dependencies() -> None:
    missing: List[str] = []
    if cdsapi is None:
        missing.append("cdsapi")
    if missing:
        raise SystemExit(
            "Missing dependencies: "
            + ", ".join(missing)
            + "\nInstall with: pip install -r requirements.txt"
        )

def download_timeseries(dataset_path: Path, lat: float, lon: float) -> None:
    """Download 2016-2025 ERA5-Land time-series for a single point with fixed variables.

    CDS delivers CSV content inside a ZIP archive, so we coerce the output filename to `.zip`.
    """
    ensure_dependencies()
    target_path = dataset_path if dataset_path.suffix.lower() == ".zip" else dataset_path.with_suffix(".zip")

    client = cdsapi.Client()
    request_body = {
        "variable": VARIABLES,
        "location": {"longitude": float(lon), "latitude": float(lat)},
        "date": [DATE_RANGE],
        "data_format": "csv",
    }
    print(f"Requesting ERA5-Land time-series for lat={lat}, lon={lon} -> {target_path} ...")
    client.retrieve(DATASET, request_body, str(target_path))
    print(f"Saved dataset to {target_path}")
