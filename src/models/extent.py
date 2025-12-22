"""Data model for geographic extents."""

from dataclasses import dataclass
from typing import Dict

from src.core.config import JAPAN_REGION_BOUNDS


@dataclass
class Extent:
    """Geographic extent defined by lat/lon bounds."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def is_valid(self) -> bool:
        """
        Check if extent has valid bounds.

        Returns:
            True if min values are less than max values
        """
        return (self.min_lon < self.max_lon and
                self.min_lat < self.max_lat and
                -180 <= self.min_lon <= 180 and
                -180 <= self.max_lon <= 180 and
                -90 <= self.min_lat <= 90 and
                -90 <= self.max_lat <= 90)

    def is_within_japan_region(self) -> bool:
        """
        Check if extent is within the Japan region where WMTS tiles are available.

        Returns:
            True if extent overlaps with valid WMTS coverage area
        """
        # Check if there's any overlap with Japan region
        overlaps = not (
            self.max_lon < JAPAN_REGION_BOUNDS['min_lon'] or
            self.min_lon > JAPAN_REGION_BOUNDS['max_lon'] or
            self.max_lat < JAPAN_REGION_BOUNDS['min_lat'] or
            self.min_lat > JAPAN_REGION_BOUNDS['max_lat']
        )
        return overlaps

    def is_fully_within_japan_region(self) -> bool:
        """
        Check if extent is fully contained within Japan region.

        Returns:
            True if entire extent is within valid WMTS coverage area
        """
        return (
            self.min_lon >= JAPAN_REGION_BOUNDS['min_lon'] and
            self.max_lon <= JAPAN_REGION_BOUNDS['max_lon'] and
            self.min_lat >= JAPAN_REGION_BOUNDS['min_lat'] and
            self.max_lat <= JAPAN_REGION_BOUNDS['max_lat']
        )

    def to_dict(self) -> Dict[str, float]:
        """
        Convert extent to dictionary.

        Returns:
            Dictionary with min_lon, min_lat, max_lon, max_lat keys
        """
        return {
            'min_lon': self.min_lon,
            'min_lat': self.min_lat,
            'max_lon': self.max_lon,
            'max_lat': self.max_lat,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'Extent':
        """
        Create extent from dictionary.

        Args:
            data: Dictionary with min_lon, min_lat, max_lon, max_lat keys

        Returns:
            Extent instance
        """
        return cls(
            min_lon=data['min_lon'],
            min_lat=data['min_lat'],
            max_lon=data['max_lon'],
            max_lat=data['max_lat'],
        )
