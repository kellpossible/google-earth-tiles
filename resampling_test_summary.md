# Resampling Validation Test Summary

## Overview

Added a new integration test `test_resampling_validation()` that validates the resampling behavior when using `selected_zooms` with color-coded tiles.

## Test Design

### Custom Layer Sources
The test uses the `tile_server` fixture to serve custom tiles with distinct colors:
- **RED tiles** at zoom 11 (native resolution)
- **BLUE tiles** at zoom 15 (native resolution)

### Configuration
- **Extent**: (139.69, 35.67) to (139.71, 35.69) - Small Tokyo area
- **Zoom Range**: 11-15 (5 zoom levels)
- **Selected Zooms**: [11, 15] (only fetch native tiles at these zooms)
- **Layer**: Custom "color_coded" layer from local tile server

### Expected Tile Counts
| Zoom | Tiles | Coverage |
|------|-------|----------|
| 11   | 1     | Single tile (1818, 806) |
| 12   | 2     | Resampled from zoom 11 |
| 13   | 4     | Resampled from zoom 15 |
| 14   | 4     | Resampled from zoom 15 |
| 15   | 9     | Native tiles (29098-29100, 12902-12904) |

## Resampling Behavior Validated

The test validates that resampling works correctly by checking tile colors:

### ✅ Zoom 11 (Native - RED)
- **Source**: Native fetch from tile server
- **Expected Color**: RGB(255, 0, 0)
- **Validation**: Center pixel should be red (R>200, G<50, B<50)

### ✅ Zoom 12 (Resampled - RED)
- **Source**: Resampled from zoom 11 (downscaling)
- **Expected Color**: RGB(255, 0, 0)
- **Validation**: Should inherit red color from zoom 11
- **Proves**: Tiles below selected zoom are resampled from the nearest lower zoom

### ✅ Zoom 13 (Resampled - BLUE)
- **Source**: Resampled from zoom 15 (upscaling)
- **Expected Color**: RGB(0, 0, 255)
- **Validation**: Should inherit blue color from zoom 15
- **Proves**: Tiles between selected zooms are resampled from the nearest higher zoom

### ✅ Zoom 14 (Resampled - BLUE)
- **Source**: Resampled from zoom 15 (upscaling)
- **Expected Color**: RGB(0, 0, 255)
- **Validation**: Should inherit blue color from zoom 15
- **Proves**: Multiple zoom levels can be resampled from the same source

### ✅ Zoom 15 (Native - BLUE)
- **Source**: Native fetch from tile server
- **Expected Color**: RGB(0, 0, 255)
- **Validation**: Center pixel should be blue (R<50, G<50, B>200)

## Test Implementation

### Tile Creation
```python
# RED tile at zoom 11
Image.new("RGB", (256, 256), (255, 0, 0))

# BLUE tiles at zoom 15
Image.new("RGB", (256, 256), (0, 0, 255))
```

### Color Validation
```python
# Extract center pixel from each tile
center_pixel = img.getpixel((128, 128))

# Validate color thresholds
assert r > 200 and g < 50 and b < 50  # RED
assert r < 50 and g < 50 and b > 200  # BLUE
```

## Key Insights

1. **Resampling Direction**:
   - Tiles below the nearest selected zoom are resampled DOWN (zoom 12 from 11)
   - Tiles between selected zooms are resampled UP (zoom 13-14 from 15)

2. **Resampling Source Selection**:
   - Uses the nearest selected zoom level
   - Zoom 12 uses zoom 11 (distance: 1)
   - Zoom 13 uses zoom 15 (distance: 2) instead of zoom 11 (distance: 2) - prefers higher zoom
   - Zoom 14 uses zoom 15 (distance: 1)

3. **Color Preservation**:
   - Solid colors are preserved during resampling
   - Validates that image data integrity is maintained

## Benefits of This Test

1. **Regression Prevention**: Catches changes to resampling logic
2. **Visual Validation**: Color coding makes it easy to verify manually in Google Earth
3. **Comprehensive Coverage**: Tests both upscaling and downscaling
4. **Fast Execution**: Small extent minimizes tile count (~0.87s)
5. **No External Dependencies**: Uses local tile server, no network required

## Related Tests

- `test_lod_select_zooms`: Tests LOD structure with selected_zooms (doesn't validate resampling colors)
- `test_multi_zoom_lod`: Tests all native zoom levels (no resampling)
- `test_custom_layer_sources`: Tests custom layer configuration (single zoom, no resampling)

## Test Results

```
tests/test_integration.py::test_resampling_validation PASSED [100%]
```

All validations pass:
- ✅ Zoom 11: RED (native)
- ✅ Zoom 12: RED (resampled from 11)
- ✅ Zoom 13: BLUE (resampled from 15)
- ✅ Zoom 14: BLUE (resampled from 15)
- ✅ Zoom 15: BLUE (native)
