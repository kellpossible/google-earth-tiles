"""Tests for core functionality."""

import pytest

from src.core.config import LAYERS
from src.core.tile_calculator import TileCalculator
from src.models.extent import Extent


def test_layer_config():
    """Test layer configuration."""
    assert 'std' in LAYERS
    assert 'ort' in LAYERS
    assert len(LAYERS) == 5

    std_layer = LAYERS['std']
    assert std_layer.name == 'std'
    assert std_layer.extension == 'png'
    assert std_layer.min_zoom == 2
    assert std_layer.max_zoom == 18


def test_tile_calculator_bounds():
    """Test tile bounds calculation."""
    # Test Tokyo center tile at zoom 12
    bounds = TileCalculator.tile_to_lat_lon_bounds(3641, 1613, 12)

    assert 'north' in bounds
    assert 'south' in bounds
    assert 'east' in bounds
    assert 'west' in bounds

    # North should be greater than south
    assert bounds['north'] > bounds['south']
    # East should be greater than west
    assert bounds['east'] > bounds['west']


def test_tile_calculator_lat_lon_to_tile():
    """Test coordinate to tile conversion."""
    # Tokyo coordinates
    lat, lon = 35.6762, 139.6503
    zoom = 12

    x, y = TileCalculator.lat_lon_to_tile(lat, lon, zoom)

    # Verify it's a valid tile coordinate
    assert isinstance(x, int)
    assert isinstance(y, int)
    assert 0 <= x < 2**zoom
    assert 0 <= y < 2**zoom


def test_tile_calculator_get_tiles_in_extent():
    """Test getting tiles in extent."""
    # Small extent (should be few tiles)
    tiles = TileCalculator.get_tiles_in_extent(
        139.69, 35.67, 139.71, 35.69, 12
    )

    assert len(tiles) > 0
    assert all(isinstance(t, tuple) and len(t) == 2 for t in tiles)


def test_extent_validation():
    """Test extent validation."""
    # Valid extent
    extent = Extent(
        min_lon=139.0,
        min_lat=35.0,
        max_lon=140.0,
        max_lat=36.0
    )
    assert extent.is_valid()

    # Invalid extent (min > max)
    invalid_extent = Extent(
        min_lon=140.0,
        min_lat=36.0,
        max_lon=139.0,
        max_lat=35.0
    )
    assert not invalid_extent.is_valid()


def test_extent_japan_region():
    """Test Japan region validation."""
    # Extent in Tokyo (should be valid)
    tokyo_extent = Extent(
        min_lon=139.6,
        min_lat=35.6,
        max_lon=139.8,
        max_lat=35.8
    )
    assert tokyo_extent.is_within_japan_region()
    assert tokyo_extent.is_fully_within_japan_region()

    # Extent outside Japan (should be invalid)
    new_york_extent = Extent(
        min_lon=-74.1,
        min_lat=40.6,
        max_lon=-73.9,
        max_lat=40.8
    )
    assert not new_york_extent.is_within_japan_region()


def test_tile_count_estimation():
    """Test tile count estimation."""
    # Small extent at zoom 12
    count = TileCalculator.estimate_tile_count(
        139.69, 35.67, 139.71, 35.69, 12
    )

    assert count > 0
    assert isinstance(count, int)


def test_download_size_estimation():
    """Test download size estimation."""
    # 100 PNG tiles
    size_mb = TileCalculator.estimate_download_size(100, 'png')
    assert size_mb > 0

    # JPG should be larger than PNG
    jpg_size = TileCalculator.estimate_download_size(100, 'jpg')
    png_size = TileCalculator.estimate_download_size(100, 'png')
    assert jpg_size > png_size
