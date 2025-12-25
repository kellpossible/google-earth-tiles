"""Generation request model."""

from dataclasses import dataclass
from pathlib import Path
from typing import List

from src.models.extent import Extent
from src.models.layer_composition import LayerComposition


@dataclass
class GenerationRequest:
    """Request parameters for KMZ generation."""

    layer_compositions: List[LayerComposition]
    min_zoom: int
    max_zoom: int
    extent: Extent
    output_path: Path

    def __post_init__(self):
        """Validate the generation request."""
        if self.min_zoom > self.max_zoom:
            raise ValueError(f"min_zoom ({self.min_zoom}) cannot be greater than max_zoom ({self.max_zoom})")

        if self.min_zoom < 0 or self.min_zoom > 18:
            raise ValueError(f"min_zoom must be between 0 and 18, got {self.min_zoom}")

        if self.max_zoom < 0 or self.max_zoom > 18:
            raise ValueError(f"max_zoom must be between 0 and 18, got {self.max_zoom}")

        if not self.layer_compositions:
            raise ValueError("layer_compositions cannot be empty")

        # Convert output_path to Path if it's a string
        if isinstance(self.output_path, str):
            self.output_path = Path(self.output_path)

    @property
    def is_lod_enabled(self) -> bool:
        """Check if LOD is enabled (min_zoom < max_zoom)."""
        return self.min_zoom < self.max_zoom

    @property
    def zoom_levels(self) -> int:
        """Get the number of zoom levels."""
        return self.max_zoom - self.min_zoom + 1

    def copy(self) -> 'GenerationRequest':
        """Create a defensive copy of this request."""
        return GenerationRequest(
            layer_compositions=[comp.copy() for comp in self.layer_compositions],
            min_zoom=self.min_zoom,
            max_zoom=self.max_zoom,
            extent=self.extent.copy(),
            output_path=Path(self.output_path)
        )
