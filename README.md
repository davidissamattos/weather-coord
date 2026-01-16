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
```bash# Configure token (CDS or ADS)
weather configure --token <UID:APIKEY> [--url https://ads.atmosphere.copernicus.eu/api]
```

## Usage

Workflow overview:

- `weather download`: fetch 2016-2025 ERA5-Land point time-series (fixed variable set) for one location.
- `weather save`: write the downloaded time-series for a location to CSV.
- `weather report`: generate an HTML report for a location.
- `weather list`: list downloaded locations.

### Commands

**Download fixed variables for a point (2016-2025)**

```
weather download --name Gothenburg --lat 57.7 --lon 11.9
```

Notes: downloads ERA5-Land time-series for the fixed variables into `.weather_era5/gothenburg.zip` (zip archive containing CSV files). If the file exists, download is skipped.

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

**List downloaded locations**

```
weather list
```

### Options (common)

- `--name`: label used for the dataset filename (`<name>.zip`)
- `--lat`, `--lon`: latitude/longitude for downloads
- `--output`: optional output path for `save`; defaults to `.weather_era5/<name>.csv`

### Notes

- Datasets are stored in `.weather_era5/` under your home directory by default.
- Downloads are global (1h cadence) and can take several minutes per variable/year.
- `save` and `report` do not trigger downloads; run `download` first for the variables/years you need.
