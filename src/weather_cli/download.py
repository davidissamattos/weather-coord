"""Download helpers for ERA5 land point time-series data."""
from __future__ import annotations

import csv
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

try:
    import cdsapi
except ImportError:  # pragma: no cover - depends on runtime environment
    cdsapi = None

try:
    from geopy.exc import GeocoderServiceError
    from geopy.geocoders import Nominatim
except ImportError:  # pragma: no cover - depends on runtime environment
    Nominatim = None
    GeocoderServiceError = Exception

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


def ensure_dependencies(require_geopy: bool = False) -> None:
    missing: List[str] = []
    if cdsapi is None:
        missing.append("cdsapi")
    if require_geopy and Nominatim is None:
        missing.append("geopy")
    if missing:
        raise SystemExit(
            "Missing dependencies: "
            + ", ".join(missing)
            + "\nInstall with: pip install -r requirements.txt"
        )


def _get_geolocator() -> Nominatim:
    ensure_dependencies(require_geopy=True)
    return Nominatim(user_agent="weather_cli", timeout=10)


def resolve_country_code(country: str | None, lat: float | None = None, lon: float | None = None) -> str:
    """Return ISO 3166-1 alpha-2 country code, using Nominatim when needed."""
    if country:
        code = country.strip()
        if len(code) == 2 and code.isalpha():
            return code.upper()
        geolocator = _get_geolocator()
        location = geolocator.geocode(code, addressdetails=True, exactly_one=True)
        if not location:
            raise SystemExit(f"Could not geocode country: {country}")
        address = location.raw.get("address", {})
        resolved = address.get("country_code")
        if resolved:
            return resolved.upper()
        raise SystemExit(f"Nominatim returned no country code for {country}")

    if lat is not None and lon is not None:
        geolocator = _get_geolocator()
        try:
            location = geolocator.reverse((float(lat), float(lon)), addressdetails=True, exactly_one=True)
        except GeocoderServiceError as exc:  # pragma: no cover - network/runtime dependent
            raise SystemExit(f"Failed to reverse-geocode coordinates: {exc}") from exc
        if not location:
            raise SystemExit("Could not determine country from coordinates.")
        address = location.raw.get("address", {})
        code = address.get("country_code")
        if code:
            return code.upper()
        raise SystemExit("Reverse geocoding succeeded but no country code was returned.")

    raise SystemExit("Country code could not be determined; provide --country or coordinates.")


def geocode_city(city: str, country: str | None = None) -> Tuple[float, float, str]:
    """Return (lat, lon, country_code) for a city using Nominatim."""
    geolocator = _get_geolocator()
    query = city.strip()
    if country:
        query = f"{query}, {country.strip()}"
    try:
        location = geolocator.geocode(query, addressdetails=True, exactly_one=True)
    except GeocoderServiceError as exc:  # pragma: no cover - network/runtime dependent
        raise SystemExit(f"Failed to geocode location: {exc}") from exc
    if not location:
        raise SystemExit(f"Could not find location for '{query}'.")

    address = location.raw.get("address", {})
    code = address.get("country_code")
    if not code:
        raise SystemExit(f"Geocoding did not return a country code for '{query}'.")

    return float(location.latitude), float(location.longitude), code.upper()


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


def _dataset_path(data_dir: Path, name: str, country_code: str, lat: float, lon: float) -> Path:
    return data_dir / f"{slugify(name)}_{country_code}_{lat:.2f}_{lon:.2f}.zip"


def _read_bulk_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        if reader.fieldnames is None:
            raise SystemExit("CSV is missing a header row.")

        header_map = {name.strip().lower(): name for name in reader.fieldnames}
        required = {"name", "country", "lat", "lon"}
        if not required.issubset(header_map):
            missing = required - set(header_map)
            raise SystemExit(f"CSV missing required columns: {', '.join(sorted(missing))}")

        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({key: row[header_map[key]].strip() for key in required})
        return rows


def download_single_location(
    data_dir: Path,
    name: str,
    lat: float | None,
    lon: float | None,
    country: str | None,
    find_city: str | None = None,
    find_country: str | None = None,
    cache_lock: threading.Lock | None = None,
) -> None:
    from .process_data import cache_location_timeseries, validate_coordinates  # lazy import to avoid circular

    resolved_lat = lat
    resolved_lon = lon
    country_code: str | None = None

    if find_city:
        resolved_lat, resolved_lon, country_code = geocode_city(find_city, country=find_country or country)

    if resolved_lat is None or resolved_lon is None:
        raise SystemExit("Latitude and longitude are required unless using --find-city/--find-country.")

    validate_coordinates(resolved_lat, resolved_lon)
    lat_f = round(float(resolved_lat), 2)
    lon_f = round(float(resolved_lon), 2)
    if country_code is None:
        country_code = resolve_country_code(country, lat=lat_f, lon=lon_f)

    ds_path = _dataset_path(data_dir, name, country_code, lat_f, lon_f)
    data_dir.mkdir(parents=True, exist_ok=True)
    if ds_path.exists():
        print(f"Skipping {name}: already present at {ds_path}")
        return

    download_timeseries(ds_path, lat=lat_f, lon=lon_f)
    print("Download complete. Processing and caching...")

    if cache_lock:
        with cache_lock:
            cache_location_timeseries(data_dir, name=name, dataset_path=ds_path)
    else:
        cache_location_timeseries(data_dir, name=name, dataset_path=ds_path)
    print("Cached processed data.")


def bulk_download_from_csv(
    data_dir: Path,
    csv_path: Path,
    max_workers: int = 5,
    dry_run: bool = False,
) -> None:
    rows = _read_bulk_rows(csv_path)
    if not rows:
        print("No rows found in CSV; nothing to do.")
        return

    if dry_run:
        for row in rows:
            cmd = [
                "weather",
                "download",
                "--name",
                row["name"],
                "--country",
                row["country"],
                "--lat",
                row["lat"],
                "--lon",
                row["lon"],
            ]
            print("DRY RUN:", " ".join(cmd))
        return

    print(f"Starting bulk downloads for {len(rows)} cities with up to {max_workers} workers...")
    cache_lock = threading.Lock()

    def worker(entry: dict[str, str]):
        try:
            download_single_location(
                data_dir=data_dir,
                name=entry["name"],
                lat=float(entry["lat"]),
                lon=float(entry["lon"]),
                country=entry["country"],
                cache_lock=cache_lock,
            )
            return (entry, None)
        except SystemExit as exc:
            return (entry, str(exc))
        except Exception as exc:  # pragma: no cover - safety net
            return (entry, f"Unexpected error: {exc}")

    failures: list[tuple[dict[str, str], str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, row): row for row in rows}
        for future in as_completed(futures):
            entry, err = future.result()
            if err:
                failures.append((entry, err))

    if failures:
        print(f"Completed with {len(failures)} failure(s):")
        for entry, err in failures:
            print(f"- {entry['name']} ({entry['country']} {entry['lat']},{entry['lon']}): {err}")
    else:
        print("All bulk downloads finished successfully.")
