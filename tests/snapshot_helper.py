"""Snapshot testing utilities for KMZ file comparison."""

import difflib
import hashlib
import shutil
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


class SnapshotAssertion:
    """Context manager for snapshot assertions."""

    def __init__(self, test_name: str, update_snapshots: bool = False):
        self.test_name = test_name
        self.update_snapshots = update_snapshots
        self.snapshot_path = SNAPSHOTS_DIR / f"{test_name}.kmz"
        self.differences: list[str] = []

    def assert_match(self, kmz_path: Path) -> None:
        """
        Assert that KMZ matches snapshot.

        Args:
            kmz_path: Path to generated KMZ file

        Raises:
            AssertionError: If KMZ doesn't match snapshot
        """
        if not kmz_path.exists():
            raise AssertionError(f"KMZ file not found: {kmz_path}")

        # Create snapshots directory if it doesn't exist
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        # If update mode or no snapshot exists, save as snapshot
        if self.update_snapshots or not self.snapshot_path.exists():
            shutil.copy(kmz_path, self.snapshot_path)
            if self.update_snapshots:
                pytest.skip(f"Snapshot updated: {self.test_name}")
            # If snapshot doesn't exist, create it and pass (don't skip)
            # This allows new tests to pass on first run
            return

        # Quick hash comparison
        current_hash = hash_file(kmz_path)
        snapshot_hash = hash_file(self.snapshot_path)

        if current_hash == snapshot_hash:
            # Perfect match!
            return

        # Hashes differ - extract and compare
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            current_dir = temp_path / "current"
            snapshot_dir = temp_path / "snapshot"

            extract_kmz(kmz_path, current_dir)
            extract_kmz(self.snapshot_path, snapshot_dir)

            self.differences = compare_directories(snapshot_dir, current_dir)

        if self.differences:
            error_msg = f"\n{'=' * 70}\nSnapshot mismatch for {self.test_name}\n{'=' * 70}\n"
            error_msg += "\n".join(self.differences)
            error_msg += f"\n{'=' * 70}\n"
            error_msg += "To update snapshot, run: pytest --update-snapshots\n"
            error_msg += f"Or delete: {self.snapshot_path}\n"
            raise AssertionError(error_msg)
