"""Snapshot testing utilities for KMZ and MBTiles file comparison."""

import difflib
import hashlib
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest

# Directory to store snapshot files
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def hash_file(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def is_text_file(file_path: Path) -> bool:
    """Check if file is likely a text file."""
    text_extensions = {".kml", ".xml", ".txt", ".html", ".css", ".js", ".json", ".yaml", ".yml"}
    return file_path.suffix.lower() in text_extensions


def compare_text_files(file1: Path, file2: Path) -> tuple[bool, str]:
    """
    Compare two text files and return diff.

    Returns:
        (is_same, diff_text)
    """
    try:
        with open(file1, encoding="utf-8") as f1:
            lines1 = f1.readlines()
        with open(file2, encoding="utf-8") as f2:
            lines2 = f2.readlines()

        if lines1 == lines2:
            return True, ""

        # Generate unified diff
        diff = difflib.unified_diff(
            lines1,
            lines2,
            fromfile=f"snapshot/{file1.name}",
            tofile=f"current/{file2.name}",
            lineterm="",
        )
        diff_text = "\n".join(diff)
        return False, diff_text
    except UnicodeDecodeError:
        # Fall back to binary comparison
        return False, "Files differ (binary or encoding issue)"


def compare_binary_files(file1: Path, file2: Path) -> tuple[bool, str]:
    """
    Compare two binary files.

    Returns:
        (is_same, message)
    """
    hash1 = hash_file(file1)
    hash2 = hash_file(file2)

    if hash1 == hash2:
        return True, ""

    size1 = file1.stat().st_size
    size2 = file2.stat().st_size

    return False, f"Binary files differ (snapshot: {size1} bytes, current: {size2} bytes)"


def compare_directories(dir1: Path, dir2: Path, prefix: str = "") -> list[str]:
    """
    Recursively compare two directories and return list of differences.

    Returns:
        List of difference messages
    """
    differences = []

    # Get all files in both directories
    files1 = {p.relative_to(dir1) for p in dir1.rglob("*") if p.is_file()}
    files2 = {p.relative_to(dir2) for p in dir2.rglob("*") if p.is_file()}

    # Check for missing/extra files
    only_in_1 = files1 - files2
    only_in_2 = files2 - files1
    common = files1 & files2

    for rel_path in sorted(only_in_1):
        differences.append(f"{prefix}MISSING in current: {rel_path}")

    for rel_path in sorted(only_in_2):
        differences.append(f"{prefix}EXTRA in current: {rel_path}")

    # Compare common files
    for rel_path in sorted(common):
        file1 = dir1 / rel_path
        file2 = dir2 / rel_path

        if is_text_file(file1):
            is_same, diff = compare_text_files(file1, file2)
            if not is_same:
                differences.append(f"{prefix}DIFF {rel_path}:")
                differences.append(diff)
        else:
            is_same, message = compare_binary_files(file1, file2)
            if not is_same:
                differences.append(f"{prefix}DIFF {rel_path}: {message}")

    return differences


def extract_kmz(kmz_path: Path, extract_dir: Path) -> None:
    """Extract KMZ to directory."""
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(kmz_path, "r") as kmz:
        kmz.extractall(extract_dir)


def extract_mbtiles_data(mbtiles_path: Path) -> dict:
    """Extract MBTiles database contents into comparable format.

    Args:
        mbtiles_path: Path to .mbtiles file

    Returns:
        Dictionary with:
            - metadata: Dict of metadata key-value pairs
            - tiles: Dict mapping (zoom, x, y) -> tile_hash
            - tile_count: Total number of tiles
            - zoom_levels: Set of zoom levels present
    """
    conn = sqlite3.connect(mbtiles_path)
    cursor = conn.cursor()

    # Extract metadata
    cursor.execute("SELECT name, value FROM metadata ORDER BY name")
    metadata = {row[0]: row[1] for row in cursor.fetchall()}

    # Extract tiles (hash the blob data for comparison)
    cursor.execute("SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles ORDER BY zoom_level, tile_column, tile_row")
    tiles = {}
    zoom_levels = set()

    for row in cursor.fetchall():
        zoom, x, y, tile_data = row
        tile_hash = hashlib.sha256(tile_data).hexdigest()[:16]  # First 16 chars of hash
        tiles[(zoom, x, y)] = tile_hash
        zoom_levels.add(zoom)

    conn.close()

    return {
        "metadata": metadata,
        "tiles": tiles,
        "tile_count": len(tiles),
        "zoom_levels": sorted(zoom_levels),
    }


def compare_mbtiles(mbtiles1: Path, mbtiles2: Path) -> list[str]:
    """Compare two MBTiles databases and return list of differences.

    Args:
        mbtiles1: Path to first MBTiles (snapshot)
        mbtiles2: Path to second MBTiles (current)

    Returns:
        List of difference messages
    """
    differences = []

    # Extract data from both databases
    data1 = extract_mbtiles_data(mbtiles1)
    data2 = extract_mbtiles_data(mbtiles2)

    # Compare metadata
    metadata1 = data1["metadata"]
    metadata2 = data2["metadata"]

    # Check for missing/extra metadata keys
    keys1 = set(metadata1.keys())
    keys2 = set(metadata2.keys())

    for key in sorted(keys1 - keys2):
        differences.append(f"MISSING metadata in current: {key} = {metadata1[key]}")

    for key in sorted(keys2 - keys1):
        differences.append(f"EXTRA metadata in current: {key} = {metadata2[key]}")

    # Compare common metadata values
    for key in sorted(keys1 & keys2):
        if metadata1[key] != metadata2[key]:
            differences.append(f"DIFF metadata '{key}':")
            differences.append(f"  Snapshot: {metadata1[key]}")
            differences.append(f"  Current:  {metadata2[key]}")

    # Compare tile counts and zoom levels
    if data1["tile_count"] != data2["tile_count"]:
        differences.append(f"DIFF tile count: snapshot={data1['tile_count']}, current={data2['tile_count']}")

    if data1["zoom_levels"] != data2["zoom_levels"]:
        differences.append(f"DIFF zoom levels: snapshot={data1['zoom_levels']}, current={data2['zoom_levels']}")

    # Compare individual tiles
    tiles1 = data1["tiles"]
    tiles2 = data2["tiles"]

    coords1 = set(tiles1.keys())
    coords2 = set(tiles2.keys())

    missing_tiles = coords1 - coords2
    extra_tiles = coords2 - coords1

    if missing_tiles:
        sample = sorted(missing_tiles)[:5]
        differences.append(f"MISSING {len(missing_tiles)} tiles in current (sample): {sample}")

    if extra_tiles:
        sample = sorted(extra_tiles)[:5]
        differences.append(f"EXTRA {len(extra_tiles)} tiles in current (sample): {sample}")

    # Compare common tiles (by hash)
    differing_tiles = []
    for coord in sorted(coords1 & coords2):
        if tiles1[coord] != tiles2[coord]:
            differing_tiles.append(coord)

    if differing_tiles:
        sample = differing_tiles[:5]
        differences.append(f"DIFF {len(differing_tiles)} tiles have different content (sample): {sample}")
        for coord in sample:
            differences.append(f"  Tile {coord}: snapshot_hash={tiles1[coord]}, current_hash={tiles2[coord]}")

    return differences


class SnapshotAssertion:
    """Context manager for snapshot assertions supporting KMZ and MBTiles formats."""

    def __init__(self, test_name: str, update_snapshots: bool = False):
        self.test_name = test_name
        self.update_snapshots = update_snapshots
        self.snapshot_path: Path | None = None  # Will be set based on file type
        self.differences: list[str] = []

    def assert_match(self, file_path: Path) -> None:
        """
        Assert that file matches snapshot (supports KMZ and MBTiles).

        Args:
            file_path: Path to generated file (KMZ or MBTiles)

        Raises:
            AssertionError: If file doesn't match snapshot
        """
        if not file_path.exists():
            raise AssertionError(f"File not found: {file_path}")

        # Detect file type and set snapshot path
        file_ext = file_path.suffix.lower()
        if file_ext not in [".kmz", ".mbtiles"]:
            raise AssertionError(f"Unsupported file type: {file_ext} (must be .kmz or .mbtiles)")

        self.snapshot_path = SNAPSHOTS_DIR / f"{self.test_name}{file_ext}"

        # Create snapshots directory if it doesn't exist
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        # If update mode or no snapshot exists, save as snapshot
        if self.update_snapshots or not self.snapshot_path.exists():
            shutil.copy(file_path, self.snapshot_path)
            if self.update_snapshots:
                pytest.skip(f"Snapshot updated: {self.test_name}")
            # If snapshot doesn't exist, create it and pass (don't skip)
            # This allows new tests to pass on first run
            return

        # Quick hash comparison
        current_hash = hash_file(file_path)
        snapshot_hash = hash_file(self.snapshot_path)

        if current_hash == snapshot_hash:
            # Perfect match!
            return

        # Hashes differ - perform format-specific comparison
        if file_ext == ".kmz":
            self._compare_kmz(file_path)
        elif file_ext == ".mbtiles":
            self._compare_mbtiles(file_path)

        if self.differences:
            error_msg = f"\n{'=' * 70}\nSnapshot mismatch for {self.test_name}\n{'=' * 70}\n"
            error_msg += "\n".join(self.differences)
            error_msg += f"\n{'=' * 70}\n"
            error_msg += "To update snapshot, run: pytest --update-snapshots\n"
            error_msg += f"Or delete: {self.snapshot_path}\n"
            raise AssertionError(error_msg)

    def _compare_kmz(self, kmz_path: Path) -> None:
        """Compare KMZ files by extracting and comparing contents."""
        import tempfile

        assert self.snapshot_path is not None, "snapshot_path must be set before comparing"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            current_dir = temp_path / "current"
            snapshot_dir = temp_path / "snapshot"

            extract_kmz(kmz_path, current_dir)
            extract_kmz(self.snapshot_path, snapshot_dir)

            self.differences = compare_directories(snapshot_dir, current_dir)

    def _compare_mbtiles(self, mbtiles_path: Path) -> None:
        """Compare MBTiles files by comparing database contents."""
        assert self.snapshot_path is not None, "snapshot_path must be set before comparing"
        self.differences = compare_mbtiles(self.snapshot_path, mbtiles_path)
