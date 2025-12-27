"""Integration tests for MBTiles generation with snapshot testing."""

import tempfile
from pathlib import Path

import yaml

from src.cli import run_cli


def test_mbtiles_basic_single_layer_png(snapshot):
    """Test basic MBTiles generation with single layer, PNG format."""
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
            "name": "Test Tileset",
            "description": "Test description",
            "attribution": "Test attribution",
            "layers": ["std"],
            "outputs": [
                {
                    "type": "mbtiles",
                    "path": str(temp_path / "output.mbtiles"),
                    "image_format": "png",
                    "export_mode": "composite",
                    "metadata_type": "overlay",
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

        # Assert matches snapshot
        snapshot.assert_match(temp_path / "output.mbtiles")


def test_mbtiles_jpeg_format(snapshot):
    """Test MBTiles with JPEG format and quality setting."""
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
            "name": "JPEG Tileset",
            "layers": ["std"],
            "outputs": [
                {
                    "type": "mbtiles",
                    "path": str(temp_path / "output.mbtiles"),
                    "image_format": "jpg",
                    "jpeg_quality": 90,
                    "export_mode": "composite",
                    "metadata_type": "overlay",
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.mbtiles")


def test_mbtiles_separate_export_mode(snapshot):
    """Test MBTiles separate export mode (one file per layer)."""
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
            "name": "Separate Layers",
            "layers": [
                "std",
                {"name": "slopezone1map", "opacity": 70},
            ],
            "outputs": [
                {
                    "type": "mbtiles",
                    "path": str(temp_path / "output.mbtiles"),
                    "image_format": "png",
                    "export_mode": "separate",
                    "metadata_type": "overlay",
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Verify both files were created
        assert (temp_path / "output_std.mbtiles").exists()
        assert (temp_path / "output_slopezone1map.mbtiles").exists()

        # Snapshot both files
        snapshot.assert_match(temp_path / "output_std.mbtiles")
        # Note: Second file snapshot would need a different test or modified snapshot helper


def test_mbtiles_multi_zoom(snapshot):
    """Test MBTiles with multiple zoom levels."""
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
                    "type": "mbtiles",
                    "path": str(temp_path / "output.mbtiles"),
                    "image_format": "png",
                    "export_mode": "composite",
                    "metadata_name": "Multi-zoom Tileset",
                    "metadata_type": "overlay",
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.mbtiles")


def test_mbtiles_multiple_layers_blending(snapshot):
    """Test MBTiles with multiple layers and blend modes."""
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
                    "type": "mbtiles",
                    "path": str(temp_path / "output.mbtiles"),
                    "image_format": "png",
                    "export_mode": "composite",
                    "metadata_name": "Blended Layers",
                    "metadata_type": "overlay",
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.mbtiles")


def test_mbtiles_baselayer_type(snapshot):
    """Test MBTiles with baselayer metadata type."""
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
                    "type": "mbtiles",
                    "path": str(temp_path / "output.mbtiles"),
                    "image_format": "png",
                    "export_mode": "composite",
                    "metadata_name": "Base Layer",
                    "metadata_description": "Background map",
                    "metadata_type": "baselayer",
                }
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.mbtiles")
