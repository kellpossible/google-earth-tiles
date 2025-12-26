# Google Earth Tile Generator

A tool to generate KMZ files from Japan GSI WMTS tiles for use in Google Earth. Supports both GUI and CLI modes with multi-layer tile downloading.

## Features

- 📍 Interactive map for selecting geographic extents (GUI mode)
- 🗺️ Support for 5 different map layers from Japan GSI
- 📦 Multi-layer KMZ generation
- 🚀 Parallel tile downloading with progress tracking
- 💻 Both GUI and CLI modes
- ⚙️ YAML configuration for batch processing

## Installation

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Install with uv

```bash
# Clone or navigate to the project directory
cd google-earth-tile-generator

# Install dependencies
uv sync

# Run the application
uv run google-earth-tiles
```

## Usage

### GUI Mode

Launch the GUI by running without arguments:

```bash
uv run google-earth-tiles
```

Or if installed globally:

```bash
google-earth-tiles
```

#### GUI Workflow:

1. **Select Layers**: Choose one or more map layers from the list
2. **Draw Extent**: Use the map to draw a rectangle around your area of interest
3. **Set Zoom Level**: Choose the tile resolution (higher = more detail)
4. **Choose Output**: Select where to save the KMZ file
5. **Generate**: Click "Generate KMZ" to download tiles and create the file

### CLI Mode

#### List Available Layers

```bash
uv run google-earth-tiles list-layers
```

This shows all available WMTS layers with their details (format, zoom range, URL).

#### Download Tiles

Run with a YAML configuration file:

```bash
uv run google-earth-tiles download config.yaml
```

Enable verbose logging:

```bash
uv run google-earth-tiles download config.yaml -v
```

#### Example Configuration File:

```yaml
# Geographic extent (WGS84 coordinates)
extent:
  min_lon: 139.6912  # West
  min_lat: 35.6794   # South
  max_lon: 139.7018  # East
  max_lat: 35.6895   # North

# Zoom level (2-18 for most layers)
zoom: 12

# Output file path
output: output/tiles.kmz

# Layers to include
layers:
  - std  # Standard map
  - ort  # Aerial photos
```

See `example-config.yaml` for a complete example.

## Available Layers

| Layer | Name | Description | Format | Zoom Range |
|-------|------|-------------|--------|------------|
| `std` | Standard Map | Roads, labels, and features | PNG | 2-18 |
| `pale` | Pale Map | Light colored base map | PNG | 2-18 |
| `blank` | Blank Map | Minimal details | PNG | 5-14 |
| `english` | English Map | English labels | PNG | 5-8 |
| `ort` | Aerial Photos | Satellite imagery | JPG | 2-18 |

## Coverage Area

The WMTS service covers Japan and surrounding areas:
- Longitude: 122°E to 154°E
- Latitude: 20°N to 46°N

The tool will validate that your selected extent falls within this region.

## Output Format

Generated KMZ files contain:
- A KML document with GroundOverlay elements for each tile
- Tile images organized by layer
- Compatible with Google Earth and other KML viewers

### KMZ Structure:

```
output.kmz
├── doc.kml
└── files/
    └── tiles/
        ├── std/
        │   ├── 12_3641_1613.png
        │   └── ...
        └── ort/
            ├── 12_3641_1613.jpg
            └── ...
```

## Development

### Project Structure

```
google-earth-tile-generator/
├── src/
│   ├── main.py              # Entry point
│   ├── cli.py               # CLI mode
│   ├── core/
│   │   ├── config.py        # Layer configurations
│   │   ├── tile_calculator.py
│   │   ├── wmts_client.py
│   │   └── kmz_generator.py
│   ├── gui/
│   │   ├── main_window.py
│   │   ├── map_widget.py
│   │   └── settings_panel.py
│   └── models/
│       └── extent.py
├── tests/
├── pyproject.toml
└── README.md
```

### Type Checking

To run type checking:

```bash
just lint
```

To check specific files or directories:

```bash
just lint-path src/core/
```

#### IDE Integration

This project uses [ty](https://docs.astral.sh/ty/) which includes a language server that provides IDE features like auto-completion, type hints, and inline diagnostics.

**VS Code**

Add to your `.vscode/settings.json`:
```json
{
  "ty.lsp.enable": true
}
```

Install the ty extension from the VS Code marketplace (when available) or configure manually.

**PyCharm**

ty support in PyCharm is available through the ty plugin. See [ty editor integration docs](https://docs.astral.sh/ty/editors/) for installation instructions.

**Neovim**

Configure ty as a language server in your LSP setup. Example with `nvim-lspconfig`:

```lua
require('lspconfig').ty.setup{}
```

For detailed setup instructions, see the [ty editor integration guide](https://docs.astral.sh/ty/editors/).

### Running Tests

```bash
uv run pytest
```

## Limitations

- Tiles are only available for Japan and surrounding areas
- Large extents at high zoom levels can result in thousands of tiles
- Download speed depends on network connection and server load
- The tool respects the WMTS service with rate limiting

## Attribution

Tile data: © [Geospatial Information Authority of Japan (GSI)](https://maps.gsi.go.jp/)

## License

This tool is for educational and personal use. Please respect the terms of service of the Japan GSI WMTS service.

## Troubleshooting

### GUI doesn't launch
- Ensure PyQt6 and PyQt6-WebEngine are installed
- Check Python version (3.10+ required)

### Tiles fail to download
- Check internet connection
- Verify extent is within Japan region
- Check if GSI WMTS service is accessible

### KMZ file won't open in Google Earth
- Verify the file was generated without errors
- Check the extent is valid
- Try with a smaller extent/zoom level first

## Examples

### Example 1: Tokyo City Center

```yaml
extent:
  min_lon: 139.6912
  min_lat: 35.6794
  max_lon: 139.7018
  max_lat: 35.6895
zoom: 14
output: tokyo-center.kmz
layers: [std, ort]
```

### Example 2: Mount Fuji Area

```yaml
extent:
  min_lon: 138.6
  min_lat: 35.2
  max_lon: 138.9
  max_lat: 35.5
zoom: 11
output: fuji-area.kmz
layers: [std, pale]
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
