"""Integration tests for KMZ generation with snapshot testing."""

import tempfile
from pathlib import Path

import yaml
from PIL import Image

from src.cli import run_cli


def test_basic_single_layer_composite(snapshot):
    """Test basic KMZ generation with single layer, single zoom."""
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
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Run CLI
        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Assert matches snapshot
        snapshot.assert_match(temp_path / "output.kmz")


def test_multi_zoom_lod(snapshot):
    """Test LOD with multiple zoom levels."""
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
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.kmz")


def test_separate_export_mode(snapshot):
    """Test separate export mode with layer opacity."""
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
                {"name": "slopezone1map", "opacity": 70, "export_mode": "separate"},
            ],
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.kmz")


def test_lod_select_zooms(snapshot):
    """Test LOD with selective zoom levels.

    This test uses selected_zooms=[11, 13] which means:
    - Zoom 11 and 13 tiles are fetched at their native resolution
    - Zoom 12 tiles are still present in the KMZ (for LOD coverage)
    - Zoom 12 tiles are resampled from zoom 13 (not fetched natively)

    This reduces tile fetching while maintaining smooth LOD transitions.
    """
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
            "layers": [
                {
                    "name": "std",
                    "lod_mode": "select_zooms",
                    "selected_zooms": [11, 13],  # Native tiles at 11 & 13; zoom 12 resampled from 13
                }
            ],
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.kmz")


def test_web_compatible_mode(snapshot):
    """Test web compatible mode with chunks."""
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
            "max_zoom": 14,
            "layers": ["std"],
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": True}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.kmz")


def test_web_compatible_with_separate_layer(snapshot):
    """Test web compatible mode with separate layer export."""
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
            "max_zoom": 14,
            "layers": [
                "std",
                {"name": "slopezone1map", "opacity": 60, "export_mode": "separate"},
            ],
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": True}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.kmz")


def test_multiple_layers_blending(snapshot):
    """Test multiple layers with different blend modes and opacities."""
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
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.kmz")


def test_layer_enabled_disabled(snapshot):
    """Test layer enabled/disabled functionality."""
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
                {"name": "ort", "enabled": False},  # Disabled layer
            ],
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.kmz")


def test_blend_modes(snapshot):
    """Test different blend modes."""
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
                {"name": "ort", "blend_mode": "screen"},
            ],
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        snapshot.assert_match(temp_path / "output.kmz")


