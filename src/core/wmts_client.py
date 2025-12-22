"""WMTS tile downloading client."""

import asyncio
import logging
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import aiohttp

from src.core.config import (
    DOWNLOAD_TIMEOUT,
    MAX_CONCURRENT_DOWNLOADS,
    MAX_RETRIES,
    RETRY_DELAY,
    LayerConfig,
)

logger = logging.getLogger(__name__)


class WMTSClient:
    """Client for downloading WMTS tiles."""

    def __init__(self, layer_config: LayerConfig):
        """
        Initialize WMTS client.

        Args:
            layer_config: Layer configuration
        """
        self.layer = layer_config
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def download_tile(
        self,
        x: int,
        y: int,
        z: int,
        output_dir: Path,
    ) -> Optional[Path]:
        """
        Download a single tile.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            z: Zoom level
            output_dir: Directory to save tile

        Returns:
            Path to downloaded tile, or None if download failed
        """
        url = self.layer.url_template.format(x=x, y=y, z=z)
        filename = f"{z}_{x}_{y}.{self.layer.extension}"
        output_path = output_dir / filename

        # Check if tile already exists
        if output_path.exists():
            logger.debug(f"Tile already exists: {filename}")
            return output_path

        # Download with retry logic
        for attempt in range(MAX_RETRIES):
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        output_path.write_bytes(content)
                        logger.debug(f"Downloaded: {filename}")
                        return output_path
                    elif response.status == 404:
                        logger.warning(f"Tile not found (404): {url}")
                        return None
                    else:
                        logger.warning(
                            f"HTTP {response.status} for {url} (attempt {attempt + 1}/{MAX_RETRIES})"
                        )
            except Exception as e:
                logger.warning(
                    f"Error downloading {url}: {e} (attempt {attempt + 1}/{MAX_RETRIES})"
                )

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        logger.error(f"Failed to download tile after {MAX_RETRIES} attempts: {url}")
        return None

    async def download_tiles_batch(
        self,
        tiles: List[Tuple[int, int, int]],
        output_dir: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Tuple[Path, int, int, int]]:
        """
        Download multiple tiles in parallel.

        Args:
            tiles: List of (x, y, z) tuples
            output_dir: Directory to save tiles
            progress_callback: Optional callback function(current, total)

        Returns:
            List of (tile_path, x, y, z) tuples for successfully downloaded tiles
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        downloaded_tiles = []
        completed = 0

        async def download_with_limit(x: int, y: int, z: int):
            """Download with semaphore to limit concurrency."""
            nonlocal completed

            async with semaphore:
                # Rate limiting
                await asyncio.sleep(0.1)

                tile_path = await self.download_tile(x, y, z, output_dir)

                completed += 1
                if progress_callback:
                    progress_callback(completed, len(tiles))

                if tile_path:
                    return (tile_path, x, y, z)
                return None

        # Create download tasks
        tasks = [download_with_limit(x, y, z) for x, y, z in tiles]

        # Execute all downloads
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None results and exceptions
        for result in results:
            if result and not isinstance(result, Exception):
                downloaded_tiles.append(result)

        return downloaded_tiles
