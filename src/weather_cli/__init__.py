"""ERA5 weather CLI package."""

from .cli import Weather, main
from .delete import delete_location
from .download import DATA_FOLDER_NAME, VARIABLES, download_timeseries, ensure_dependencies, slugify
from .list import list_downloads
from .process_data import (
	cache_location_timeseries,
	find_dataset_path,
	get_cached_location_timeseries,
	list_downloaded_locations,
	load_location_timeseries,
	validate_coordinates,
)
from .report import render_report
from .report_aggregate import render_aggregate_report
from .report_func import (
	create_aggregation_info,
	create_daily_precipitation,
	create_daily_radiation_band,
	create_summary_table,
	create_temperature_band,
	create_temperature_histogram,
	write_static_page,
)

__all__ = [
	"Weather",
	"main",
	"DATA_FOLDER_NAME",
	"VARIABLES",
	"delete_location",
	"download_timeseries",
	"ensure_dependencies",
	"list_downloads",
	"find_dataset_path",
	"load_location_timeseries",
	"cache_location_timeseries",
	"get_cached_location_timeseries",
	"list_downloaded_locations",
	"slugify",
	"validate_coordinates",
	"create_daily_precipitation",
	"create_temperature_histogram",
	"create_summary_table",
	"render_report",
	"render_aggregate_report",
	"write_static_page",
	"create_temperature_band",
	"create_daily_radiation_band",
	"create_aggregation_info",
]
