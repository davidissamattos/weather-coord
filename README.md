# sharve-era5-request
CLI for downloading ERA5 single-level data and generating reports.

## Install

Install with pip

```
pip install weather-cli-era5
```

Local installation from the repository

```
pip install .
```

Or for local installation in editable mode (for development):

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

- `weather download`: fetch 2016-2025 ERA5-Land point time-series (fixed variable set) for one location, with optional automatic geocoding. Supports bulk downloads from CSV files. Validates data integrity and skips empty files.
- `weather save`: write the processed time-series for a location (from cache) to CSV.
- `weather report`: generate an HTML report for one location or an aggregated report across multiple locations.
- `weather list`: list cached locations (names/country/coords from the database). Supports filtering by country, coordinates, or name.
- `weather refresh-database`: rebuild the SQLite cache from all downloaded datasets. Validates data and skips invalid files.
- `weather delete`: remove a location from cache and filesystem.

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

**Bulk download from CSV**

```bash
weather download --bulk --csv ./cities.csv --max-workers 5
```

Download multiple locations in parallel from a CSV file. The CSV must have headers: `name`, `country`, `lat`, `lon`.

Example CSV format:
```csv
name,country,lat,lon
Gothenburg,SE,57.7,11.97
Oslo,NO,59.91,10.75
Stockholm,SE,59.33,18.07
```

Options:
- `--max-workers`: Number of parallel downloads (default: 5)
- `--dry-run`: Print commands without executing downloads

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

**Filter cached locations**

```bash
# Filter by country
weather list --filter "country=SE"

# Filter by latitude/longitude
weather list --filter "lat > 60"
weather list --filter "lon < 12"

# Combined filters
weather list --filter "country=SE and lat > 60"
weather list --filter "country=SE or country=NO"

# Search by name
weather list --filter "name contains Stockholm"
```

Filter expressions support:
- **Equality/inequality**: `country=SE`, `country!=NO`
- **Numeric comparisons**: `lat > 60`, `lat < 65`, `lon >= 10`
- **Text search**: `name contains Stockholm` (case-sensitive LIKE pattern)
- **Logical operators**: `and`, `or` (can be combined)
- **Field names**: `name`, `country`, `lat`/`latitude`, `lon`/`longitude`

**Refresh the cache database**

```
weather refresh-database
```

Reprocesses all downloaded ZIP/CSV files into the SQLite cache (useful after schema changes or manual file edits). Automatically skips files with no valid data and reports statistics.

**Delete a location**

```bash
weather delete --name Gothenburg
```

Removes a location from both the database (weather and locations tables) and deletes the associated files from the filesystem. Works with location name or filename.

### Options (common)

- `--name`: label used for the dataset filename (`<name>.zip`) and cache key
- `--lat`, `--lon`: latitude/longitude for downloads
- `--output`: optional output path for `save`; defaults to `.weather_era5/<name>.csv`

### Notes

- A download for a specific location takes approximately 30s
- Datasets are stored in `.weather_era5/` under your home directory by default; a SQLite cache (`weather.sqlite`) powers `report`, `save`, and `list`.
- `save` and `report` read only from the cache; run `download` (or `refresh-database` if you already have ZIP/CSV files) first.

