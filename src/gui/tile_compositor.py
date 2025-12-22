"""Tile compositor for preview rendering."""

import asyncio
import io
import logging
from typing import List, Optional

import aiohttp
import requests
from PIL import Image
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestJob, QWebEngineUrlSchemeHandler

from src.models.layer_composition import LayerComposition

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

    async def fetch_tile(self, url: str) -> Optional[Image.Image]:
        """
        Fetch a tile from URL.

        Args:
            url: Tile URL

        Returns:
            PIL Image or None if fetch failed
        """
        try:
            session = await self.get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.read()
                    return Image.open(io.BytesIO(data)).convert('RGBA')
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
            base: Base image
            overlay: Overlay image
            blend_mode: Blend mode ('normal', 'multiply', 'screen', 'overlay')

        Returns:
            Blended image
        """
        if blend_mode == 'normal':
            # Normal alpha compositing
            result = Image.alpha_composite(base, overlay)
        elif blend_mode == 'multiply':
            # Multiply blend
            base_rgb = base.convert('RGB')
            overlay_rgb = overlay.convert('RGB')
            blended = Image.blend(base_rgb, overlay_rgb, 0.5)  # Simplified multiply
            # TODO: Implement proper multiply blend
            result = Image.alpha_composite(base, overlay)
        elif blend_mode == 'screen':
            # Screen blend
            # TODO: Implement screen blend
            result = Image.alpha_composite(base, overlay)
        elif blend_mode == 'overlay':
            # Overlay blend
            # TODO: Implement overlay blend
            result = Image.alpha_composite(base, overlay)
        else:
            result = Image.alpha_composite(base, overlay)

        return result

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
            url = composition.layer_config.url_template.format(x=x, y=y, z=z)
            tile = await self.fetch_tile(url)
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

    def set_layer_compositions(self, compositions: List[LayerComposition]):
        """
        Set the layer compositions for preview tiles.

        Args:
            compositions: List of LayerComposition objects
        """
        self.layer_compositions = compositions

    def _fetch_tile_sync(self, url: str) -> Optional[Image.Image]:
        """
        Fetch a tile synchronously using requests.

        Args:
            url: Tile URL

        Returns:
            PIL Image or None if fetch failed
        """
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return Image.open(io.BytesIO(response.content)).convert('RGBA')
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
                url = composition.layer_config.url_template.format(x=x, y=y, z=z)
                tile = self._fetch_tile_sync(url)
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

    def requestStarted(self, request: QWebEngineUrlRequestJob):
        """
        Handle URL request synchronously.

        This runs in Qt's IO thread, so blocking here won't freeze the UI.

        Args:
            request: The URL request
        """
        url = request.requestUrl().toString()

        try:
            # Parse URL: preview://tile/z/x/y.png
            qurl = request.requestUrl()

            # Get path component (should be /z/x/y.png)
            path = qurl.path()

            # Remove leading slash and .png extension
            if path.startswith('/'):
                path = path[1:]
            if path.endswith('.png'):
                path = path[:-4]

            # Split into z/x/y parts
            parts = path.split('/')

            if len(parts) != 3:
                logger.warning(f"Invalid preview URL format: {url} (path: {qurl.path()}, parts: {parts})")
                request.fail(QWebEngineUrlRequestJob.Error.UrlInvalid)
                return

            z = int(parts[0])
            x = int(parts[1])
            y = int(parts[2])

            # Composite tile synchronously (we're already in IO thread)
            compositions = list(self.layer_compositions)
            tile_data = self._composite_tile_sync(x, y, z, compositions)

            if tile_data:
                # Create QBuffer with request as parent to keep it alive
                buffer = QBuffer(request)
                buffer.setData(QByteArray(tile_data))
                buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                request.reply(b'image/png', buffer)
            else:
                request.fail(QWebEngineUrlRequestJob.Error.RequestFailed)

        except Exception as e:
            logger.exception(f"Error handling preview tile request: {e}")
            request.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
