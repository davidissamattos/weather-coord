# sharve-era5-request
CLI for downloading ERA5 single-level data and generating reports.

## Install

```
pip install .
```

Or for local dev:

```
pip install -e .
```

## Register for the ERA5 to get an API token

1. If you do not have an account yet, please register https://cds.climate.copernicus.eu/
2. If you are not logged in, please login 
3. Open your profile and copy API key


## Configure (one time only)

weather configure --token paste_your_api_key_token

Additional config (if needed)
```bash
# Configure token (CDS or ADS)
weather configure --token <UID:APIKEY> [--url https://ads.atmosphere.copernicus.eu/api]
```

## Usage

Workflow overview:

- `weather download`: fetch 2016-2025 ERA5-Land point time-series (fixed variable set) for one location, with optional automatic geocoding.
- `weather save`: write the processed time-series for a location (from cache) to CSV.
- `weather report`: generate an HTML report for one location or an aggregated report across multiple locations.
- `weather list`: list cached locations (names/country/coords from the database).
- `weather refresh-database`: rebuild the SQLite cache from all downloaded datasets.

### Commands

**Download fixed variables for a point (2016-2025)**

```
weather download --name Gothenburg --lat 57.7 --lon 11.9
```

Notes: downloads ERA5-Land time-series for the fixed variables into `.weather_era5/gothenburg.zip` (zip archive containing CSV files). If the file exists, download is skipped.

**Download with automatic geocoding**

```
weather download --name Gothenburg --find-city Gothenburg --find-country Sweden
```

This uses Nominatim to resolve latitude/longitude and country code; you can also provide `--find-city` alone and let reverse geocoding pick the country.

**Save point data to CSV**

```
weather save --name Gothenburg --output ./gothenburg.csv
```

This reads the downloaded point dataset for the location and writes a CSV with all variables aligned on time.

**Generate a report**

```
weather report --name Gothenburg
```

Produces an HTML report with one summary table for all variables and per-variable histogram and climatology line plots.

**Generate an aggregated report across cities (weighted)**

```
weather report --name "Gothenburg,Oslo" --weights "2,1"
```

Loads each city from the cache, aggregates metrics with provided weights (defaults to equal weights), and writes a combined HTML report.

**List cached locations**

```
weather list
```

Shows name (from the database, falling back to filename if missing), country, and coordinates for cached datasets.

**Refresh the cache database**

```
weather refresh-database
```

Reprocesses all downloaded ZIP/CSV files into the SQLite cache (useful after schema changes or manual file edits).

### Options (common)

- `--name`: label used for the dataset filename (`<name>.zip`) and cache key
- `--lat`, `--lon`: latitude/longitude for downloads
- `--output`: optional output path for `save`; defaults to `.weather_era5/<name>.csv`

### Notes

- Datasets are stored in `.weather_era5/` under your home directory by default; a SQLite cache (`weather.sqlite`) powers `report`, `save`, and `list`.
- Downloads are global (1h cadence) and can take several minutes per variable/year.
- `save` and `report` read only from the cache; run `download` (or `refresh-database` if you already have ZIP/CSV files) first.
