"""Tests for KML utility functions."""

from pathlib import Path

import pytest

from src.utils.kml_extent import extract_kml_features, extract_metadata_from_kml


def test_extract_metadata_from_document_level():
    """Test extracting metadata from Document-level name and description."""
    kml_path = Path(__file__).parent / "fixtures" / "test_extent_with_metadata.kml"

    metadata = extract_metadata_from_kml(kml_path)

    assert metadata["name"] == "Test Study Area"
    assert metadata["description"] == "This is a test description for the study area"


def test_extract_metadata_fallback_to_placemark():
    """Test fallback to Placemark-level metadata when Document has none."""
    kml_path = Path(__file__).parent / "fixtures" / "test_extent_placemark_metadata.kml"

    metadata = extract_metadata_from_kml(kml_path)

    assert metadata["name"] == "Placemark Name Only"
    assert metadata["description"] == "Placemark description only"


def test_extract_metadata_no_metadata():
    """Test extraction when no metadata is present."""
    kml_path = Path(__file__).parent / "fixtures" / "test_extent_no_metadata.kml"

    metadata = extract_metadata_from_kml(kml_path)

    assert metadata["name"] is None
    assert metadata["description"] is None


def test_extract_metadata_file_not_found():
    """Test error handling when KML file doesn't exist."""
    kml_path = Path("/nonexistent/file.kml")

    with pytest.raises(FileNotFoundError):
        extract_metadata_from_kml(kml_path)


def test_extract_kml_features_with_styles_and_folders():
    """Test extracting features including Styles, Folders, and Placemarks."""
    kml_path = Path(__file__).parent / "fixtures" / "test_extent_with_features.kml"

    features = extract_kml_features(kml_path)

    # Should have Style, Folder, and Placemark (excluding name/description)
    assert len(features) == 3

    # Verify features are ElementTree Elements
    import xml.etree.ElementTree as ET
    assert all(isinstance(f, ET.Element) for f in features)

    # Get tags (namespace-qualified)
    tags = [f.tag for f in features]
    kml_ns = "{http://www.opengis.net/kml/2.2}"

    # Should have Style, Folder, and Placemark
    assert f"{kml_ns}Style" in tags
    assert f"{kml_ns}Folder" in tags
    assert f"{kml_ns}Placemark" in tags


def test_extract_kml_features_excludes_name_description():
    """Test that name and description are excluded from features."""
    kml_path = Path(__file__).parent / "fixtures" / "test_extent_with_metadata.kml"

    features = extract_kml_features(kml_path)

    # Get tags
    tags = [f.tag for f in features]
    kml_ns = "{http://www.opengis.net/kml/2.2}"

    # Should not contain name or description
    assert f"{kml_ns}name" not in tags
    assert f"{kml_ns}description" not in tags

    # Should contain Placemark
    assert f"{kml_ns}Placemark" in tags


def test_extract_kml_features_file_not_found():
    """Test error handling when KML file doesn't exist."""
    kml_path = Path("/nonexistent/file.kml")

    with pytest.raises(FileNotFoundError):
        extract_kml_features(kml_path)


def test_extract_kml_features_deep_copy():
    """Test that extracted features are deep copies."""
    kml_path = Path(__file__).parent / "fixtures" / "test_extent_with_features.kml"

    features1 = extract_kml_features(kml_path)
    features2 = extract_kml_features(kml_path)

    # Should be equal in content but different objects
    assert len(features1) == len(features2)
    assert features1 is not features2
    assert features1[0] is not features2[0]
