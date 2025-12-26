"""MBTiles format generator."""

import logging
import sqlite3
from pathlib import Path

from src.core.base_tile_generator import BaseTileGenerator
from src.core.tile_calculator import TileCalculator
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition
from src.utils.image_encoding import ImageEncoder

logger = logging.getLogger(__name__)


class MBTilesGenerator(BaseTileGenerator):
    """Generator for MBTiles format databases.

    Implements the MBTiles 1.3 specification:
    https://github.com/mapbox/mbtiles-spec/blob/master/1.3/spec.md

    MBTiles uses the TMS (Tile Map Service) coordinate system with Y-axis
    inverted compared to XYZ. This generator handles the conversion automatically.
    """

    @staticmethod
    def create_database_schema(conn: sqlite3.Connection) -> None:
        """Create MBTiles 1.3 schema with metadata and tiles tables.

        Args:
            conn: SQLite database connection
        """
        cursor = conn.cursor()

        # Metadata table: key-value pairs for tileset information
        cursor.execute("""
            CREATE TABLE metadata (
                name TEXT,
                value TEXT
            )
        """)

        # Tiles table: stores tile images as BLOBs
        cursor.execute("""
            CREATE TABLE tiles (
                zoom_level INTEGER,
                tile_column INTEGER,
                tile_row INTEGER,
                tile_data BLOB
            )
        """)

        # Unique index on tile coordinates
        cursor.execute("""
            CREATE UNIQUE INDEX tile_index ON tiles
            (zoom_level, tile_column, tile_row)
        """)

        conn.commit()
        logger.info("Created MBTiles schema")

    @staticmethod
    def xyz_to_tms(x: int, y: int, zoom: int) -> tuple[int, int]:
        """Convert XYZ coordinates to TMS coordinates.

        MBTiles uses TMS with Y-axis inverted from standard XYZ.
        Formula: tms_y = (2^zoom - 1) - xyz_y

        Args:
            x: Tile X coordinate (XYZ)
            y: Tile Y coordinate (XYZ)
            zoom: Zoom level

        Returns:
            Tuple of (tms_x, tms_y) where tms_y is inverted
        """
        tms_y = (2**zoom - 1) - y
        return (x, tms_y)

    def populate_metadata(
        self,
        conn: sqlite3.Connection,
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        image_format: str,
        metadata_config: dict,
    ) -> None:
        """Populate metadata table with required and optional fields.

        Args:
            conn: SQLite database connection
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            image_format: "png" or "jpg"
            metadata_config: Dict with name, description, attribution, type
        """
        cursor = conn.cursor()

        # Required metadata per MBTiles spec
        metadata = {
            "name": metadata_config.get("name", "Tile Export"),
            "format": image_format,  # "png" or "jpg"
        }

        # Recommended metadata
        metadata["bounds"] = f"{extent.min_lon},{extent.min_lat},{extent.max_lon},{extent.max_lat}"
        center_lon = (extent.min_lon + extent.max_lon) / 2
        center_lat = (extent.min_lat + extent.max_lat) / 2
        metadata["center"] = f"{center_lon},{center_lat},{max_zoom}"
        metadata["minzoom"] = str(min_zoom)
        metadata["maxzoom"] = str(max_zoom)

        # Optional metadata (only include if provided)
        for key in ["description", "attribution", "type"]:
            value = metadata_config.get(key)
            if value:
                metadata[key] = value

        # Insert all metadata
        for name, value in metadata.items():
            cursor.execute("INSERT INTO metadata (name, value) VALUES (?, ?)", (name, value))

        conn.commit()
        logger.info(f"Populated metadata with {len(metadata)} fields")

    async def generate_mbtiles(
        self,
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
        image_format: str,
        metadata_config: dict,
        jpeg_quality: int = 80,
    ) -> Path:
        """Generate MBTiles database with composited layers.

        Args:
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of enabled layer compositions
            image_format: "png" or "jpg"
            metadata_config: Metadata configuration dict
            jpeg_quality: JPEG quality 1-100 (only used if format is jpg)

        Returns:
            Path to created .mbtiles file
        """
        logger.info(f"Generating MBTiles file: {self.output_path}")
        logger.info(f"Extent: {extent.min_lon:.6f},{extent.min_lat:.6f} to {extent.max_lon:.6f},{extent.max_lat:.6f}")
        logger.info(f"Zoom range: {min_zoom}-{max_zoom}, Format: {image_format}")

        # Create database and schema
        conn = sqlite3.connect(self.output_path)
        self.create_database_schema(conn)
        self.populate_metadata(conn, extent, min_zoom, max_zoom, image_format, metadata_config)

        try:
            # Calculate total tiles for progress tracking
            total_tiles = sum(
                TileCalculator.estimate_tile_count(extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom)
                for zoom in range(min_zoom, max_zoom + 1)
            )

            processed = 0
            cursor = conn.cursor()

            # Generate tiles for each zoom level
            for zoom in range(min_zoom, max_zoom + 1):
                tiles_at_zoom = TileCalculator.get_tiles_in_extent(
                    extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, zoom
                )

                logger.info(f"Processing zoom {zoom}: {len(tiles_at_zoom)} tiles")

                for x, y in tiles_at_zoom:
                    # Composite tile (returns PNG bytes from compositor)
                    tile_data_png = await self.compositor.composite_tile(x, y, zoom, layer_compositions)

                    if tile_data_png:
                        # Encode to target format
                        tile_data = ImageEncoder.encode_tile(tile_data_png, image_format, jpeg_quality)

                        # Convert to TMS coordinates
                        tms_x, tms_y = self.xyz_to_tms(x, y, zoom)

                        # Insert into database
                        cursor.execute(
                            "INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)",
                            (zoom, tms_x, tms_y, tile_data),
                        )

                    processed += 1
                    if self.progress_callback:
                        self.progress_callback(processed, total_tiles, f"Inserting tile {processed}/{total_tiles}...")

                # Commit per zoom level for progress checkpoints
                conn.commit()
                logger.info(f"Completed zoom level {zoom}")

            logger.info(f"Created MBTiles file: {self.output_path} ({total_tiles} tiles)")
            return self.output_path

        finally:
            conn.close()
            await self.close()
