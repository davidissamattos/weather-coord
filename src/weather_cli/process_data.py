"""Processing helpers for ERA5 point time-series datasets."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

try:
    import numpy as np
except ImportError:  # pragma: no cover - depends on runtime environment
    np = None

try:
    import pandas as pd
except ImportError:  # pragma: no cover - depends on runtime environment
    pd = None

from .download import VARIABLES, slugify

CANONICAL_COLUMNS = {
    "temperature_c": ["t2m"],
    "dewpoint_c": ["d2m"],
    "total_precipitation": ["tp"],
    "surface_solar_radiation_downwards": ["ssrd"],
    "surface_thermal_radiation_downwards": ["strd"],
    "snow_cover": ["snowc"],
    "windspeed_u_ms": ["u10"],
    "windspeed_v_ms": ["v10"],
}


def _coerce_float(label: str, value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise SystemExit(f"{label} must be a number, got {value!r}")


def validate_coordinates(lat: float, lon: float) -> None:
    lat_f = _coerce_float("Latitude", lat)
    lon_f = _coerce_float("Longitude", lon)
    if not (-90.0 <= lat_f <= 90.0):
        raise SystemExit("Latitude must be between -90 and 90")
    if not (-180.0 <= lon_f <= 360.0):
        raise SystemExit("Longitude must be between -180 and 360")


def list_downloaded_locations(data_dir: Path) -> list[tuple[str, Path]]:
    """List downloaded location datasets (name -> path)."""
    results: list[tuple[str, Path]] = []
    paths = list(sorted(data_dir.glob("*.zip")))
    paths += list(sorted(data_dir.glob("*.csv")))  # legacy support
    for path in paths:
        results.append((path.stem, path))
    return results


def find_dataset_path(data_dir: Path, name: str) -> Path:
    """Find a dataset file for a given name (prefix match on slug)."""
    slug = slugify(name)
    matches = sorted(data_dir.glob(f"{slug}_*.zip")) or sorted(data_dir.glob(f"{slug}_*.csv"))

    # Fallback to legacy/no-coordinate filename if present
    legacy = data_dir / f"{slug}.zip"
    legacy_csv = data_dir / f"{slug}.csv"
    if not matches and legacy.exists():
        return legacy
    if not matches and legacy_csv.exists():
        return legacy_csv

    if not matches:
        raise SystemExit(
            f"No dataset found for '{name}'. Run 'weather download --name {name} --lat ... --lon ...' first."
        )
    if len(matches) > 1:
        raise SystemExit(
            f"Multiple datasets found for '{name}':\n" + "\n".join(str(m) for m in matches)
            + "\nPlease delete duplicates or specify a unique name."
        )
    return matches[0]


def load_location_timeseries(data_dir: Path, name: str, dataset_path: Path | None = None):
    """Load the fixed-variables time-series for a named location."""
    if pd is None or np is None:
        raise SystemExit("Missing dependencies: pandas and numpy are required.")

    path = dataset_path or find_dataset_path(data_dir, name)
    raw_df = _read_csv_archive(path)
    df = pd.DataFrame(index=raw_df.index)

    # Preserve one latitude/longitude if present
    if "latitude" in raw_df.columns:
        df.insert(0, "latitude", raw_df["latitude"].iloc[0])
    if "longitude" in raw_df.columns:
        df.insert(1 if "latitude" in df.columns else 0, "longitude", raw_df["longitude"].iloc[0])

    missing: list[str] = []
    for canonical, candidates in CANONICAL_COLUMNS.items():
        col_name = next((c for c in candidates if c in raw_df.columns), None)
        if col_name is None:
            missing.append(canonical)
            continue
        series = raw_df[col_name]
        if canonical in {"temperature_c", "dewpoint_c"}:
            series = series - 273.15
        df[canonical] = series.values

    df.index.name = "timestamp"

    # Derived metrics
    df = _add_relative_humidity(df, raw_df)
    df = _add_windspeed(df, raw_df)

    if missing:
        raise SystemExit(
            "Missing variables in dataset: " + ", ".join(missing)
        )

    if df.empty:
        raise SystemExit(f"Dataset for '{name}' contains no data.")
    return df


def _read_csv_archive(path: Path):
    """Load and merge CSV files contained in a ZIP archive."""
    if path.suffix.lower() == ".csv":
        try:
            df = pd.read_csv(path)
        except OSError as exc:
            raise SystemExit(
                f"Failed to open dataset for '{path.stem}': {exc}."
                " The file may be incomplete or corrupt. Delete the file and re-run download: "
                f"{path}"
            ) from exc
        return _clean_frames([df])

    try:
        with ZipFile(path) as zf:
            csv_members = [name for name in zf.namelist() if name.lower().endswith(".csv")]
            if not csv_members:
                raise SystemExit("Downloaded archive contains no CSV files.")

            frames = []
            for name in sorted(csv_members):
                with zf.open(name) as fp:
                    df = pd.read_csv(fp)
                frames.append(df)
    except OSError as exc:
        raise SystemExit(
            f"Failed to open dataset for '{path.stem}': {exc}."
            " The file may be incomplete or corrupt. Delete the file and re-run download: "
            f"{path}"
        ) from exc

    return _clean_frames(frames)


def _clean_frames(frames):
    cleaned = []
    lat_value = None
    lon_value = None

    for df in frames:
        time_col = None
        for candidate in ("timestamp", "valid_time", "time"):
            if candidate in df.columns:
                time_col = candidate
                break
        if time_col is None:
            raise SystemExit("CSV is missing required time column ('timestamp' or 'valid_time' or 'time').")

        lat_col = next((c for c in ("latitude", "lat") if c in df.columns), None)
        lon_col = next((c for c in ("longitude", "lon") if c in df.columns), None)

        if lat_col and lat_value is None:
            lat_value = df[lat_col].dropna().iloc[0] if not df[lat_col].dropna().empty else None
        if lon_col and lon_value is None:
            lon_value = df[lon_col].dropna().iloc[0] if not df[lon_col].dropna().empty else None

        df = df.copy()
        df.rename(columns={time_col: "timestamp"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])

        for col in (lat_col, lon_col):
            if col and col in df.columns:
                df.drop(columns=[col], inplace=True)

        df = df.set_index("timestamp")
        cleaned.append(df)

    if not cleaned:
        raise SystemExit("CSV archive is empty after parsing.")

    merged = pd.concat(cleaned, axis=1).sort_index()
    merged.index.name = "timestamp"
    if lat_value is not None:
        merged.insert(0, "latitude", lat_value)
    if lon_value is not None:
        merged.insert(1 if "latitude" in merged.columns else 0, "longitude", lon_value)
    return merged


def add_rh_from_magnus(df: pd.DataFrame,
                                            d2m_col: str = "d2m",
                                            t2m_col: str = "t2m",
                                            out_col: str = "rh_perc") -> pd.DataFrame:
        """
        Add relative humidity (%) using the Magnus equation.

        Inputs:
            - df[d2m_col]: dew point in Kelvin
            - df[t2m_col]: air temperature in Celsius

        Output:
            - df[out_col]: relative humidity in percent (0–100)
        """
        if d2m_col not in df.columns or t2m_col not in df.columns:
                missing = [c for c in (d2m_col, t2m_col) if c not in df.columns]
                raise KeyError(f"Missing required column(s): {missing}")

        a = 17.27
        b = 237.7

        td_c = df[d2m_col].astype(float) - 273.15  # K -> °C
        t_c = df[t2m_col].astype(float)             # already °C

        rh = 100.0 * np.exp((a * td_c) / (b + td_c) - (a * t_c) / (b + t_c))

        df = df.copy()
        df[out_col] = rh.clip(lower=0.0, upper=100.0)

        return df


def _add_relative_humidity(df: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
        # Compute RH using raw dewpoint (K) and temperature (K -> C)
        temp_df = raw_df.assign(t2m_c=raw_df["t2m"] - 273.15)
        rh_df = add_rh_from_magnus(temp_df, d2m_col="d2m", t2m_col="t2m_c", out_col="rh_perc")
        df["rh_perc"] = rh_df["rh_perc"].values
        return df


def _add_windspeed(df: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
        u = raw_df["u10"].astype(float)
        v = raw_df["v10"].astype(float)
        df["windspeed_ms"] = np.hypot(u, v)
        return df
