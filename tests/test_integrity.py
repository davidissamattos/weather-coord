"""Tests for data integrity validation."""
import pandas as pd
import numpy as np

from weather_cli.process_data import _validate_dataframe_integrity


def test_validate_dataframe_with_valid_data():
    """Test validation passes for dataframe with valid data."""
    df = pd.DataFrame({
        "latitude": [57.7],
        "longitude": [11.9],
        "temperature_c": [15.5],
        "dewpoint_c": [10.2],
    }, index=pd.to_datetime(["2024-01-01"]))
    
    assert _validate_dataframe_integrity(df, "test") is True


def test_validate_dataframe_with_all_null_data():
    """Test validation fails for dataframe with all null data columns."""
    df = pd.DataFrame({
        "latitude": [57.7],
        "longitude": [11.9],
        "temperature_c": [None],
        "dewpoint_c": [None],
    }, index=pd.to_datetime(["2024-01-01"]))
    
    assert _validate_dataframe_integrity(df, "test") is False


def test_validate_empty_dataframe():
    """Test validation fails for empty dataframe."""
    df = pd.DataFrame()
    
    assert _validate_dataframe_integrity(df, "test") is False


def test_validate_dataframe_with_some_valid_columns():
    """Test validation passes if at least one data column has values."""
    df = pd.DataFrame({
        "latitude": [57.7],
        "longitude": [11.9],
        "temperature_c": [15.5],
        "dewpoint_c": [None],
        "precipitation": [None],
    }, index=pd.to_datetime(["2024-01-01"]))
    
    assert _validate_dataframe_integrity(df, "test") is True


def test_validate_dataframe_only_metadata():
    """Test validation fails if only metadata columns present."""
    df = pd.DataFrame({
        "latitude": [57.7],
        "longitude": [11.9],
        "country": ["SE"],
    }, index=pd.to_datetime(["2024-01-01"]))
    
    assert _validate_dataframe_integrity(df, "test") is False


def test_validate_dataframe_with_partial_nulls():
    """Test validation passes if some rows have data."""
    df = pd.DataFrame({
        "latitude": [57.7, 57.7],
        "longitude": [11.9, 11.9],
        "temperature_c": [None, 15.5],
        "dewpoint_c": [None, None],
    }, index=pd.to_datetime(["2024-01-01", "2024-01-02"]))
    
    assert _validate_dataframe_integrity(df, "test") is True
