"""Tile calculation and coordinate conversion utilities."""

import math
from typing import Dict, List, Tuple


class TileCalculator:
    """Utilities for tile math and coordinate conversions."""

    @staticmethod
    def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
        """
        Convert latitude/longitude to tile coordinates.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            zoom: Zoom level

        Returns:
            Tuple of (x, y) tile coordinates
        """
        n = 2.0 ** zoom
        x = int((lon + 180.0) / 360.0 * n)

        lat_rad = math.radians(lat)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)

        return (x, y)

    @staticmethod
    def tile_to_lat_lon_bounds(x: int, y: int, zoom: int) -> Dict[str, float]:
        """
        Convert tile coordinates to WGS84 lat/lon bounds.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            zoom: Zoom level

        Returns:
            Dictionary with 'north', 'south', 'east', 'west' bounds in degrees
        """
        n = 2.0 ** zoom

        # Northwest corner
        lon_west = x / n * 360.0 - 180.0
        lat_north_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_north = math.degrees(lat_north_rad)

        # Southeast corner
        lon_east = (x + 1) / n * 360.0 - 180.0
        lat_south_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
        lat_south = math.degrees(lat_south_rad)

        return {
            'north': lat_north,
            'south': lat_south,
            'east': lon_east,
            'west': lon_west
        }

    @staticmethod
    def get_tiles_in_extent(min_lon: float, min_lat: float,
                           max_lon: float, max_lat: float,
                           zoom: int) -> List[Tuple[int, int]]:
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
    def estimate_tile_count(min_lon: float, min_lat: float,
                           max_lon: float, max_lat: float,
                           zoom: int) -> int:
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
            'png': 50,  # PNG tiles average ~50KB
            'jpg': 80,  # JPG tiles average ~80KB
        }

        size_kb = tile_count * avg_size_kb.get(layer_extension, 50)
        return size_kb / 1024  # Convert to MB
