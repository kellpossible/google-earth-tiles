"""Tests for core functionality."""

from src.core.config import LAYERS
from src.core.tile_calculator import TileCalculator
from src.models.extent import Extent


def test_layer_config():
    """Test layer configuration."""
    assert "std" in LAYERS
    assert "ort" in LAYERS
    assert len(LAYERS) > 5  # Should have many layers

    std_layer = LAYERS["std"]
    assert std_layer.name == "std"
    assert std_layer.extension == "png"
    assert std_layer.min_zoom == 2
    assert std_layer.max_zoom == 18


def test_tile_calculator_bounds():
    """Test tile bounds calculation."""
    # Test Tokyo center tile at zoom 12
    bounds = TileCalculator.tile_to_lat_lon_bounds(3641, 1613, 12)

    assert "north" in bounds
    assert "south" in bounds
    assert "east" in bounds
    assert "west" in bounds

    # North should be greater than south
    assert bounds["north"] > bounds["south"]
    # East should be greater than west
    assert bounds["east"] > bounds["west"]


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
    tiles = TileCalculator.get_tiles_in_extent(139.69, 35.67, 139.71, 35.69, 12)

    assert len(tiles) > 0
    assert all(isinstance(t, tuple) and len(t) == 2 for t in tiles)


def test_extent_validation():
    """Test extent validation."""
    # Valid extent
    extent = Extent(min_lon=139.0, min_lat=35.0, max_lon=140.0, max_lat=36.0)
    assert extent.is_valid()

    # Invalid extent (min > max)
    invalid_extent = Extent(min_lon=140.0, min_lat=36.0, max_lon=139.0, max_lat=35.0)
    assert not invalid_extent.is_valid()


def test_extent_japan_region():
    """Test Japan region validation."""
    # Extent in Tokyo (should be valid)
    tokyo_extent = Extent(min_lon=139.6, min_lat=35.6, max_lon=139.8, max_lat=35.8)
    assert tokyo_extent.is_within_japan_region()
    assert tokyo_extent.is_fully_within_japan_region()

    # Extent outside Japan (should be invalid)
    new_york_extent = Extent(min_lon=-74.1, min_lat=40.6, max_lon=-73.9, max_lat=40.8)
    assert not new_york_extent.is_within_japan_region()


def test_tile_count_estimation():
    """Test tile count estimation."""
    # Small extent at zoom 12
    count = TileCalculator.estimate_tile_count(139.69, 35.67, 139.71, 35.69, 12)

    assert count > 0
    assert isinstance(count, int)


def test_download_size_estimation():
    """Test download size estimation."""
    # 100 PNG tiles
    size_mb = TileCalculator.estimate_download_size(100, "png")
    assert size_mb > 0

    # JPG should be larger than PNG
    jpg_size = TileCalculator.estimate_download_size(100, "jpg")
    png_size = TileCalculator.estimate_download_size(100, "png")
    assert jpg_size > png_size


def test_calculate_chunks_at_zoom():
    """Test chunk calculation at specific zoom level."""
    # Small extent (0.1° x 0.1°) at zoom 12 should produce few chunks
    chunks = TileCalculator.calculate_chunks_at_zoom(139.69, 35.67, 139.79, 35.77, 12, chunk_size=8)
    assert chunks > 0
    assert isinstance(chunks, int)

    # Larger extent should produce more chunks
    large_chunks = TileCalculator.calculate_chunks_at_zoom(139.0, 35.0, 140.0, 36.0, 12, chunk_size=8)
    assert large_chunks > chunks

    # Higher zoom should produce more chunks for same extent (use zoom 16 for significant difference)
    high_zoom_chunks = TileCalculator.calculate_chunks_at_zoom(139.69, 35.67, 139.79, 35.77, 16, chunk_size=8)
    assert high_zoom_chunks > chunks


