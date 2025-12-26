# Test Snapshots

This directory contains KMZ snapshot files used for integration testing.

## What are snapshot tests?

Snapshot tests compare generated KMZ files against known-good reference files. This ensures that changes to the codebase don't inadvertently alter the output format, structure, or content.

## How snapshot testing works

1. **First run**: When a test runs for the first time, it generates a KMZ file and saves it as a snapshot
2. **Subsequent runs**: The test regenerates the KMZ and compares it to the snapshot
3. **Hash comparison**: If the KMZ files have identical hashes, the test passes immediately
4. **Detailed comparison**: If hashes differ, the snapshot system:
   - Extracts both KMZ files (which are ZIP archives)
   - Compares the directory structure
   - For text files (KML, XML): Shows a unified diff highlighting differences
   - For binary files (PNG images): Reports size differences
   - Displays a comprehensive report of all differences

## Updating snapshots

When you intentionally change the KMZ generation logic, you need to update the snapshots:

```bash
just update-snapshots
```

Or directly with pytest:

```bash
pytest tests/ --update-snapshots
```

## Snapshot files

Each test creates one snapshot KMZ file:

- `test_basic_single_layer_composite.kmz` - Basic single layer at single zoom
- `test_multi_zoom_lod.kmz` - Multiple zoom levels with LOD (all zooms fetched natively)
- `test_separate_export_mode.kmz` - Separate layer export with opacity
- `test_lod_select_zooms.kmz` - Selective zoom levels with resampling
  (Fetches native tiles at zoom 11 & 13 only; zoom 12 resampled from zoom 13)
- `test_web_compatible_mode.kmz` - Web compatible mode with chunks
- `test_web_compatible_with_separate_layer.kmz` - Web mode + separate layers
- `test_multiple_layers_blending.kmz` - Multiple layers with blend modes
- `test_layer_enabled_disabled.kmz` - Disabled layer functionality
- `test_blend_modes.kmz` - Different blend mode testing

## Deterministic output

To ensure snapshots are reproducible, tests disable timestamps in the KML files by setting `include_timestamp: false` in the configuration. This prevents timestamp variations from causing test failures.

## Git tracking

These snapshot KMZ files are tracked in git (exception to the usual `*.kmz` gitignore rule) to ensure consistent test behavior across all developers and CI environments.
