"""Processing helpers for ERA5 point time-series datasets."""
from __future__ import annotations

import math
import sqlite3
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

DB_FILENAME = "weather.sqlite"
DB_COLUMNS = [
    "filename",
    "name",
    "country",
    "timestamp",
    "latitude",
    "longitude",
    "temperature_c",
    "dewpoint_c",
    "total_precipitation",
    "surface_solar_radiation_downwards",
    "surface_thermal_radiation_downwards",
    "snow_cover",
    "windspeed_u_ms",
    "windspeed_v_ms",
    "rh_perc",
    "heat_index_c",
    "heat_index_classification",
    "windspeed_ms",
]


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


def _db_path(data_dir: Path) -> Path:
    return data_dir / DB_FILENAME


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS weather (
            filename TEXT NOT NULL,
            name TEXT,
            country TEXT,
            timestamp TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            temperature_c REAL,
            dewpoint_c REAL,
            total_precipitation REAL,
            surface_solar_radiation_downwards REAL,
            surface_thermal_radiation_downwards REAL,
            snow_cover REAL,
            windspeed_u_ms REAL,
            windspeed_v_ms REAL,
            rh_perc REAL,
            heat_index_c REAL,
            heat_index_classification TEXT,
            windspeed_ms REAL,
            PRIMARY KEY (filename, country, timestamp)
        )
        """
    )
    # If an older table exists without expected columns, migrate or rebuild it.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(weather)").fetchall()}
    # Migrate legacy columns (name = slug, display_name = human display)
    if "filename" not in cols and "name" in cols and "display_name" in cols:
        try:
            conn.execute("ALTER TABLE weather RENAME COLUMN name TO filename")
            conn.execute("ALTER TABLE weather RENAME COLUMN display_name TO name")
            cols = {row[1] for row in conn.execute("PRAGMA table_info(weather)").fetchall()}
        except sqlite3.Error:
            cols = set()

    # If still missing required columns, rebuild the table (cache can be refreshed).
    required = set(DB_COLUMNS)
    if not required.issubset(cols) or "country" not in cols:
        conn.execute("DROP TABLE weather")
        conn.execute(
            """
            CREATE TABLE weather (
                filename TEXT NOT NULL,
                name TEXT,
                country TEXT,
                timestamp TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                temperature_c REAL,
                dewpoint_c REAL,
                total_precipitation REAL,
                surface_solar_radiation_downwards REAL,
                surface_thermal_radiation_downwards REAL,
                snow_cover REAL,
                windspeed_u_ms REAL,
                windspeed_v_ms REAL,
                rh_perc REAL,
                heat_index_c REAL,
                heat_index_classification TEXT,
                windspeed_ms REAL,
                PRIMARY KEY (filename, country, timestamp)
            )
            """
        )
    conn.commit()


def _parse_meta_from_path(path: Path) -> tuple[str, str | None]:
    parts = path.stem.split("_")
    name = parts[0] if parts else path.stem
    country = parts[1] if len(parts) >= 4 else None
    return name, country


def _read_cached_timeseries(data_dir: Path, name: str):
    db = _db_path(data_dir)
    if not db.exists():
        return None
    if pd is None:
        return None
    with sqlite3.connect(db) as conn:
        try:
            df = pd.read_sql_query(
                "SELECT * FROM weather WHERE filename = ? ORDER BY timestamp",
                conn,
                params=[name],
            )
        except Exception:
            return None
    if df.empty:
        return None
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).set_index("timestamp")
    # Preserve column order
    cols = [c for c in DB_COLUMNS if c not in {"filename", "timestamp", "name"}]
    existing = [c for c in cols if c in df.columns]
    return df[existing]


def _resolve_cache_key(data_dir: Path, name: str) -> str | None:
    """Return the filename key to use for cached lookup given a user-supplied name."""
    db = _db_path(data_dir)
    if not db.exists():
        return None

    slug = slugify(name)
    try:
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                """
                SELECT filename
                FROM weather
                WHERE filename = ?
                   OR lower(COALESCE(name, '')) = lower(?)
                   OR filename LIKE ?
                ORDER BY
                    CASE
                        WHEN filename = ? THEN 0
                        WHEN lower(COALESCE(name, '')) = lower(?) THEN 1
                        ELSE 2
                    END,
                    length(filename)
                LIMIT 1
                """,
                (slug, name, f"{slug}%", slug, name),
            ).fetchone()
    except sqlite3.Error:
        return None

    return row[0] if row else None


def _write_cached_timeseries(
    data_dir: Path,
    filename: str,
    name: str | None,
    df: pd.DataFrame,
    country: str | None,
) -> None:
    db = _db_path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        _ensure_table(conn)
        conn.execute("DELETE FROM weather WHERE filename = ?", (filename,))
        placeholders = ",".join(["?"] * len(DB_COLUMNS))
        col_names = ",".join(DB_COLUMNS)
        rows = []
        for ts, row in df.iterrows():
            values = {
                "filename": filename,
                "name": name,
                "country": country,
                "timestamp": ts.isoformat(),
            }
            for col in DB_COLUMNS:
                if col in {"filename", "timestamp", "country", "name"}:
                    continue
                values[col] = row.get(col) if hasattr(row, "get") else row[col] if col in row else None
            rows.append(tuple(values.get(col) for col in DB_COLUMNS))
        conn.executemany(
            f"INSERT OR REPLACE INTO weather ({col_names}) VALUES ({placeholders})",
            rows,
        )
        conn.commit()


def get_cached_location_timeseries(data_dir: Path, name: str) -> pd.DataFrame:
    """Return cached timeseries from sqlite; do not process raw data."""
    key = _resolve_cache_key(data_dir, name)
    if key is None:
        raise SystemExit(
            f"Cached data not found for '{name}'. Run 'weather refresh-database' or re-download to populate the cache."
        )

    cached = _read_cached_timeseries(data_dir, key)
    if cached is None:
        raise SystemExit(
            f"Cached data not found for '{name}'. Run 'weather refresh-database' or re-download to populate the cache."
        )
    return cached


def process_raw_timeseries(raw_df: pd.DataFrame, country_code: str | None = None) -> pd.DataFrame:
    """Convert raw ERA5 dataframe into the canonical processed form ready for caching."""
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
    df = _add_heat_index(df)
    df = _add_windspeed(df, raw_df)

    # Attach country if known so cache and callers see it
    if "country" not in df.columns:
        df.insert(0, "country", country_code)

    if missing:
        raise SystemExit(
            "Missing variables in dataset: " + ", ".join(missing)
        )

    if df.empty:
        raise SystemExit("Dataset contains no data after processing.")

    return df


def cache_location_timeseries(
    data_dir: Path,
    name: str,
    dataset_path: Path,
    country_code: str | None = None,
) -> pd.DataFrame:
    """Process a raw dataset and store it in the sqlite cache; does not read from cache."""
    if pd is None or np is None:
        raise SystemExit("Missing dependencies: pandas and numpy are required.")

    display_name = name
    filename = slugify(name)

    path = dataset_path
    if country_code is None:
        _derived_name, derived_country = _parse_meta_from_path(path)
        if derived_country:
            country_code = derived_country

    raw_df = _read_csv_archive(path)
    df = process_raw_timeseries(raw_df, country_code=country_code)
    _write_cached_timeseries(data_dir, filename, display_name, df, country_code)
    return df


def load_location_timeseries(data_dir: Path, name: str) -> pd.DataFrame:
    """Deprecated shim: load only from cache. Prefer get_cached_location_timeseries."""
    return get_cached_location_timeseries(data_dir, name)


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


def compute_hi_f(temp_c: float, rh: float) -> float:
    """
    Compute Heat Index (Fahrenheit) from air temperature in Celsius and RH in percent
    following Rothfusz (1990) with NWS adjustments.
    """

    T = temp_c * 1.8 + 32
    RH = rh

    simple = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (RH * 0.094))
    avg_hi = (T + simple) / 2.0

    if avg_hi < 80:
        return avg_hi

    HI = (
        -42.379
        + 2.04901523 * T
        + 10.14333127 * RH
        - 0.22475541 * T * RH
        - 0.00683783 * T * T
        - 0.05481717 * RH * RH
        + 0.00122874 * T * T * RH
        + 0.00085282 * T * RH * RH
        - 0.00000199 * T * T * RH * RH
    )

    if (RH < 13) and (80 <= T <= 112):
        adj = ((13 - RH) / 4.0) * math.sqrt((17 - abs(T - 95.0)) / 17.0)
        HI -= adj

    if (RH > 85) and (80 <= T <= 87):
        adj = ((RH - 85) / 10.0) * ((87 - T) / 5.0)
        HI += adj

    return HI


def _classify_heat_index(hi_f: float) -> str:
    if hi_f < 80:
        return "Normal"
    if hi_f < 90:
        return "Caution"
    if hi_f < 103:
        return "Extreme Caution"
    if hi_f < 125:
        return "Danger"
    return "Extreme Danger"


def _add_heat_index(df: pd.DataFrame) -> pd.DataFrame:
    if "temperature_c" not in df.columns or "rh_perc" not in df.columns:
        raise SystemExit("Missing temperature or relative humidity for heat index calculation.")

    temps = df["temperature_c"].astype(float)
    rhs = df["rh_perc"].astype(float)
    hi_f_values = [compute_hi_f(t, r) for t, r in zip(temps, rhs)]
    hi_c_values = [(hi_f - 32.0) / 1.8 for hi_f in hi_f_values]
    classes = [_classify_heat_index(hi_f) for hi_f in hi_f_values]

    df = df.copy()
    df["heat_index_c"] = hi_c_values
    df["heat_index_classification"] = classes
    return df


def _add_windspeed(df: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
        u = raw_df["u10"].astype(float)
        v = raw_df["v10"].astype(float)
        df["windspeed_ms"] = np.hypot(u, v)
        return df
