"""Integration tests for GeoTIFF generation with snapshot testing."""

import tempfile
from pathlib import Path

import yaml
from osgeo import gdal

from src.cli import run_cli

# Enable GDAL exceptions for better error messages
gdal.UseExceptions()


def test_geotiff_basic_single_layer_lzw(snapshot):
    """Test basic GeoTIFF generation with single layer, LZW compression."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        config = {
            "extent": {
                "type": "latlon",
                "min_lon": 139.69,
                "min_lat": 35.67,
                "max_lon": 139.71,
                "max_lat": 35.69,
            },
            "min_zoom": 12,
            "max_zoom": 12,
            "name": "Test GeoTIFF",
            "description": "Test description",
            "attribution": "Test attribution",
            "layers": ["std"],
            "outputs": [
                {
                    "type": "geotiff",
                    "path": str(temp_path / "output.tif"),
                    "compression": "lzw",
                    "export_mode": "composite",
                    "multi_zoom": False,  # Single zoom for faster test
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Run CLI
        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Verify output exists
        output_file = temp_path / "output.tif"
        assert output_file.exists()

        # Read and validate GeoTIFF BEFORE snapshot comparison
        ds = gdal.Open(str(output_file))
        assert ds is not None, "Failed to open GeoTIFF"

        # Verify dimensions (extent spans 2 tiles at zoom 12)
        assert ds.RasterXSize == 256, f"Expected width 256, got {ds.RasterXSize}"
        assert ds.RasterYSize == 512, f"Expected height 512, got {ds.RasterYSize}"

        # Verify band count (RGBA)
        assert ds.RasterCount == 4, f"Expected 4 bands (RGBA), got {ds.RasterCount}"

        # Verify compression
        metadata = ds.GetMetadata("IMAGE_STRUCTURE")
        assert metadata.get("COMPRESSION") == "LZW", f"Expected LZW compression, got {metadata.get('COMPRESSION')}"

        # Verify no overviews (multi_zoom=False)
        band = ds.GetRasterBand(1)
        assert band.GetOverviewCount() == 0, f"Expected 0 overviews, got {band.GetOverviewCount()}"

        # Verify CRS is Web Mercator
        srs = ds.GetProjection()
        assert "3857" in srs or "Pseudo-Mercator" in srs, "Expected EPSG:3857 (Web Mercator) CRS"

        # Verify geotransform is set
        geotransform = ds.GetGeoTransform()
        assert geotransform is not None
        assert geotransform != (0, 1, 0, 0, 0, 1), "Geotransform not properly set"

        # Verify raster has data (not all zeros)
        data = band.ReadAsArray(0, 0, 256, 1)  # Read first row
        assert data is not None
        assert data.max() > 0, "Raster data is all zeros"

        # Verify metadata
        general_metadata = ds.GetMetadata()
        assert "TIFFTAG_SOFTWARE" in general_metadata, "Missing TIFFTAG_SOFTWARE metadata"
        assert "AREA_OR_POINT" in general_metadata, "Missing AREA_OR_POINT metadata"

        ds = None

        # Assert matches snapshot (AFTER all validation)
        snapshot.assert_match(output_file)


def test_geotiff_deflate_compression(snapshot):
    """Test GeoTIFF with DEFLATE compression."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        config = {
            "extent": {
                "type": "latlon",
                "min_lon": 139.69,
                "min_lat": 35.67,
                "max_lon": 139.71,
                "max_lat": 35.69,
            },
            "min_zoom": 12,
            "max_zoom": 12,
            "layers": ["std"],
            "outputs": [
                {
                    "type": "geotiff",
                    "path": str(temp_path / "output.tif"),
                    "compression": "deflate",
                    "export_mode": "composite",
                    "multi_zoom": False,
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Validate DEFLATE compression BEFORE snapshot
        output_file = temp_path / "output.tif"
        ds = gdal.Open(str(output_file))
        assert ds is not None

        metadata = ds.GetMetadata("IMAGE_STRUCTURE")
        assert metadata.get("COMPRESSION") == "DEFLATE", (
            f"Expected DEFLATE compression, got {metadata.get('COMPRESSION')}"
        )
        assert ds.RasterCount == 4, f"Expected 4 bands, got {ds.RasterCount}"

        # Verify basic properties
        assert ds.RasterXSize == 256
        assert ds.RasterYSize == 512

        ds = None

        snapshot.assert_match(output_file)


def test_geotiff_jpeg_compression(snapshot):
    """Test GeoTIFF with JPEG compression and quality setting."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        config = {
            "extent": {
                "type": "latlon",
                "min_lon": 139.69,
                "min_lat": 35.67,
                "max_lon": 139.71,
                "max_lat": 35.69,
            },
            "min_zoom": 12,
            "max_zoom": 12,
            "layers": ["std"],
            "outputs": [
                {
                    "type": "geotiff",
                    "path": str(temp_path / "output.tif"),
                    "compression": "jpeg",
                    "jpeg_quality": 90,
                    "export_mode": "composite",
                    "multi_zoom": False,
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Validate JPEG compression BEFORE snapshot
        output_file = temp_path / "output.tif"
        ds = gdal.Open(str(output_file))
        assert ds is not None

        metadata = ds.GetMetadata("IMAGE_STRUCTURE")
        compression = metadata.get("COMPRESSION")
        # JPEG compression uses YCbCr color space
        assert "JPEG" in compression, f"Expected JPEG compression, got {compression}"

        # JPEG should be RGB only (no alpha)
        assert ds.RasterCount == 3, f"Expected 3 bands (RGB) for JPEG, got {ds.RasterCount}"

        # Verify dimensions
        assert ds.RasterXSize == 256
        assert ds.RasterYSize == 512

        ds = None

        snapshot.assert_match(output_file)


def test_geotiff_no_compression(snapshot):
    """Test GeoTIFF with no compression."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        config = {
            "extent": {
                "type": "latlon",
                "min_lon": 139.69,
                "min_lat": 35.67,
                "max_lon": 139.71,
                "max_lat": 35.69,
            },
            "min_zoom": 12,
            "max_zoom": 12,
            "layers": ["std"],
            "outputs": [
                {
                    "type": "geotiff",
                    "path": str(temp_path / "output.tif"),
                    "compression": "none",
                    "export_mode": "composite",
                    "multi_zoom": False,
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Validate no compression BEFORE snapshot
        output_file = temp_path / "output.tif"
        ds = gdal.Open(str(output_file))
        assert ds is not None

        metadata = ds.GetMetadata("IMAGE_STRUCTURE")
        compression = metadata.get("COMPRESSION", "None")
        assert compression in ["None", "NONE", None], f"Expected no compression, got {compression}"

        assert ds.RasterCount == 4
        assert ds.RasterXSize == 256
        assert ds.RasterYSize == 512

        # File should be larger without compression
        file_size = output_file.stat().st_size
        assert file_size > 400_000, f"Uncompressed file should be >400KB, got {file_size}"

        ds = None

        snapshot.assert_match(output_file)


def test_geotiff_separate_export_mode(snapshot):
    """Test GeoTIFF separate export mode (one file per layer)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        config = {
            "extent": {
                "type": "latlon",
                "min_lon": 139.69,
                "min_lat": 35.67,
                "max_lon": 139.71,
                "max_lat": 35.69,
            },
            "min_zoom": 12,
            "max_zoom": 12,
            "layers": [
                "std",
                {"name": "slopezone1map", "opacity": 70},
            ],
            "outputs": [
                {
                    "type": "geotiff",
                    "path": str(temp_path / "output.tif"),
                    "compression": "lzw",
                    "export_mode": "separate",
                    "multi_zoom": False,
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Verify both files were created BEFORE snapshot
        file1 = temp_path / "output_std.tif"
        file2 = temp_path / "output_slopezone1map.tif"
        assert file1.exists(), "output_std.tif not created"
        assert file2.exists(), "output_slopezone1map.tif not created"

        # Validate first file
        ds1 = gdal.Open(str(file1))
        assert ds1 is not None
        assert ds1.RasterCount == 4
        assert ds1.RasterXSize == 256
        assert ds1.RasterYSize == 512
        ds1 = None

        # Validate second file
        ds2 = gdal.Open(str(file2))
        assert ds2 is not None
        assert ds2.RasterCount == 4
        assert ds2.RasterXSize == 256
        assert ds2.RasterYSize == 512
        ds2 = None

        # Snapshot first file
        snapshot.assert_match(file1)


def test_geotiff_multi_zoom_with_pyramids(snapshot):
    """Test GeoTIFF with multiple zoom levels and pyramids enabled."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        config = {
            "extent": {
                "type": "latlon",
                "min_lon": 139.69,
                "min_lat": 35.67,
                "max_lon": 139.71,
                "max_lat": 35.69,
            },
            "min_zoom": 11,
            "max_zoom": 13,
            "layers": ["std"],
            "outputs": [
                {
                    "type": "geotiff",
                    "path": str(temp_path / "output.tif"),
                    "compression": "lzw",
                    "export_mode": "composite",
                    "multi_zoom": True,  # Enable pyramids
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Validate pyramids BEFORE snapshot
        output_file = temp_path / "output.tif"
        ds = gdal.Open(str(output_file))
        assert ds is not None

        # Base raster should be at max_zoom (13)
        assert ds.RasterXSize == 512  # 2x2 tiles at zoom 13
        assert ds.RasterYSize == 512

        # Should have overviews for zoom 11 and 12
        # Overview factors: zoom 12 = 2^(13-12) = 2, zoom 11 = 2^(13-11) = 4
        band = ds.GetRasterBand(1)
        overview_count = band.GetOverviewCount()
        assert overview_count == 2, f"Expected 2 overviews (for zoom 11-12), got {overview_count}"

        # Verify overview sizes
        overview1 = band.GetOverview(0)  # First overview (factor 2)
        assert overview1.XSize == 256, f"First overview should be 256px wide, got {overview1.XSize}"
        assert overview1.YSize == 256

        overview2 = band.GetOverview(1)  # Second overview (factor 4)
        assert overview2.XSize == 128, f"Second overview should be 128px wide, got {overview2.XSize}"
        assert overview2.YSize == 128

        ds = None

        snapshot.assert_match(output_file)


def test_geotiff_multi_zoom_no_pyramids(snapshot):
    """Test GeoTIFF with multiple zoom levels but pyramids disabled."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        config = {
            "extent": {
                "type": "latlon",
                "min_lon": 139.69,
                "min_lat": 35.67,
                "max_lon": 139.71,
                "max_lat": 35.69,
            },
            "min_zoom": 11,
            "max_zoom": 13,
            "layers": ["std"],
            "outputs": [
                {
                    "type": "geotiff",
                    "path": str(temp_path / "output.tif"),
                    "compression": "lzw",
                    "export_mode": "composite",
                    "multi_zoom": False,  # Disable pyramids - only max zoom
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Validate NO pyramids BEFORE snapshot
        output_file = temp_path / "output.tif"
        ds = gdal.Open(str(output_file))
        assert ds is not None

        # Should only have base raster at max_zoom (13)
        assert ds.RasterXSize == 512
        assert ds.RasterYSize == 512

        # Should have NO overviews
        band = ds.GetRasterBand(1)
        overview_count = band.GetOverviewCount()
        assert overview_count == 0, f"Expected 0 overviews (multi_zoom=False), got {overview_count}"

        ds = None

        snapshot.assert_match(output_file)


def test_geotiff_multiple_layers_blending(snapshot):
    """Test GeoTIFF with multiple layers and blend modes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        config = {
            "extent": {
                "type": "latlon",
                "min_lon": 139.69,
                "min_lat": 35.67,
                "max_lon": 139.71,
                "max_lat": 35.69,
            },
            "min_zoom": 12,
            "max_zoom": 12,
            "layers": [
                "std",
                {"name": "ort", "opacity": 80, "blend_mode": "multiply"},
                {"name": "slopezone1map", "opacity": 50, "blend_mode": "overlay"},
            ],
            "outputs": [
                {
                    "type": "geotiff",
                    "path": str(temp_path / "output.tif"),
                    "compression": "lzw",
                    "export_mode": "composite",
                    "multi_zoom": False,
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Validate composited output BEFORE snapshot
        output_file = temp_path / "output.tif"
        ds = gdal.Open(str(output_file))
        assert ds is not None

        # Should be single composite raster
        assert ds.RasterCount == 4
        assert ds.RasterXSize == 256
        assert ds.RasterYSize == 512

        # Verify raster has data from compositing
        band = ds.GetRasterBand(1)
        data = band.ReadAsArray(0, 0, 256, 256)
        assert data is not None
        assert data.max() > 0, "Composited raster has no data"

        # Composited data should have variety (not uniform)
        assert data.std() > 1, "Composited data appears too uniform"

        ds = None

        snapshot.assert_match(output_file)
