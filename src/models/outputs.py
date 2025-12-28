"""Type aliases for output models."""

from src.models.generated import Outputs, Outputs1, Outputs2

# Type aliases for better readability
KMZOutput = Outputs
MBTilesOutput = Outputs1
GeoTIFFOutput = Outputs2
OutputUnion = Outputs | Outputs1 | Outputs2

__all__ = ["KMZOutput", "MBTilesOutput", "GeoTIFFOutput", "OutputUnion"]
