"""Tile compositor for preview rendering."""

import asyncio
import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

import aiohttp
import numpy as np
import requests
from PIL import Image
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestJob, QWebEngineUrlSchemeHandler

from src.models.layer_composition import LayerComposition
from src.core.config import LayerConfig

logger = logging.getLogger(__name__)


class TileCompositor:
    """Composites multiple tile layers with blend modes and opacity."""

    def __init__(self):
        """Initialize compositor."""
        self.session: Optional[aiohttp.ClientSession] = None

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

    async def fetch_tile(self, url: str, needs_upsampling: bool = False,
                         scale_factor: int = 1, offset_x: int = 0, offset_y: int = 0) -> Optional[Image.Image]:
        """
        Fetch a tile from URL and optionally upsample it.

        Args:
            url: Tile URL
            needs_upsampling: Whether to upsample the tile
            scale_factor: Scale factor for upsampling (2^zoom_diff)
            offset_x: X offset within parent tile (0 to scale_factor-1)
            offset_y: Y offset within parent tile (0 to scale_factor-1)

        Returns:
            PIL Image or None if fetch failed
        """
        try:
            session = await self.get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.read()
                    tile = Image.open(io.BytesIO(data)).convert('RGBA')

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
        layer_compositions: List[LayerComposition]
    ) -> Optional[bytes]:
        """
        Composite a tile from multiple layers.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            z: Zoom level
            layer_compositions: List of LayerComposition objects

        Returns:
            PNG image bytes or None if composition failed
        """
        if not layer_compositions:
            # Return transparent tile
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()

        # Fetch all tiles
        tiles = []
        for composition in layer_compositions:
            # Get effective coordinates for this layer
            fetch_x, fetch_y, fetch_z, needs_upsampling, scale_factor, offset_x, offset_y = \
                self._get_effective_tile_coords(x, y, z, composition.layer_config)

            if fetch_x is None:
                # Layer doesn't support this zoom (below min), skip it
                logger.debug(f"Skipping {composition.layer_config.name} at zoom {z} (below min)")
                continue

            # Build URL with effective coordinates
            url = composition.layer_config.url_template.format(x=fetch_x, y=fetch_y, z=fetch_z)

            # Fetch and optionally upsample
            tile = await self.fetch_tile(url, needs_upsampling, scale_factor, offset_x, offset_y)
            if tile:
                tiles.append((tile, composition.opacity, composition.blend_mode))
            else:
                # Use transparent tile if fetch failed
                tiles.append((Image.new('RGBA', (256, 256), (0, 0, 0, 0)), composition.opacity, composition.blend_mode))

        # Composite tiles
        result = Image.new('RGBA', (256, 256), (0, 0, 0, 0))

        for tile, opacity, blend_mode in tiles:
            # Apply opacity
            tile_with_opacity = self.apply_opacity(tile, opacity)

            # Blend with result
            result = self.blend_images(result, tile_with_opacity, blend_mode)

        # Convert to PNG bytes
        buffer = io.BytesIO()
        result.save(buffer, format='PNG')
        return buffer.getvalue()

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

    def _fetch_tile_sync(self, url: str, needs_upsampling: bool = False,
                         scale_factor: int = 1, offset_x: int = 0, offset_y: int = 0) -> Optional[Image.Image]:
        """
        Fetch a tile synchronously using requests and optionally upsample it.

        Args:
            url: Tile URL
            needs_upsampling: Whether to upsample the tile
            scale_factor: Scale factor for upsampling (2^zoom_diff)
            offset_x: X offset within parent tile (0 to scale_factor-1)
            offset_y: Y offset within parent tile (0 to scale_factor-1)

        Returns:
            PIL Image or None if fetch failed
        """
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                tile = Image.open(io.BytesIO(response.content)).convert('RGBA')

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

    def _composite_tile_sync(self, x: int, y: int, z: int, compositions: List[LayerComposition]) -> Optional[bytes]:
        """
        Synchronously composite a tile (for use in background threads).

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
            tiles = []
            for composition in compositions:
                # Get effective coordinates for this layer
                fetch_x, fetch_y, fetch_z, needs_upsampling, scale_factor, offset_x, offset_y = \
                    self._get_effective_tile_coords(x, y, z, composition.layer_config)

                if fetch_x is None:
                    # Layer doesn't support this zoom (below min), skip it
                    logger.debug(f"Skipping {composition.layer_config.name} at zoom {z} (below min)")
                    continue

                # Build URL with effective coordinates
                url = composition.layer_config.url_template.format(x=fetch_x, y=fetch_y, z=fetch_z)

                # Fetch and optionally upsample
                tile = self._fetch_tile_sync(url, needs_upsampling, scale_factor, offset_x, offset_y)
                if tile:
                    tiles.append((tile, composition.opacity, composition.blend_mode))
                else:
                    # Use transparent tile if fetch failed
                    tiles.append((Image.new('RGBA', (256, 256), (0, 0, 0, 0)), composition.opacity, composition.blend_mode))

            # Composite tiles
            result = Image.new('RGBA', (256, 256), (0, 0, 0, 0))

            for tile, opacity, blend_mode in tiles:
                # Apply opacity
                tile_with_opacity = self.compositor.apply_opacity(tile, opacity)

                # Blend with result
                result = self.compositor.blend_images(result, tile_with_opacity, blend_mode)

            # Convert to PNG bytes
            buffer = io.BytesIO()
            result.save(buffer, format='PNG')
            return buffer.getvalue()

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

    def requestStarted(self, request: QWebEngineUrlRequestJob):
        """
        Handle URL request - returns immediately, work happens in background.

        Args:
            request: The URL request
        """
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
