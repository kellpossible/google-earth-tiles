"""Output configuration model."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OutputConfig:
    """Configuration for a single output."""

    output_type: str  # Type identifier (e.g., "kmz", "geotiff", "mbtiles")
    output_path: Path
    options: dict = field(default_factory=dict)  # Format-specific options

    # Convenience property for backward compatibility with KMZ-specific code
    @property
    def web_compatible(self) -> bool:
        """Get web_compatible option (KMZ-specific)."""
        return self.options.get("web_compatible", False)

    @web_compatible.setter
    def web_compatible(self, value: bool):
        """Set web_compatible option (KMZ-specific)."""
        self.options["web_compatible"] = value

    def __post_init__(self):
        """Validate and normalize the output configuration."""
        # Convert output_path to Path if it's a string
        if isinstance(self.output_path, str):
            self.output_path = Path(self.output_path)

        # Validate output_type against registry
        from src.outputs import OUTPUT_HANDLERS

        if self.output_type not in OUTPUT_HANDLERS:
            valid_types = list(OUTPUT_HANDLERS.keys())
            raise ValueError(
                f"Invalid output_type: {self.output_type}. Valid types: {valid_types}"
            )

        # Validate format-specific options
        from src.outputs import get_output_handler

        handler = get_output_handler(self.output_type)
        handler.validate_options(self.options)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the output config
        """
        result = {
            "type": self.output_type,
            "path": str(self.output_path),
        }

        # Add format-specific options (flatten for backward compatibility)
        # For KMZ, include web_compatible at top level
        if self.output_type == "kmz" and "web_compatible" in self.options:
            result["web_compatible"] = self.options["web_compatible"]

        # Include any other options
        for key, value in self.options.items():
            if key not in result:
                result[key] = value

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "OutputConfig":
        """Create OutputConfig from dictionary.

        Args:
            data: Dictionary containing output configuration

        Returns:
            OutputConfig instance

        Raises:
            ValueError: If required keys are missing or invalid
        """
        if "path" not in data:
            raise ValueError("Missing required key 'path' in output configuration")

        output_type = data.get("type", "kmz")

        # Extract format-specific options
        # Exclude standard keys: type, path
        standard_keys = {"type", "path"}
        options = {k: v for k, v in data.items() if k not in standard_keys}

        return cls(
            output_type=output_type,
            output_path=Path(data["path"]),
            options=options,
        )
