# Google Earth Tile Generator

A tile map generator with GUI and CLI modes for creating raster map files from WMTS tile sources. Currently primarily designed for Japan GSI map data.

**WARNING**: vibe coded using claude, with only marginal code review. Use at your own risk.

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

View configuration schema documentation:
```bash
uv run google-earth-tiles schema           # Formatted markdown
uv run google-earth-tiles schema --yaml    # Raw YAML
```

Generate from configuration:
```bash
uv run google-earth-tiles download config.yaml
```

## Configuration Format

See the [JSON Schema](schemas/config.schema.yaml) for the format of configuration yaml files.

### View Schema Documentation

To view the complete schema documentation in your terminal:

```bash
uv run google-earth-tiles schema           # Pretty-printed with colors
uv run google-earth-tiles schema --yaml    # Raw YAML (for scripting/piping)
```

The default format displays a formatted view of all configuration options, types, and descriptions.

### IDE Support

For the best editing experience with autocomplete and validation:

1. Use VS Code with the [YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)
2. Saved configs automatically include schema reference
3. Get real-time validation, autocomplete, and hover documentation

### Schema Development

When modifying the configuration structure:

```bash
just codegen  # Regenerate Pydantic models from schema
```

- Schema: `schemas/config.schema.yaml`
- Generated models: `src/models/generated.py`

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

### Code Generation

```bash
just codegen  # Generate Pydantic models from schema
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