def test_find_max_web_compatible_zoom():
    """Test finding maximum web-compatible zoom level."""
    # Small extent should support high zoom
    small_extent_zoom = TileCalculator.find_max_web_compatible_zoom(
        139.69, 35.67, 139.71, 35.69, layer_count=2, max_chunks_per_layer=500
    )
    assert small_extent_zoom >= 14
    assert small_extent_zoom <= 18

    # Large extent should force lower zoom
    large_extent_zoom = TileCalculator.find_max_web_compatible_zoom(
        139.0, 35.0, 140.0, 36.0, layer_count=2, max_chunks_per_layer=500
    )
    assert large_extent_zoom < small_extent_zoom

    # More layers should reduce maximum zoom (or keep it same if already at limit)
    more_layers_zoom = TileCalculator.find_max_web_compatible_zoom(
        139.69, 35.67, 139.71, 35.69, layer_count=5, max_chunks_per_layer=500
    )
    assert more_layers_zoom <= small_extent_zoom


def test_get_chunk_grid():
    """Test chunk grid generation."""
    # Get tiles for a small extent
    tiles = TileCalculator.get_tiles_in_extent(139.69, 35.67, 139.71, 35.69, 12)

    # Generate chunk grid
    chunks = TileCalculator.get_chunk_grid(tiles, 12, chunk_size=8)

    assert len(chunks) > 0
    assert all(isinstance(chunk, dict) for chunk in chunks)

    # Each chunk should have required fields
    for chunk in chunks:
        assert "chunk_x" in chunk
        assert "chunk_y" in chunk
        assert "tiles" in chunk
        assert "bounds" in chunk
        assert isinstance(chunk["tiles"], list)
        assert isinstance(chunk["bounds"], dict)
        assert "north" in chunk["bounds"]
        assert "south" in chunk["bounds"]
        assert "east" in chunk["bounds"]
        assert "west" in chunk["bounds"]


def test_calculate_chunk_bounds():
    """Test chunk bounds calculation."""
    # Create a simple set of tiles (2x2 grid)
    tiles = [(100, 200), (101, 200), (100, 201), (101, 201)]
    zoom = 12

    bounds = TileCalculator.calculate_chunk_bounds(tiles, zoom)

    # Should return valid bounds
    assert "north" in bounds
    assert "south" in bounds
    assert "east" in bounds
    assert "west" in bounds

    # North should be greater than south
    assert bounds["north"] > bounds["south"]
    # East should be greater than west
    assert bounds["east"] > bounds["west"]

    # Bounds should be in valid lat/lon range
    assert -90 <= bounds["south"] <= 90
    assert -90 <= bounds["north"] <= 90
    assert -180 <= bounds["west"] <= 180
    assert -180 <= bounds["east"] <= 180


def test_web_compatible_zoom_calculation_realistic():
    """Test web compatible zoom calculation with realistic scenarios."""
    # Asahidake extent (from config)
    asahidake_extent = (142.783, 43.621, 142.971, 43.733)

    # Single layer should support zoom 16
    zoom = TileCalculator.find_max_web_compatible_zoom(*asahidake_extent, layer_count=1, max_chunks_per_layer=500)
    assert zoom >= 16, f"Asahidake with 1 layer should support zoom 16, got {zoom}"

    # Two layers (composited + separate) should also support zoom 16
    zoom = TileCalculator.find_max_web_compatible_zoom(*asahidake_extent, layer_count=2, max_chunks_per_layer=500)
    assert zoom >= 16, f"Asahidake with 2 layers should support zoom 16, got {zoom}"

    # Very small extent (0.01° x 0.01°) should support maximum zoom
    tiny_extent = (139.700, 35.670, 139.710, 35.680)
    zoom = TileCalculator.find_max_web_compatible_zoom(*tiny_extent, layer_count=1, max_chunks_per_layer=500)
    assert zoom == 18, f"Tiny extent should support zoom 18, got {zoom}"
