"""Configuration model for extent specification (lat/lon or file-based)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.models.extent import Extent


@dataclass
class ExtentConfig:
    """Configuration for extent specification (lat/lon or file-based)."""

    mode: Literal["latlon", "file"]

    # For latlon mode
    extent: Extent | None = None

    # For file mode
    file_path: Path | None = None
    padding_meters: float = 0.0

    # Cached resolved extent (calculated from KML + padding)
    _resolved_extent: Extent | None = None

    # Cached metadata extracted from KML file
    _extracted_metadata: dict[str, str | None] | None = None

    def get_extent(self) -> Extent:
        """
        Get the resolved extent for this configuration.

        Returns:
            Resolved extent

        Raises:
            ValueError: If extent is not available for the current mode
        """
        if self.mode == "latlon":
            if self.extent is None:
                raise ValueError("Lat/lon mode requires extent")
            return self.extent
        else:  # file mode
            if self._resolved_extent is None:
                raise ValueError("File-based extent not yet resolved")
            return self._resolved_extent

    def get_extracted_metadata(self) -> dict[str, str | None]:
        """
        Get metadata extracted from KML file.

        Returns:
            Dictionary with 'name' and 'description' keys (values can be None)
            Empty dict if mode is not 'file' or no extraction performed
        """
        if self.mode != "file":
            return {}

        if self._extracted_metadata is None:
            return {}

        return self._extracted_metadata

    def to_dict(self) -> dict:
        """
        Serialize for YAML config.

        Returns:
            Dictionary representation for YAML serialization
        """
        result = {"type": self.mode}

        if self.mode == "latlon":
            if self.extent is not None:
                result.update(self.extent.to_dict())
        else:  # file mode
            if self.file_path is not None:
                result["file"] = str(self.file_path)
            if self.padding_meters > 0:
                result["padding"] = self.padding_meters

        return result

    @classmethod
    def from_dict(cls, data: dict, config_dir: Path | None = None) -> "ExtentConfig":
        """
        Deserialize from YAML config.

        Args:
            data: Configuration dictionary
            config_dir: Directory containing config file (for resolving relative paths)

        Returns:
            ExtentConfig instance
        """
        mode = data.get("type", "latlon")

        if mode == "latlon":
            extent = Extent(
                min_lon=data["min_lon"],
                min_lat=data["min_lat"],
                max_lon=data["max_lon"],
                max_lat=data["max_lat"],
            )
            return cls(mode="latlon", extent=extent)
        else:  # file mode
            file_path = Path(data["file"])

            # Resolve relative paths relative to config file directory
            if config_dir and not file_path.is_absolute():
                file_path = config_dir / file_path

            padding = data.get("padding", 0.0)
            return cls(mode="file", file_path=file_path, padding_meters=padding)
