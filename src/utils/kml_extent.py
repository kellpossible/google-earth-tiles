"""Utility functions for calculating extents from KML files."""

import copy
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import pyproj

from src.models.extent import Extent

logger = logging.getLogger(__name__)

# KML namespace
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


def extract_coordinates_from_kml(kml_path: Path) -> list[tuple[float, float]]:
    """
    Extract all coordinate pairs from KML file.

    Args:
        kml_path: Path to KML file

    Returns:
        List of (lon, lat) tuples

    Raises:
        FileNotFoundError: If KML file doesn't exist
        ValueError: If KML is invalid or contains no coordinates
    """
    if not kml_path.exists():
        raise FileNotFoundError(f"KML file not found: {kml_path}")

    try:
        tree = ET.parse(kml_path)
        root = tree.getroot()

        coords = []

        # Find all <coordinates> elements
        # KML format: "lon,lat,alt lon,lat,alt ..." (space or newline separated)
        for coord_elem in root.findall(".//kml:coordinates", KML_NS):
            if coord_elem.text:
                text = coord_elem.text.strip()
                for point in text.split():
                    parts = point.split(",")
                    if len(parts) >= 2:
                        lon, lat = float(parts[0]), float(parts[1])
                        coords.append((lon, lat))

        if not coords:
            raise ValueError(f"No coordinates found in KML file: {kml_path}")

        return coords

    except ET.ParseError as e:
        raise ValueError(f"Invalid KML file: {e}") from e


def calculate_bbox(coords: list[tuple[float, float]]) -> Extent:
    """
    Calculate bounding box from coordinate list.

    Args:
        coords: List of (lon, lat) tuples

    Returns:
        Extent representing the bounding box
    """
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    return Extent(
        min_lon=min(lons),
        min_lat=min(lats),
        max_lon=max(lons),
        max_lat=max(lats),
    )


def apply_padding_meters(extent: Extent, padding_meters: float) -> Extent:
    """
    Apply uniform padding in meters to an extent.

    Uses WGS84 ellipsoid for accurate meter-to-degree conversion.
    Padding is applied equally to all four sides.

    Args:
        extent: Original extent
        padding_meters: Padding distance in meters (uniform on all sides)

    Returns:
        New extent with padding applied
    """
    if padding_meters <= 0:
        return extent.copy()

    # Use pyproj Geod for accurate geodesic calculations
    geod = pyproj.Geod(ellps="WGS84")

    # Calculate center point
    center_lon = (extent.min_lon + extent.max_lon) / 2
    center_lat = (extent.min_lat + extent.max_lat) / 2

    # Calculate new corners by moving padding_meters in each direction
    # North: azimuth 0°
    lon_n, lat_n, _ = geod.fwd(center_lon, extent.max_lat, 0, padding_meters)

    # South: azimuth 180°
    lon_s, lat_s, _ = geod.fwd(center_lon, extent.min_lat, 180, padding_meters)

    # East: azimuth 90°
    lon_e, lat_e, _ = geod.fwd(extent.max_lon, center_lat, 90, padding_meters)

    # West: azimuth 270°
    lon_w, lat_w, _ = geod.fwd(extent.min_lon, center_lat, 270, padding_meters)

    return Extent(
        min_lon=lon_w,
        min_lat=lat_s,
        max_lon=lon_e,
        max_lat=lat_n,
    )


def calculate_extent_from_kml(kml_path: Path, padding_meters: float = 0.0) -> Extent:
    """
    Calculate extent from KML file with optional padding.

    Args:
        kml_path: Path to KML file
        padding_meters: Optional padding in meters (default: 0)

    Returns:
        Extent with bounding box (optionally padded)

    Raises:
        FileNotFoundError: If KML file doesn't exist
        ValueError: If KML is invalid or contains no coordinates
    """
    coords = extract_coordinates_from_kml(kml_path)
    extent = calculate_bbox(coords)

    if padding_meters > 0:
        extent = apply_padding_meters(extent, padding_meters)

    return extent


def extract_metadata_from_kml(kml_path: Path) -> dict[str, str | None]:
    """
    Extract name and description metadata from KML file.

    Searches for:
    1. Document-level <name> and <description> in <Document> element
    2. Falls back to first <Placemark> <name> and <description> if Document has none
    3. Returns None for fields if not found

    Args:
        kml_path: Path to KML file

    Returns:
        Dictionary with 'name' and 'description' keys (values can be None)

    Raises:
        FileNotFoundError: If KML file doesn't exist
        ValueError: If KML is invalid
    """
    if not kml_path.exists():
        raise FileNotFoundError(f"KML file not found: {kml_path}")

    try:
        tree = ET.parse(kml_path)
        root = tree.getroot()

        name = None
        description = None

        # Strategy 1: Try Document-level metadata
        doc_elem = root.find(".//kml:Document", KML_NS)
        if doc_elem is not None:
            name_elem = doc_elem.find("kml:name", KML_NS)
            desc_elem = doc_elem.find("kml:description", KML_NS)

            if name_elem is not None and name_elem.text:
                name = name_elem.text.strip()
                if not name:  # Empty string after strip
                    name = None
            if desc_elem is not None and desc_elem.text:
                description = desc_elem.text.strip()
                if not description:  # Empty string after strip
                    description = None

        # Strategy 2: Fallback to first Placemark if Document had no metadata
        if name is None or description is None:
            placemark = root.find(".//kml:Placemark", KML_NS)
            if placemark is not None:
                if name is None:
                    name_elem = placemark.find("kml:name", KML_NS)
                    if name_elem is not None and name_elem.text:
                        name = name_elem.text.strip()
                        if not name:  # Empty string after strip
                            name = None

                if description is None:
                    desc_elem = placemark.find("kml:description", KML_NS)
                    if desc_elem is not None and desc_elem.text:
                        description = desc_elem.text.strip()
                        if not description:  # Empty string after strip
                            description = None

        return {
            "name": name,
            "description": description,
        }

    except ET.ParseError as e:
        raise ValueError(f"Invalid KML file: {e}") from e


def extract_kml_features(kml_path: Path) -> list[ET.Element]:
    """
    Extract feature elements from KML Document for merging.

    Extracts all child elements of Document except name/description:
    - Placemarks, Folders, GroundOverlays, ScreenOverlays, etc.
    - Styles, StyleMaps
    - Any other KML features

    Returns deep copies to prevent mutation.

    Args:
        kml_path: Path to KML file

    Returns:
        List of ElementTree Elements representing KML features

    Raises:
        FileNotFoundError: If KML file doesn't exist
        ValueError: If KML is invalid
    """
    if not kml_path.exists():
        raise FileNotFoundError(f"KML file not found: {kml_path}")

    try:
        tree = ET.parse(kml_path)
        root = tree.getroot()

        # Find Document element
        doc_elem = root.find(".//kml:Document", KML_NS)

        if doc_elem is None:
            logger.warning(f"No Document element found in KML file: {kml_path}")
            return []

        # Extract all features (skip Document-level name/description)
        features = []
        skip_tags = [f"{{{KML_NS['kml']}}}name", f"{{{KML_NS['kml']}}}description"]

        for child in doc_elem:
            if child.tag not in skip_tags:
                # Deep copy to avoid modifying original
                features.append(copy.deepcopy(child))

        return features

    except ET.ParseError as e:
        raise ValueError(f"Invalid KML file: {e}") from e
