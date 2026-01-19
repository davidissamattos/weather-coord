"""Download helpers for ERA5 land point time-series data."""
from __future__ import annotations

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
