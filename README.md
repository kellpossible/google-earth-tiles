# Google Earth Tile Generator

A tile map generator with GUI and CLI modes for creating raster map files from WMTS tile sources. Currently primarily designed for Japan GSI map data.

## Features

- **Multiple output formats**: KMZ (Google Earth), MBTiles (standard tile database), and GeoTIFF (georeferenced raster)
- **Interactive GUI**: Map-based extent selection with real-time preview
- **Multi-layer support**: Composite multiple layers with opacity and blend modes
- **Custom tile sources**: Add your own WMTS/XYZ tile servers
- **CLI automation**: YAML-based configuration for batch processing

## Installation

### System Requirements

**GDAL** (for GeoTIFF output support):
- **macOS**: `brew install gdal`
- **Ubuntu/Debian**: `sudo apt-get install gdal-bin libgdal-dev`
- **Windows**: Download from [GISInternals](https://www.gisinternals.com/release.php) or use [OSGeo4W](https://trac.osgeo.org/osgeo4w/)

### Install with uv

Requires [uv](https://github.com/astral-sh/uv).

```bash
cd google-earth-tile-generator
uv sync
uv run google-earth-tiles
```

## Usage

### GUI Mode

```bash
uv run google-earth-tiles
```

1. Select layers and configure properties (opacity, blend mode, export mode)
2. Draw extent rectangle on the map
3. Set zoom levels (2-18)
4. Add output configurations (KMZ, MBTiles, or GeoTIFF)
5. Generate

### CLI Mode

List available layers:
```bash
uv run google-earth-tiles list-layers
```

Generate from configuration:
```bash
uv run google-earth-tiles download config.yaml
```

Example configuration:
```yaml
extent:
  min_lon: 139.69
  min_lat: 35.67
  max_lon: 139.71
  max_lat: 35.69

min_zoom: 12
max_zoom: 14

# Optional: Global metadata (applies to all outputs)
name: "My Tileset"
description: "Optional description of the tileset"
attribution: "© Custom Attribution 2025"

layers:
  - std
  - name: ort
    opacity: 80
    blend_mode: multiply

outputs:
  - type: kmz
    path: output.kmz
    web_compatible: false
    attribution_mode: description  # "description" (default) or "overlay"

  - type: mbtiles
    path: output.mbtiles
    image_format: png
    export_mode: composite
    metadata_type: baselayer

  - type: geotiff
    path: output.tif
    compression: lzw
    export_mode: composite
    multi_zoom: true  # Include pyramids for all zoom levels
```

### Custom Layer Sources

Add custom WMTS/XYZ tile sources via configuration:

```yaml
layer_sources:
  my_custom_layer:
    url_template: "https://example.com/{z}/{x}/{y}.png"
    extension: png
    min_zoom: 0
    max_zoom: 18
    display_name: "Custom Layer"
    category: "custom"
```

## Output Formats

### KMZ (Google Earth)

- Standard mode: KML with GroundOverlay elements and LOD (Level of Detail)
- Web-compatible mode: Optimized for Google Earth Web (merged tiles, single zoom)
- Separate export: Individual overlay folders (that can be toggled) per layer within single KMZ file

### MBTiles

- MBTiles 1.3 specification
- Composite mode: All layers in single database
- Separate mode: One database per layer (`output_{layer_id}.mbtiles`)
- PNG or JPEG tile encoding
- Full metadata control (name, description, attribution, type)

### GeoTIFF

- EPSG:3857 (Web Mercator) coordinate reference system
- Composite mode: All layers in single GeoTIFF
- Separate mode: One GeoTIFF per layer (`output_{layer_id}.tif`)
- Compression: LZW (default), DEFLATE, JPEG, or None
- Multi-zoom pyramids: Optional internal overviews for efficient multi-scale viewing
- Tiled format: Optimized for large rasters with 256×256 pixel internal tiles
- BigTIFF: Automatic support for files >4GB

Options:
- `compression`: `lzw` (default), `deflate`, `jpeg`, `none`
- `export_mode`: `composite` (default), `separate`
- `multi_zoom`: `true` (default) to include pyramids, `false` for single zoom level
- `jpeg_quality`: 1-100 (default: 80, only for JPEG compression)

## Development

### Running Tests

```bash
uv run pytest                      # All tests
uv run pytest tests/test_core.py   # Core tests only
uv run pytest -k integration       # Integration tests only
```

### Linting

```bash
just lint                 # Run all linters
uv run ruff check .       # Ruff only
uv run ty check           # Type checking only
```

## Attribution

Default tile data: © [Geospatial Information Authority of Japan (GSI)](https://maps.gsi.go.jp/)

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](./LICENSE) file for details.
