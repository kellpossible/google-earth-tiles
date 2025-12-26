"""Tile pyramid downsampling for LOD generation."""

import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


class TileDownsampler:
    """Generates lower zoom level tiles from higher zoom tiles."""

    @staticmethod
    def downsample_tile_level(
        source_tiles: list[tuple[Path, int, int, int]], target_zoom: int, output_dir: Path, progress_callback=None
    ) -> list[tuple[Path, int, int, int]]:
        """
        Downsample a collection of tiles at zoom N to create tiles at zoom N-1.

        This implements the standard tile pyramid approach: group each 2x2 grid
        of tiles from zoom N into a single tile at zoom N-1.

        Args:
            source_tiles: List of (tile_path, x, y, z) at zoom N
            target_zoom: Target zoom level (N-1)
            output_dir: Directory to save downsampled tiles
            progress_callback: Optional callback(current, total, message)

        Returns:
            List of (tile_path, x, y, z) at target_zoom
        """
        # Group source tiles by parent tile coordinates
        parent_groups: dict[tuple[int, int], list[tuple[Path, int, int]]] = {}

        for tile_path, x, y, _z in source_tiles:
            # Calculate parent tile coordinates at target_zoom
            parent_x = x // 2
            parent_y = y // 2

            # Position within parent (0-1 for x and y: NW=0,0 NE=1,0 SW=0,1 SE=1,1)
            offset_x = x % 2
            offset_y = y % 2

            key = (parent_x, parent_y)
            if key not in parent_groups:
                parent_groups[key] = []

            parent_groups[key].append((tile_path, offset_x, offset_y))

        # Generate downsampled tiles
        downsampled_tiles = []
        total = len(parent_groups)

        for i, ((parent_x, parent_y), children) in enumerate(parent_groups.items()):
            if progress_callback:
                progress_callback(i, total, f"Downsampling to zoom {target_zoom}...")

            # Create 512x512 canvas (will downsample to 256x256)
            # Initialize with transparent background
            canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))

            # Place child tiles on canvas
            for tile_path, offset_x, offset_y in children:
                if not tile_path.exists():
                    logger.warning(f"Source tile not found: {tile_path}")
                    continue

                try:
                    child_img = Image.open(tile_path).convert("RGBA")
                    paste_x = offset_x * 256
                    paste_y = offset_y * 256
                    canvas.paste(child_img, (paste_x, paste_y))
                except Exception as e:
                    logger.error(f"Error loading tile {tile_path}: {e}")
                    continue

            # Downsample to 256x256 using high-quality Lanczos filter
            downsampled = canvas.resize((256, 256), Image.Resampling.LANCZOS)

            # Save downsampled tile
            output_path = output_dir / f"{target_zoom}_{parent_x}_{parent_y}.png"
            downsampled.save(output_path, "PNG")

            downsampled_tiles.append((output_path, parent_x, parent_y, target_zoom))

        if progress_callback:
            progress_callback(total, total, f"Completed zoom {target_zoom}")

        logger.info(f"Generated {len(downsampled_tiles)} tiles at zoom {target_zoom}")
        return downsampled_tiles

    @staticmethod
    def generate_lod_pyramid(
        max_zoom_tiles: list[tuple[Path, int, int, int]],
        max_zoom: int,
        min_zoom: int,
        output_dir: Path,
        progress_callback=None,
    ) -> dict[int, list[tuple[Path, int, int, int]]]:
        """
        Generate complete LOD pyramid from max zoom down to min zoom.

        Iterates from max_zoom-1 down to min_zoom, creating each zoom level
        by downsampling from the zoom level above it.

        Args:
            max_zoom_tiles: Tiles at maximum zoom level
            max_zoom: Maximum zoom level
            min_zoom: Minimum zoom level
            output_dir: Directory for output tiles
            progress_callback: Optional callback(current, total, message)

        Returns:
            Dictionary mapping zoom level to list of tiles at that level
        """
        pyramid = {max_zoom: max_zoom_tiles}

        current_tiles = max_zoom_tiles
        for zoom in range(max_zoom - 1, min_zoom - 1, -1):
            # Create zoom-specific directory
            zoom_dir = output_dir / f"zoom_{zoom}"
            zoom_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Downsampling from zoom {zoom + 1} to {zoom}...")

            # Downsample from current tiles to next zoom level
            downsampled = TileDownsampler.downsample_tile_level(current_tiles, zoom, zoom_dir, progress_callback)

            pyramid[zoom] = downsampled
            current_tiles = downsampled

        logger.info(f"Generated LOD pyramid with {len(pyramid)} zoom levels (zoom {min_zoom} to {max_zoom})")
        return pyramid
