"""Tile calculation and coordinate conversion utilities."""

import math


class TileCalculator:
    """Utilities for tile math and coordinate conversions."""

    @staticmethod
    def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
        """
        Convert latitude/longitude to tile coordinates.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            zoom: Zoom level

        Returns:
            Tuple of (x, y) tile coordinates
        """
        n = 2.0**zoom
        x = int((lon + 180.0) / 360.0 * n)

        lat_rad = math.radians(lat)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)

        return (x, y)

    @staticmethod
    def tile_to_lat_lon_bounds(x: int, y: int, zoom: int) -> dict[str, float]:
        """
        Convert tile coordinates to WGS84 lat/lon bounds.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            zoom: Zoom level

        Returns:
            Dictionary with 'north', 'south', 'east', 'west' bounds in degrees
        """
        n = 2.0**zoom

        # Northwest corner
        lon_west = x / n * 360.0 - 180.0
        lat_north_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_north = math.degrees(lat_north_rad)

        # Southeast corner
        lon_east = (x + 1) / n * 360.0 - 180.0
        lat_south_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
        lat_south = math.degrees(lat_south_rad)

        return {"north": lat_north, "south": lat_south, "east": lon_east, "west": lon_west}

    @staticmethod
    def get_tiles_in_extent(
        min_lon: float, min_lat: float, max_lon: float, max_lat: float, zoom: int
    ) -> list[tuple[int, int]]:
        """
        Get all tile coordinates within a geographic extent.

        Args:
            min_lon: Minimum longitude
            min_lat: Minimum latitude
            max_lon: Maximum longitude
            max_lat: Maximum latitude
            zoom: Zoom level

        Returns:
            List of (x, y) tile coordinate tuples
        """
        # Get tile coordinates for all four corners
        x_nw, y_nw = TileCalculator.lat_lon_to_tile(max_lat, min_lon, zoom)
        x_ne, y_ne = TileCalculator.lat_lon_to_tile(max_lat, max_lon, zoom)
        x_sw, y_sw = TileCalculator.lat_lon_to_tile(min_lat, min_lon, zoom)
        x_se, y_se = TileCalculator.lat_lon_to_tile(min_lat, max_lon, zoom)

        # Find actual min/max tile coordinates
        x_min = min(x_nw, x_ne, x_sw, x_se)
        x_max = max(x_nw, x_ne, x_sw, x_se)
        y_min = min(y_nw, y_ne, y_sw, y_se)
        y_max = max(y_nw, y_ne, y_sw, y_se)

        # Generate all tiles in the range
        tiles = []
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                tiles.append((x, y))

        return tiles

    @staticmethod
    def estimate_tile_count(min_lon: float, min_lat: float, max_lon: float, max_lat: float, zoom: int) -> int:
        """
        Estimate the number of tiles in an extent.

        Args:
            min_lon: Minimum longitude
            min_lat: Minimum latitude
            max_lon: Maximum longitude
            max_lat: Maximum latitude
            zoom: Zoom level

        Returns:
            Number of tiles
        """
        # Get tile coordinates for all four corners
        x_nw, y_nw = TileCalculator.lat_lon_to_tile(max_lat, min_lon, zoom)
        x_ne, y_ne = TileCalculator.lat_lon_to_tile(max_lat, max_lon, zoom)
        x_sw, y_sw = TileCalculator.lat_lon_to_tile(min_lat, min_lon, zoom)
        x_se, y_se = TileCalculator.lat_lon_to_tile(min_lat, max_lon, zoom)

        # Find actual min/max tile coordinates
        x_min = min(x_nw, x_ne, x_sw, x_se)
        x_max = max(x_nw, x_ne, x_sw, x_se)
        y_min = min(y_nw, y_ne, y_sw, y_se)
        y_max = max(y_nw, y_ne, y_sw, y_se)

        width = x_max - x_min + 1
        height = y_max - y_min + 1

        return width * height

    @staticmethod
    def estimate_download_size(tile_count: int, layer_extension: str) -> float:
        """
        Estimate download size in megabytes.

        Args:
            tile_count: Number of tiles
            layer_extension: File extension ('png' or 'jpg')

        Returns:
            Estimated size in MB
        """
        # Average tile sizes (approximate)
        avg_size_kb = {
            "png": 50,  # PNG tiles average ~50KB
            "jpg": 80,  # JPG tiles average ~80KB
        }

        size_kb = tile_count * avg_size_kb.get(layer_extension, 50)
        return size_kb / 1024  # Convert to MB

    @staticmethod
    def calculate_chunks_at_zoom(
        min_lon: float, min_lat: float, max_lon: float, max_lat: float, zoom: int, chunk_size: int = 8
    ) -> int:
        """
        Calculate number of chunks needed for extent at zoom level.

        A chunk represents an NxN grid of 256x256 tiles merged into a single image.
        Default chunk_size=8 creates 2048x2048 pixel images (8*256=2048).

        Args:
            min_lon: Minimum longitude
            min_lat: Minimum latitude
            max_lon: Maximum longitude
            max_lat: Maximum latitude
            zoom: Zoom level
            chunk_size: Number of tiles per chunk (default 8 for 2048x2048)

        Returns:
            Number of chunks needed to cover the extent
        """
        # Get all tiles at this zoom
        tiles = TileCalculator.get_tiles_in_extent(min_lon, min_lat, max_lon, max_lat, zoom)

        if not tiles:
            return 0

        # Get tile coordinate bounds
        x_coords = [x for x, y in tiles]
        y_coords = [y for x, y in tiles]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # Calculate chunks (ceiling division by chunk_size)
        chunk_width = math.ceil((x_max - x_min + 1) / chunk_size)
        chunk_height = math.ceil((y_max - y_min + 1) / chunk_size)

        return chunk_width * chunk_height

    @staticmethod
    def find_max_web_compatible_zoom(
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        layer_count: int,
        max_chunks_per_layer: int = 500,
        chunk_size: int = 8,
    ) -> int:
        """
        Find largest zoom level that stays under chunk limit for web compatibility.

        Google Earth Web has a limit of ~10,000 features per import. We use a
        conservative limit of 500 chunks per layer to stay well under this limit
        while accounting for multiple layers and KML overhead.

        Args:
            min_lon: Minimum longitude
            min_lat: Minimum latitude
            max_lon: Maximum longitude
            max_lat: Maximum latitude
            layer_count: Number of enabled layers (including separate layers)
            max_chunks_per_layer: Maximum chunks allowed per layer (default 500)
            chunk_size: Number of tiles per chunk (default 8)

        Returns:
            Maximum zoom level that fits within limits (minimum 2)
        """
        # Start from zoom 18 and work down
        for zoom in range(18, 1, -1):
            chunks_needed = TileCalculator.calculate_chunks_at_zoom(
                min_lon, min_lat, max_lon, max_lat, zoom, chunk_size
            )

            # Check if this zoom level fits under the per-layer limit
            if chunks_needed <= max_chunks_per_layer:
                return zoom

        # If nothing fits, return minimum
        return 2

    @staticmethod
    def get_chunk_grid(tiles: list[tuple[int, int]], zoom: int, chunk_size: int = 8) -> list[dict]:
        """
        Group tiles into NxN chunks and calculate their geographic bounds.

        Args:
            tiles: List of (x, y) tile coordinates at a zoom level
            zoom: Zoom level (needed for bounds calculation)
            chunk_size: Number of tiles per chunk dimension (default 8)

        Returns:
            List of chunk dictionaries with:
            - chunk_x: Chunk X coordinate
            - chunk_y: Chunk Y coordinate
            - tiles: List of (x, y) tile coordinates in this chunk
            - bounds: Geographic bounds dict with north/south/east/west
        """
        if not tiles:
            return []

        # Find tile bounds
        x_coords = [x for x, y in tiles]
        y_coords = [y for x, y in tiles]
        x_min, y_min = min(x_coords), min(y_coords)

        # Group tiles by chunk
        chunk_map = {}
        for x, y in tiles:
            chunk_x = (x - x_min) // chunk_size
            chunk_y = (y - y_min) // chunk_size
            chunk_key = (chunk_x, chunk_y)

            if chunk_key not in chunk_map:
                chunk_map[chunk_key] = []
            chunk_map[chunk_key].append((x, y))

        # Build chunk list with bounds
        chunks = []
        for (chunk_x, chunk_y), chunk_tiles in chunk_map.items():
            # Calculate chunk bounds from constituent tiles
            chunk_bounds = TileCalculator.calculate_chunk_bounds(chunk_tiles, zoom)

            chunks.append({"chunk_x": chunk_x, "chunk_y": chunk_y, "tiles": chunk_tiles, "bounds": chunk_bounds})

        return chunks

    @staticmethod
    def calculate_chunk_bounds(tiles: list[tuple[int, int]], zoom: int) -> dict[str, float]:
        """
        Calculate geographic bounds for a chunk from its constituent tiles.

        Args:
            tiles: List of (x, y) tile coordinates
            zoom: Zoom level

        Returns:
            Dictionary with 'north', 'south', 'east', 'west' bounds in degrees
        """
        if not tiles:
            return {"north": 0.0, "south": 0.0, "east": 0.0, "west": 0.0}

        x_coords = [x for x, y in tiles]
        y_coords = [y for x, y in tiles]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # Get bounds of northwest and southeast corners of the chunk
        nw_bounds = TileCalculator.tile_to_lat_lon_bounds(x_min, y_min, zoom)
        se_bounds = TileCalculator.tile_to_lat_lon_bounds(x_max, y_max, zoom)

        return {
            "north": nw_bounds["north"],
            "south": se_bounds["south"],
            "east": se_bounds["east"],
            "west": nw_bounds["west"],
        }