def test_custom_layer_sources(snapshot, tile_server):
    """Test custom layer sources with local tile server."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test tiles at z=12 for the extent (139.69, 35.67) to (139.71, 35.69)
        # These are the tile coordinates that cover this Tokyo area extent
        tiles_to_create = [
            (12, 3637, 1612),
            (12, 3637, 1613),
        ]

        for z, x, y in tiles_to_create:
            tile_path = tile_server.fixtures_dir / str(z) / str(x) / f"{y}.png"
            tile_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate simple test tile (solid red semi-transparent)
            tile = Image.new("RGBA", (256, 256), (255, 0, 0, 128))
            tile.save(tile_path)

        # Create config using tile server
        config = {
            "layer_sources": {
                "custom_red": {
                    "url_template": tile_server.url_template,
                    "extension": "png",
                    "min_zoom": 10,
                    "max_zoom": 14,
                    "display_name": "Custom Red Layer",
                    "attribution": "Test Custom Layer",
                    "category": "other",
                }
            },
            "extent": {
                "type": "latlon",
                "min_lon": 139.69,
                "min_lat": 35.67,
                "max_lon": 139.71,
                "max_lat": 35.69,
            },
            "min_zoom": 12,
            "max_zoom": 12,
            "layers": ["custom_red"],
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
            "enable_cache": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Run CLI
        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Assert matches snapshot
        snapshot.assert_match(temp_path / "output.kmz")


def test_resampling_validation(tile_server):
    """Test resampling behavior with color-coded tiles.

    This test validates that resampling works correctly by:
    - Creating RED tiles at zoom 11 (native)
    - Creating BLUE tiles at zoom 15 (native)
    - Using selected_zooms=[11, 15] with zoom range 11-15

    Expected resampling:
    - Zoom 11: RED (native)
    - Zoom 12: RED (resampled from zoom 11)
    - Zoom 13: BLUE (resampled from zoom 15)
    - Zoom 14: BLUE (resampled from zoom 15)
    - Zoom 15: BLUE (native)
    """
    import zipfile

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # For the extent (139.69, 35.67) to (139.71, 35.69):
        # Zoom 11: 1 tile (1818, 806)
        # Zoom 13: 4 tiles - need for downsampling calculations
        # Zoom 15: 64 tiles - each zoom 13 tile needs a 4x4 grid (zoom_diff=2) at zoom 15
        # Intermediate zooms will be resampled

        # Create RED tile at zoom 11
        red_tiles_z11 = [(11, 1818, 806)]

        for z, x, y in red_tiles_z11:
            tile_path = tile_server.fixtures_dir / str(z) / str(x) / f"{y}.png"
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            tile = Image.new("RGB", (256, 256), (255, 0, 0))  # Solid red
            tile.save(tile_path)

        # Create BLUE tiles at zoom 15
        # For downsampling from z15 to z13, we need 4x4 grids aligned with z13 tiles
        # Z13 tiles: (7274,3225), (7274,3226), (7275,3225), (7275,3226)
        # Each needs a 4x4 grid at z15 starting at (x13<<2, y13<<2)
        blue_tiles_z15 = []
        for x13, y13 in [(7274, 3225), (7274, 3226), (7275, 3225), (7275, 3226)]:
            base_x = x13 << 2  # x13 * 4
            base_y = y13 << 2  # y13 * 4
            for dy in range(4):
                for dx in range(4):
                    blue_tiles_z15.append((15, base_x + dx, base_y + dy))

        for z, x, y in blue_tiles_z15:
            tile_path = tile_server.fixtures_dir / str(z) / str(x) / f"{y}.png"
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            tile = Image.new("RGB", (256, 256), (0, 0, 255))  # Solid blue
            tile.save(tile_path)

        # Create config with selected_zooms=[11, 15]
        config = {
            "layer_sources": {
                "color_coded": {
                    "url_template": tile_server.url_template,
                    "extension": "png",
                    "min_zoom": 10,
                    "max_zoom": 16,
                    "display_name": "Color Coded Layer",
                    "attribution": "Test Color Coded Layer",
                    "category": "other",
                }
            },
            "extent": {
                "type": "latlon",
                "min_lon": 139.69,
                "min_lat": 35.67,
                "max_lon": 139.71,
                "max_lat": 35.69,
            },
            "min_zoom": 11,
            "max_zoom": 15,
            "layers": [
                {
                    "name": "color_coded",
                    "lod_mode": "select_zooms",
                    "selected_zooms": [11, 15],
                }
            ],
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
            "enable_cache": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Run CLI
        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Extract and validate tile colors
        output_kmz = temp_path / "output.kmz"
        assert output_kmz.exists()

        with zipfile.ZipFile(output_kmz, "r") as kmz:
            # Find all PNG files
            png_files = [f for f in kmz.namelist() if f.endswith(".png")]

            # Validate we have tiles at all zoom levels
            assert len(png_files) > 0, "No tiles found in KMZ"

            # Extract and check color of tiles by zoom level
            zoom_colors = {}

            for png_file in png_files:
                # Extract zoom from filename (format: z_x_y.png)
                filename = Path(png_file).name
                zoom = int(filename.split("_")[0])

                # Extract tile to temp path
                tile_data = kmz.read(png_file)
                tile_path = temp_path / f"extracted_{filename}"
                with open(tile_path, "wb") as f:
                    f.write(tile_data)

                # Load image and get dominant color
                img = Image.open(tile_path)
                # Get the color of the center pixel (should be solid color)
                center_pixel = img.getpixel((128, 128))

                # Convert to RGB tuple
                rgb_color: tuple[int, int, int]
                if isinstance(center_pixel, int):
                    # Grayscale
                    rgb_color = (center_pixel, center_pixel, center_pixel)
                elif isinstance(center_pixel, tuple):
                    # RGB or RGBA
                    if len(center_pixel) == 4:
                        rgb_color = (center_pixel[0], center_pixel[1], center_pixel[2])
                    else:
                        rgb_color = (center_pixel[0], center_pixel[1], center_pixel[2])
                else:
                    # Unexpected type, skip
                    continue

                if zoom not in zoom_colors:
                    zoom_colors[zoom] = rgb_color

        # Validate exact colors at each zoom level
        # With all tiles provided, solid color resampling should be exact

        # Zoom 11: RED (native)
        assert 11 in zoom_colors, "No tiles at zoom 11"
        assert zoom_colors[11] == (255, 0, 0), f"Zoom 11 should be RGB(255, 0, 0), got RGB{zoom_colors[11]}"

        # Zoom 12: RED (resampled from zoom 11)
        assert 12 in zoom_colors, "No tiles at zoom 12"
        assert zoom_colors[12] == (255, 0, 0), (
            f"Zoom 12 should be RGB(255, 0, 0) (resampled from 11), got RGB{zoom_colors[12]}"
        )

        # Zoom 13: BLUE (resampled from zoom 15)
        assert 13 in zoom_colors, "No tiles at zoom 13"
        assert zoom_colors[13] == (0, 0, 255), (
            f"Zoom 13 should be RGB(0, 0, 255) (resampled from 15), got RGB{zoom_colors[13]}"
        )

        # Zoom 14: BLUE (resampled from zoom 15)
        assert 14 in zoom_colors, "No tiles at zoom 14"
        assert zoom_colors[14] == (0, 0, 255), (
            f"Zoom 14 should be RGB(0, 0, 255) (resampled from 15), got RGB{zoom_colors[14]}"
        )

        # Zoom 15: BLUE (native)
        assert 15 in zoom_colors, "No tiles at zoom 15"
        assert zoom_colors[15] == (0, 0, 255), f"Zoom 15 should be RGB(0, 0, 255), got RGB{zoom_colors[15]}"


def test_extract_metadata_from_kml_extent(snapshot):
    """Test extracting metadata from KML extent file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy test KML to temp directory
        test_kml = Path(__file__).parent / "fixtures" / "test_extent_with_metadata.kml"
        extent_kml = temp_path / "extent.kml"
        import shutil

        shutil.copy(test_kml, extent_kml)

        config = {
            "extent": {"type": "file", "file": str(extent_kml)},
            "extract_extent_metadata": True,
            "min_zoom": 12,
            "max_zoom": 12,
            "layers": ["std"],
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Run CLI
        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Verify KMZ was created
        assert (temp_path / "output.kmz").exists()

        # Extract and verify KML contains extracted metadata
        import zipfile

        with zipfile.ZipFile(temp_path / "output.kmz", "r") as kmz:
            kml_content = kmz.read("doc.kml").decode("utf-8")

            # Should contain the extracted name from KML
            assert "Test Study Area" in kml_content


def test_extract_metadata_config_override(snapshot):
    """Test that config metadata overrides extracted metadata."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy test KML to temp directory
        test_kml = Path(__file__).parent / "fixtures" / "test_extent_with_metadata.kml"
        extent_kml = temp_path / "extent.kml"
        import shutil

        shutil.copy(test_kml, extent_kml)

        config = {
            "extent": {"type": "file", "file": str(extent_kml)},
            "extract_extent_metadata": True,
            "name": "Override Name",  # Config overrides extracted
            "min_zoom": 12,
            "max_zoom": 12,
            "layers": ["std"],
            "outputs": [{"type": "kmz", "path": str(temp_path / "output.kmz"), "web_compatible": False}],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Run CLI
        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Extract and verify KML contains override name, not extracted name
        import zipfile

        with zipfile.ZipFile(temp_path / "output.kmz", "r") as kmz:
            kml_content = kmz.read("doc.kml").decode("utf-8")

            # Should contain the override name
            assert "Override Name" in kml_content
            # Should NOT contain the extracted name
            assert "Test Study Area" not in kml_content


def test_merge_extent_kml(snapshot):
    """Test merging extent KML into output KMZ."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy test KML with features to temp directory
        test_kml = Path(__file__).parent / "fixtures" / "test_extent_with_features.kml"
        extent_kml = temp_path / "extent.kml"
        import shutil

        shutil.copy(test_kml, extent_kml)

        config = {
            "extent": {"type": "file", "file": str(extent_kml)},
            "min_zoom": 12,
            "max_zoom": 12,
            "layers": ["std"],
            "outputs": [
                {"type": "kmz", "path": str(temp_path / "output.kmz"), "merge_extent_kml": True, "web_compatible": False}
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Run CLI
        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Extract and verify KML contains merged features
        import zipfile

        with zipfile.ZipFile(temp_path / "output.kmz", "r") as kmz:
            kml_content = kmz.read("doc.kml").decode("utf-8")

            # Should contain the Extent Boundary folder
            assert "Extent Boundary" in kml_content

            # Should contain merged features
            assert "Study Boundaries" in kml_content
            assert "Main Area" in kml_content
            assert "Point of Interest" in kml_content
            assert "boundaryStyle" in kml_content


def test_merge_extent_kml_web_compatible(snapshot):
    """Test merging extent KML in web-compatible mode."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy test KML with features to temp directory
        test_kml = Path(__file__).parent / "fixtures" / "test_extent_with_features.kml"
        extent_kml = temp_path / "extent.kml"
        import shutil

        shutil.copy(test_kml, extent_kml)

        config = {
            "extent": {"type": "file", "file": str(extent_kml)},
            "min_zoom": 12,
            "max_zoom": 12,
            "layers": ["std"],
            "outputs": [
                {"type": "kmz", "path": str(temp_path / "output.kmz"), "merge_extent_kml": True, "web_compatible": True}
            ],
            "include_timestamp": False,
        }

        config_path = temp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Run CLI
        exit_code = run_cli(str(config_path))
        assert exit_code == 0

        # Extract and verify KML contains merged features in web-compatible mode
        import zipfile

        with zipfile.ZipFile(temp_path / "output.kmz", "r") as kmz:
            kml_content = kmz.read("doc.kml").decode("utf-8")

            # Should contain the Extent Boundary folder
            assert "Extent Boundary" in kml_content

            # Should contain merged features
            assert "Study Boundaries" in kml_content
            assert "Main Area" in kml_content
