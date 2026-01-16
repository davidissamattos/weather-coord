"""ERA5 weather CLI package."""

from .cli import Weather, main
from .download import DATA_FOLDER_NAME, VARIABLES, download_timeseries, ensure_dependencies, slugify
from .list import list_downloads
from .process_data import find_dataset_path, list_downloaded_locations, load_location_timeseries, validate_coordinates
from .report import create_daily_precipitation, create_daily_radiation_max, create_summary_table, create_temperature_climatology, create_temperature_histogram, render_report, write_static_page

__all__ = [
	"Weather",
	"main",
	"DATA_FOLDER_NAME",
	"VARIABLES",
	"download_timeseries",
	"ensure_dependencies",
	"list_downloads",
	"find_dataset_path",
	"load_location_timeseries",
	"list_downloaded_locations",
	"slugify",
	"validate_coordinates",
	"create_daily_precipitation",
	"create_daily_radiation_max",
	"create_temperature_climatology",
	"create_temperature_histogram",
	"create_summary_table",
	"render_report",
	"write_static_page",
]
