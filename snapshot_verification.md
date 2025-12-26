# Snapshot Verification Report

## Summary

All 9 snapshot files have been inspected and verified to match their test configurations.

## Detailed Verification

### ✅ test_basic_single_layer_composite.kmz
**Config**: Single layer (std), zoom 12
**Expected**: Basic KMZ with 2 tiles at zoom 12
**Actual**:
- Size: 224.6 KB
- 2 GroundOverlays (2 tiles at zoom 12)
- No LOD regions (single zoom)
- Separate layer mode (not composited)
- Files: `files/tiles/std/12_3637_1612.png`, `12_3637_1613.png`

**Status**: ✅ Correct

---

### ✅ test_multi_zoom_lod.kmz
**Config**: Single layer (std), zoom 11-13, all zooms fetched natively
**Expected**: LOD structure with native tiles at all zoom levels
**Actual**:
- Size: 789.8 KB
- 7 GroundOverlays with LOD regions
  - Zoom 13: 4 overlays (LOD: 80 - -1)
  - Zoom 12: 2 overlays (LOD: 80 - 256)
  - Zoom 11: 1 overlay (LOD: -1 - 256)
- Proper LOD hierarchy for smooth transitions

**Status**: ✅ Correct

---

### ✅ test_lod_select_zooms.kmz
**Config**: Single layer (std), zoom 11-13, selected_zooms=[11, 13]
**Expected**: Native tiles at zoom 11 & 13, zoom 12 resampled from zoom 13
**Actual**:
- Size: 890.2 KB
- 7 GroundOverlays with LOD regions
  - Zoom 13: 4 overlays (LOD: 80 - -1) - native tiles
  - Zoom 12: 2 overlays (LOD: 80 - 256) - resampled from zoom 13
  - Zoom 11: 1 overlay (LOD: -1 - 256) - native tiles
- Zoom 12 tiles are larger (165KB, 166KB) vs test_multi_zoom_lod (113KB, 115KB)
  confirming they are resampled from higher resolution zoom 13

**Status**: ✅ Correct - zoom 12 present but resampled as expected

---

### ✅ test_separate_export_mode.kmz
**Config**: Two layers (std + slopezone1map), zoom 12, slopezone1map as separate layer with 70% opacity
**Expected**: Composited base + separate layer with opacity
**Actual**:
- Size: 231.6 KB
- 4 GroundOverlays (2 composited + 2 separate)
- No LOD regions (single zoom)
- 4 folders:
  - "Layer: Base" with composited tiles
  - "Composited Tiles"
  - "Layer: slopezone1map" with separate layer
  - "slopezone1map Tiles"
- Separate layer has opacity: `b2ffffff` (70% opacity)
- Files: `files/tiles/composited/12_*.png`, `files/tiles/slopezone1map/12_*.png`

**Status**: ✅ Correct

---

### ✅ test_web_compatible_mode.kmz
**Config**: Single layer (std), zoom 12-14, web_compatible=True
**Expected**: Single zoom with 2048x2048 chunks (no LOD regions)
**Actual**:
- Size: 435.2 KB
- 1 GroundOverlay (single merged chunk)
- No LOD regions (web compatible mode)
- Description includes "Optimized for Google Earth Web"
- Files: `files/chunks/std/14_0_0.png`
- Single zoom 14 (calculated as max supportable zoom)

**Status**: ✅ Correct

---

### ✅ test_web_compatible_with_separate_layer.kmz
**Config**: Two layers (std + slopezone1map), zoom 12-14, web_compatible=True, slopezone1map as separate with 60% opacity
**Expected**: Composited chunk + separate layer chunk with opacity
**Actual**:
- Size: 436.8 KB
- 2 GroundOverlays (1 composited + 1 separate)
- No LOD regions (web compatible mode)
- Description includes "Optimized for Google Earth Web"
- 3 folders:
  - "Layer: Base"
  - "Composited Tiles (Zoom 14)"
  - "Layer: slopezone1map"
- Separate layer has opacity: `99ffffff` (60% opacity)
- Files: `files/chunks/composited/14_0_0.png`, `files/chunks/slopezone1map/14_0_0.png`

**Status**: ✅ Correct

---

### ✅ test_multiple_layers_blending.kmz
**Config**: Three layers (std, ort @ 80% multiply, slopezone1map @ 50% overlay), zoom 12
**Expected**: Composited tiles with blend modes applied
**Actual**:
- Size: 397.6 KB
- 2 GroundOverlays (2 composited tiles)
- No LOD regions (single zoom)
- Files: `files/tiles/composited/12_3637_1612.png`, `12_3637_1613.png`
- Larger file size (397KB vs 231KB) confirms multiple layers composited
- Blend modes applied during compositing

**Status**: ✅ Correct

---

### ✅ test_layer_enabled_disabled.kmz
**Config**: Two layers (std enabled, ort disabled), zoom 12
**Expected**: Only std layer tiles (ort excluded)
**Actual**:
- Size: 224.6 KB
- 2 GroundOverlays (2 tiles at zoom 12)
- No LOD regions (single zoom)
- Separate layer mode (not composited, since only one enabled layer)
- Files: `files/tiles/std/12_3637_1612.png`, `12_3637_1613.png`
- Identical to test_basic_single_layer_composite (both have only std layer)

**Status**: ✅ Correct - disabled layer excluded as expected

---

### ✅ test_blend_modes.kmz
**Config**: Two layers (std, ort @ screen blend mode), zoom 12
**Expected**: Composited tiles with screen blend mode applied
**Actual**:
- Size: 232.4 KB
- 2 GroundOverlays (2 composited tiles)
- No LOD regions (single zoom)
- Files: `files/tiles/composited/12_3637_1612.png`, `12_3637_1613.png`
- Screen blend mode applied during compositing

**Status**: ✅ Correct

---

## Overall Assessment

All 9 snapshots are correct and match their expected configurations:

1. ✅ **Single layer tests** produce separate layer output
2. ✅ **Multi-layer tests** produce composited output
3. ✅ **LOD tests** have proper Region elements with correct min/max LOD values
4. ✅ **Selective zoom tests** correctly resample intermediate zoom levels
5. ✅ **Separate layer tests** correctly apply opacity and create dual folder structure
6. ✅ **Web compatible tests** create merged chunks without LOD regions
7. ✅ **Blend mode tests** correctly composite multiple layers
8. ✅ **Disabled layer tests** correctly exclude disabled layers
9. ✅ **Timestamp exclusion** working (no timestamps in descriptions)

## Key Findings

- **LOD behavior**: Selective zoom mode (selected_zooms) correctly resamples intermediate zoom levels from the nearest higher zoom level
- **File sizes**: Confirm compositing and resampling are working (different file sizes between native and resampled tiles)
- **Web compatible mode**: Correctly creates single-zoom chunk-based output with no LOD regions
- **Opacity encoding**: Correctly encodes opacity in KML color values (e.g., `b2ffffff` for 70%, `99ffffff` for 60%)
