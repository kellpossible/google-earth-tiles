"""Tile compositor for preview rendering."""

import asyncio
import hashlib
import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

import aiohttp
import numpy as np
import requests
from PIL import Image
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QStandardPaths, QUrl
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestJob, QWebEngineUrlSchemeHandler

from src.models.layer_composition import LayerComposition
from src.core.config import LayerConfig

logger = logging.getLogger(__name__)


class TileCompositor:
    """Composites multiple tile layers with blend modes and opacity."""

    def __init__(self):
        """Initialize compositor."""
        self.session: Optional[aiohttp.ClientSession] = None

        # Initialize cache directory
        # QStandardPaths.CacheLocation already includes org/app name if set via QCoreApplication
        cache_base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
        self.cache_dir = Path(cache_base) / "tiles"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Tile cache directory: {self.cache_dir}")

    def _get_cache_path(self, url: str) -> Path:
        """
        Get cache file path for a tile URL.

        Args:
            url: Tile URL

        Returns:
            Path to cached tile file
        """
        # Hash the URL to create a unique filename
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        return self.cache_dir / f"{url_hash}.png"

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    def _get_effective_tile_coords(self, x: int, y: int, z: int, layer_config: LayerConfig) -> tuple:
        """
        Get actual tile coords to fetch, handling zoom clamping and upsampling.

        Args:
            x, y, z: Requested tile coordinates
            layer_config: Layer configuration with min/max zoom

        Returns:
            (fetch_x, fetch_y, fetch_z, needs_upsampling, scale_factor, offset_x, offset_y)
        """
        if z < layer_config.min_zoom:
            # Layer doesn't support this zoom - skip it
            return (None, None, None, False, 1, 0, 0)
        elif z > layer_config.max_zoom:
            # Need to fetch parent tile and upsample
            effective_z = layer_config.max_zoom
            zoom_diff = z - effective_z
            scale_factor = 2 ** zoom_diff

            fetch_x = x >> zoom_diff
            fetch_y = y >> zoom_diff
            offset_x = x - (fetch_x << zoom_diff)
            offset_y = y - (fetch_y << zoom_diff)

            return (fetch_x, fetch_y, effective_z, True, scale_factor, offset_x, offset_y)
        else:
            # Within range - fetch normally
            return (x, y, z, False, 1, 0, 0)

    def _upsample_tile(self, image: Image.Image, scale_factor: int, offset_x: int, offset_y: int) -> Image.Image:
        """
        Upsample a tile by scaling and cropping using bilinear interpolation.

        Args:
            image: Source tile (256x256)
            scale_factor: How much to scale (2^zoom_diff)
            offset_x, offset_y: Which subtile to extract (0 to scale_factor-1)

        Returns:
            Upsampled 256x256 tile
        """
        upscaled_size = 256 * scale_factor
        scaled_image = image.resize((upscaled_size, upscaled_size), Image.Resampling.BILINEAR)

        left = offset_x * 256
        top = offset_y * 256
        right = left + 256
        bottom = top + 256

        return scaled_image.crop((left, top, right, bottom))

    async def _downsample_from_grid(
        self,
        base_x: int,
        base_y: int,
        source_zoom: int,
        zoom_diff: int,
        url_template: str
    ) -> Image.Image:
        """
        Downsample by fetching a grid of higher-zoom tiles.

        Args:
            base_x: Base tile X coordinate at source zoom
            base_y: Base tile Y coordinate at source zoom
            source_zoom: Source zoom level (higher than target)
            zoom_diff: Difference between source and target zoom (source - target)
            url_template: URL template for fetching tiles

        Returns:
            Downsampled 256x256 tile
        """
        scale = 2 ** zoom_diff
        canvas_size = 256 * scale
        canvas = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))

        # Fetch and place tiles in grid
        for dy in range(scale):
            for dx in range(scale):
                tile_x = base_x + dx
                tile_y = base_y + dy

                url = url_template.format(x=tile_x, y=tile_y, z=source_zoom)
                tile = await self.fetch_tile(url, needs_upsampling=False, scale_factor=1, offset_x=0, offset_y=0)

                if tile:
                    canvas.paste(tile, (dx * 256, dy * 256))

        # Downsample to target size using high-quality Lanczos filter
        return canvas.resize((256, 256), Image.Resampling.LANCZOS)

    def fetch_tile_sync(self, url: str, needs_upsampling: bool = False,
                        scale_factor: int = 1, offset_x: int = 0, offset_y: int = 0) -> Optional[Image.Image]:
        """
        Fetch a tile synchronously and optionally upsample it.

        Checks cache first, downloads if not cached, and saves to cache.

        Args:
            url: Tile URL
            needs_upsampling: Whether to upsample the tile
            scale_factor: Scale factor for upsampling (2^zoom_diff)
            offset_x: X offset within parent tile (0 to scale_factor-1)
            offset_y: Y offset within parent tile (0 to scale_factor-1)

        Returns:
            PIL Image or None if fetch failed
        """
        cache_path = self._get_cache_path(url)

        # Check cache first
        if cache_path.exists():
            try:
                tile = Image.open(cache_path).convert('RGBA')

                # Upsample if needed using bilinear interpolation
                if needs_upsampling:
                    tile = self._upsample_tile(tile, scale_factor, offset_x, offset_y)

                return tile
            except Exception as e:
                logger.warning(f"Error reading cached tile {cache_path}: {e}")
                # Fall through to download

        # Download tile
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                tile = Image.open(io.BytesIO(response.content)).convert('RGBA')

                # Save to cache
                try:
                    tile.save(cache_path, format='PNG')
                except Exception as e:
                    logger.warning(f"Error saving tile to cache {cache_path}: {e}")

                # Upsample if needed using bilinear interpolation
                if needs_upsampling:
                    tile = self._upsample_tile(tile, scale_factor, offset_x, offset_y)

                return tile
            else:
                logger.warning(f"Failed to fetch tile {url}: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Error fetching tile {url}: {e}")
            return None

    async def fetch_tile(self, url: str, needs_upsampling: bool = False,
                         scale_factor: int = 1, offset_x: int = 0, offset_y: int = 0) -> Optional[Image.Image]:
        """
        Fetch a tile from URL asynchronously and optionally upsample it.

        Checks cache first, downloads if not cached, and saves to cache.

        Args:
            url: Tile URL
            needs_upsampling: Whether to upsample the tile
            scale_factor: Scale factor for upsampling (2^zoom_diff)
            offset_x: X offset within parent tile (0 to scale_factor-1)
            offset_y: Y offset within parent tile (0 to scale_factor-1)

        Returns:
            PIL Image or None if fetch failed
        """
        cache_path = self._get_cache_path(url)

        # Check cache first
        if cache_path.exists():
            try:
                tile = Image.open(cache_path).convert('RGBA')

                # Upsample if needed using bilinear interpolation
                if needs_upsampling:
                    tile = self._upsample_tile(tile, scale_factor, offset_x, offset_y)

                return tile
            except Exception as e:
                logger.warning(f"Error reading cached tile {cache_path}: {e}")
                # Fall through to download

        # Download tile
        try:
            session = await self.get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.read()
                    tile = Image.open(io.BytesIO(data)).convert('RGBA')

                    # Save to cache
                    try:
                        tile.save(cache_path, format='PNG')
                    except Exception as e:
                        logger.warning(f"Error saving tile to cache {cache_path}: {e}")

                    # Upsample if needed using bilinear interpolation
                    if needs_upsampling:
                        tile = self._upsample_tile(tile, scale_factor, offset_x, offset_y)

                    return tile
                else:
                    logger.warning(f"Failed to fetch tile {url}: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.warning(f"Error fetching tile {url}: {e}")
            return None

    @staticmethod
    def _blend_tile_stack(tiles: List[tuple]) -> bytes:
        """
        Composite a stack of tiles into a single PNG image.

        Shared by both async and sync compositors to ensure consistent blending.

        Args:
            tiles: List of (tile_image, opacity, blend_mode) tuples

        Returns:
            PNG image bytes
        """
        result = Image.new('RGBA', (256, 256), (0, 0, 0, 0))

        for tile, opacity, blend_mode in tiles:
            # Apply opacity if needed
            if opacity < 100:
                # Create a copy and modify alpha channel
                tile_copy = tile.copy()
                alpha = tile_copy.split()[3]
                alpha = alpha.point(lambda p: int(p * opacity / 100))
                tile_copy.putalpha(alpha)
                tile_with_opacity = tile_copy
            else:
                tile_with_opacity = tile

            # Blend with result using numpy for performance
            base_array = np.array(result, dtype=np.float32) / 255.0
            overlay_array = np.array(tile_with_opacity, dtype=np.float32) / 255.0

            base_rgb = base_array[:, :, :3]
            base_alpha = base_array[:, :, 3:4]
            overlay_rgb = overlay_array[:, :, :3]
            overlay_alpha = overlay_array[:, :, 3:4]

            # Apply blend mode to RGB channels
            if blend_mode == 'normal':
                blended_rgb = overlay_rgb
            elif blend_mode == 'multiply':
                blended_rgb = base_rgb * overlay_rgb
            elif blend_mode == 'screen':
                blended_rgb = 1 - (1 - base_rgb) * (1 - overlay_rgb)
            elif blend_mode == 'overlay':
                mask = base_rgb < 0.5
                blended_rgb = np.where(
                    mask,
                    2 * base_rgb * overlay_rgb,
                    1 - 2 * (1 - base_rgb) * (1 - overlay_rgb)
                )
            else:
                blended_rgb = overlay_rgb

            # Alpha compositing: blend the blended RGB with base RGB using overlay's alpha
            result_rgb = base_rgb * (1 - overlay_alpha) + blended_rgb * overlay_alpha

            # Alpha channel compositing
            result_alpha = overlay_alpha + base_alpha * (1 - overlay_alpha)

            # Combine and convert back
            result_array = np.dstack([result_rgb, result_alpha])
            result_array = np.clip(result_array * 255, 0, 255).astype(np.uint8)
            result = Image.fromarray(result_array, mode='RGBA')

        # Convert to PNG bytes
        buffer = io.BytesIO()
        result.save(buffer, format='PNG')
        return buffer.getvalue()

    def apply_opacity(self, image: Image.Image, opacity: int) -> Image.Image:
        """
        Apply opacity to an image.

        Args:
            image: PIL Image in RGBA mode
            opacity: Opacity 0-100

        Returns:
            Image with opacity applied
        """
        if opacity >= 100:
            return image

        # Create a copy and modify alpha channel
        result = image.copy()
        alpha = result.split()[3]
        alpha = alpha.point(lambda p: int(p * opacity / 100))
        result.putalpha(alpha)
        return result

    def blend_images(self, base: Image.Image, overlay: Image.Image, blend_mode: str) -> Image.Image:
        """
        Blend two images using specified blend mode.

        Args:
            base: Base image (RGBA)
            overlay: Overlay image (RGBA with opacity already applied)
            blend_mode: Blend mode ('normal', 'multiply', 'screen', 'overlay')

        Returns:
            Blended image
        """
        if blend_mode == 'normal':
            # Normal alpha compositing
            return Image.alpha_composite(base, overlay)

        # For other blend modes, we need to do custom blending
        # Convert to numpy arrays for pixel operations
        base_array = np.array(base, dtype=np.float32) / 255.0
        overlay_array = np.array(overlay, dtype=np.float32) / 255.0

        # Extract RGB and alpha channels
        base_rgb = base_array[:, :, :3]
        base_alpha = base_array[:, :, 3:4]
        overlay_rgb = overlay_array[:, :, :3]
        overlay_alpha = overlay_array[:, :, 3:4]

        # Apply blend mode to RGB channels
        if blend_mode == 'multiply':
            # Multiply: darker, multiplies color values
            blended_rgb = base_rgb * overlay_rgb
        elif blend_mode == 'screen':
            # Screen: lighter, inverse of multiply
            blended_rgb = 1 - (1 - base_rgb) * (1 - overlay_rgb)
        elif blend_mode == 'overlay':
            # Overlay: multiply if base < 0.5, screen if base >= 0.5
            blended_rgb = np.where(
                base_rgb < 0.5,
                2 * base_rgb * overlay_rgb,
                1 - 2 * (1 - base_rgb) * (1 - overlay_rgb)
            )
        else:
            # Unknown mode, fall back to normal
            return Image.alpha_composite(base, overlay)

        # Alpha blending: combine base and overlay using overlay's alpha
        # result_rgb = base_rgb * (1 - overlay_alpha) + blended_rgb * overlay_alpha
        result_rgb = base_rgb * (1 - overlay_alpha) + blended_rgb * overlay_alpha

        # Alpha channel: standard alpha compositing
        result_alpha = base_alpha + overlay_alpha * (1 - base_alpha)

        # Combine RGB and alpha
        result_array = np.concatenate([result_rgb, result_alpha], axis=2)

        # Convert back to uint8 and create PIL image
        result_array = np.clip(result_array * 255, 0, 255).astype(np.uint8)
        return Image.fromarray(result_array, mode='RGBA')

    async def composite_tile(
        self,
        x: int,
        y: int,
        z: int,
        layer_compositions: List[LayerComposition],
        output_min_zoom: Optional[int] = None,
        output_max_zoom: Optional[int] = None
    ) -> Optional[bytes]:
        """
        Composite a tile from multiple layers with per-layer LOD support.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            z: Zoom level
            layer_compositions: List of LayerComposition objects
            output_min_zoom: Minimum zoom level in output range (for LOD)
            output_max_zoom: Maximum zoom level in output range (for LOD)

        Returns:
            PNG image bytes or None if composition failed
        """
        if not layer_compositions:
            # Return transparent tile
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()

        # Determine output zoom range if not provided
        if output_min_zoom is None:
            output_min_zoom = min(comp.layer_config.min_zoom for comp in layer_compositions)
        if output_max_zoom is None:
            output_max_zoom = max(comp.layer_config.max_zoom for comp in layer_compositions)

        # Fetch all tiles
        tiles = []
        for composition in layer_compositions:
            # Skip disabled layers
            if not composition.enabled:
                logger.debug(f"Skipping {composition.layer_config.name} (layer disabled)")
                continue

            # Get available zooms for this layer based on its LOD settings
            available_zooms = composition.get_available_zooms(output_min_zoom, output_max_zoom)

            if not available_zooms:
                logger.debug(f"Skipping {composition.layer_config.name} at zoom {z} (no available zooms)")
                continue

            # For select_zooms mode, only include layer at explicitly selected zoom levels
            # (no resampling from nearby zooms)
            if composition.lod_mode == "select_zooms" and z not in available_zooms:
                logger.debug(f"Skipping {composition.layer_config.name} at zoom {z} (zoom not in selected_zooms)")
                continue

            # Find best source zoom for this layer
            source_zoom = composition.find_best_source_zoom(z, available_zooms)

            # Calculate fetch coordinates and determine if resampling is needed
            if source_zoom == z:
                # Direct fetch - no resampling
                url = composition.layer_config.url_template.format(x=x, y=y, z=source_zoom)
                tile = await self.fetch_tile(url, needs_upsampling=False, scale_factor=1, offset_x=0, offset_y=0)
            elif source_zoom < z:
                # Upsample from lower zoom
                zoom_diff = z - source_zoom
                scale_factor = 2 ** zoom_diff
                fetch_x = x >> zoom_diff
                fetch_y = y >> zoom_diff
                offset_x = x - (fetch_x << zoom_diff)
                offset_y = y - (fetch_y << zoom_diff)
                url = composition.layer_config.url_template.format(x=fetch_x, y=fetch_y, z=source_zoom)
                tile = await self.fetch_tile(url, needs_upsampling=True, scale_factor=scale_factor, offset_x=offset_x, offset_y=offset_y)
            else:
                # Downsample from higher zoom
                zoom_diff = source_zoom - z
                base_x = x << zoom_diff
                base_y = y << zoom_diff
                tile = await self._downsample_from_grid(base_x, base_y, source_zoom, zoom_diff, composition.layer_config.url_template)

            # Add tile to composition
            if tile:
                tiles.append((tile, composition.opacity, composition.blend_mode))
            else:
                # Use transparent tile if fetch failed
                tiles.append((Image.new('RGBA', (256, 256), (0, 0, 0, 0)), composition.opacity, composition.blend_mode))

        # Composite tiles using shared blending logic
        return self._blend_tile_stack(tiles)

    async def close(self):
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()


class PreviewTileSchemeHandler(QWebEngineUrlSchemeHandler):
    """URL scheme handler for preview:// tiles.

    Note: requestStarted runs in Qt's IO thread, so blocking operations here
    won't freeze the UI. We use synchronous tile composition.
    """

    def __init__(self, parent=None):
        """Initialize handler."""
        super().__init__(parent)
        self.compositor = TileCompositor()
        self.layer_compositions: List[LayerComposition] = []
        # Thread pool for non-blocking tile composition
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="TileLoader")
        # Keep buffers alive - store them with weak references to requests
        self.active_buffers = {}
        # Version counter to track composition changes - helps avoid processing stale requests
        self.composition_version = 0

    def set_layer_compositions(self, compositions: List[LayerComposition]):
        """
        Set the layer compositions for preview tiles.

        Args:
            compositions: List of LayerComposition objects
        """
        self.layer_compositions = compositions
        # Increment version to invalidate pending requests
        self.composition_version += 1

    def _composite_tile_sync(self, x: int, y: int, z: int, compositions: List[LayerComposition]) -> Optional[bytes]:
        """
        Synchronously composite a tile (for use in background threads).

        Note: Preview always uses all available zoom levels, ignoring LOD settings.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            z: Zoom level
            compositions: Layer compositions

        Returns:
            PNG bytes or None
        """
        try:
            if not compositions:
                # Return transparent tile
                img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                return buffer.getvalue()

            # Fetch all tiles synchronously
            # Note: Preview avoids downsampling (uses _get_effective_tile_coords)
            # but still respects select_zooms LOD configuration
            tiles = []
            for composition in compositions:
                # Skip disabled layers
                if not composition.enabled:
                    logger.debug(f"Skipping {composition.layer_config.name} (layer disabled)")
                    continue

                # For select_zooms mode, only include layer at explicitly selected zoom levels
                if composition.lod_mode == "select_zooms" and z not in composition.selected_zooms:
                    logger.debug(f"Skipping {composition.layer_config.name} at zoom {z} (zoom not in selected_zooms)")
                    continue

                # Get effective coordinates for this layer
                fetch_x, fetch_y, fetch_z, needs_upsampling, scale_factor, offset_x, offset_y = \
                    self.compositor._get_effective_tile_coords(x, y, z, composition.layer_config)

                if fetch_x is None:
                    # Layer doesn't support this zoom (below min), skip it
                    logger.debug(f"Skipping {composition.layer_config.name} at zoom {z} (below min)")
                    continue

                # Build URL with effective coordinates
                url = composition.layer_config.url_template.format(x=fetch_x, y=fetch_y, z=fetch_z)

                # Fetch and optionally upsample using compositor's method
                tile = self.compositor.fetch_tile_sync(url, needs_upsampling, scale_factor, offset_x, offset_y)
                if tile:
                    tiles.append((tile, composition.opacity, composition.blend_mode))
                else:
                    # Use transparent tile if fetch failed
                    tiles.append((Image.new('RGBA', (256, 256), (0, 0, 0, 0)), composition.opacity, composition.blend_mode))

            # Composite tiles using shared blending logic
            return TileCompositor._blend_tile_stack(tiles)

        except Exception as e:
            logger.exception(f"Error compositing tile {z}/{x}/{y}: {e}")
            return None

    def _handle_request_in_background(self, request: QWebEngineUrlRequestJob, x: int, y: int, z: int, compositions: List[LayerComposition], version: int):
        """
        Handle the request in a background thread.

        Args:
            request: The URL request
            x: Tile X coordinate
            y: Tile Y coordinate
            z: Zoom level
            compositions: Layer compositions
            version: Composition version when request was made
        """
        try:
            # Check if this request is stale (composition has changed)
            if version != self.composition_version:
                logger.debug(f"Skipping stale tile request {z}/{x}/{y} (version {version} != {self.composition_version})")
                try:
                    request.fail(QWebEngineUrlRequestJob.Error.RequestAborted)
                except RuntimeError:
                    pass
                return

            # Composite tile
            tile_data = self._composite_tile_sync(x, y, z, compositions)

            if tile_data:
                # Create QBuffer without parent (we're in different thread)
                buffer = QBuffer()
                buffer.setData(QByteArray(tile_data))
                buffer.open(QIODevice.OpenModeFlag.ReadOnly)

                # Store buffer to keep it alive (use id(request) as key)
                request_id = id(request)
                self.active_buffers[request_id] = buffer

                # Clean up old buffers (keep last 100)
                if len(self.active_buffers) > 100:
                    # Remove oldest entries
                    items = list(self.active_buffers.items())
                    self.active_buffers = dict(items[-100:])

                try:
                    request.reply(b'image/png', buffer)
                except RuntimeError:
                    # Request was already deleted (timeout or cancelled)
                    logger.debug(f"Request for tile {z}/{x}/{y} was already deleted")
            else:
                try:
                    request.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
                except RuntimeError:
                    # Request was already deleted
                    logger.debug(f"Request for tile {z}/{x}/{y} was already deleted (fail)")

        except Exception as e:
            logger.exception(f"Error compositing tile {z}/{x}/{y}: {e}")
            try:
                request.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
            except RuntimeError:
                # Request was already deleted
                pass

    def requestStarted(self, a0: Optional[QWebEngineUrlRequestJob]) -> None:
        """
        Handle URL request - returns immediately, work happens in background.

        Args:
            a0: The URL request
        """
        request = a0  # Reassign for readability
        if not request:
            return

        url = request.requestUrl().toString()

        try:
            # Parse URL: preview://tile/z/x/y.png?t=timestamp
            qurl = request.requestUrl()

            # Get path component (should be /z/x/y.png)
            path = qurl.path()

            # Remove leading slash
            if path.startswith('/'):
                path = path[1:]

            # Remove .png extension (and any query string if present)
            if path.endswith('.png'):
                path = path[:-4]

            # Handle query strings that might have been included in path
            if '?' in path:
                path = path.split('?')[0]

            # Split into z/x/y parts
            parts = path.split('/')

            if len(parts) != 3:
                logger.warning(f"Invalid preview URL format: {url} (path: {qurl.path()}, parts: {parts})")
                request.fail(QWebEngineUrlRequestJob.Error.UrlInvalid)
                return

            z = int(parts[0])
            x = int(parts[1])
            y = int(parts[2])

            # Copy compositions to avoid race conditions
            compositions = list(self.layer_compositions)
            # Capture current version
            version = self.composition_version

            # Submit to thread pool and return immediately (non-blocking)
            self.executor.submit(self._handle_request_in_background, request, x, y, z, compositions, version)

        except Exception as e:
            logger.exception(f"Error handling preview tile request: {e}")
            request.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
