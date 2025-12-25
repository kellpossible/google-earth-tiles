"""Layer composition model."""

from dataclasses import dataclass
from typing import Dict, Any, Union

from src.core.config import LayerConfig


@dataclass
class LayerComposition:
    """Composition settings for a single layer."""

    layer_config: LayerConfig
    opacity: int  # 0-100
    blend_mode: str  # 'normal', 'multiply', 'screen', 'overlay'

    def __post_init__(self):
        """Validate composition settings."""
        if not 0 <= self.opacity <= 100:
            raise ValueError(f"Opacity must be between 0 and 100, got {self.opacity}")

        valid_modes = {'normal', 'multiply', 'screen', 'overlay'}
        if self.blend_mode not in valid_modes:
            raise ValueError(f"Blend mode must be one of {valid_modes}, got {self.blend_mode}")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert composition to dictionary for YAML serialization.

        Returns:
            Dictionary with name, opacity, and blend_mode keys
        """
        return {
            'name': self.layer_config.name,
            'opacity': self.opacity,
            'blend_mode': self.blend_mode
        }

    @classmethod
    def from_dict(cls, data: Union[str, Dict[str, Any]]) -> 'LayerComposition':
        """
        Create composition from dictionary (loaded from YAML).

        Args:
            data: Dictionary with name, opacity (optional), blend_mode (optional),
                  or a simple string representing the layer name

        Returns:
            LayerComposition instance

        Raises:
            ValueError: If layer name is not found in LAYERS
        """
        from src.core.config import LAYERS

        # Handle both simple string format and dict format
        if isinstance(data, str):
            layer_name = data
            opacity = 100
            blend_mode = 'normal'
        else:
            layer_name = data['name']
            opacity = data.get('opacity', 100)
            blend_mode = data.get('blend_mode', 'normal')

        if layer_name not in LAYERS:
            raise ValueError(f"Unknown layer: {layer_name}. Valid layers: {', '.join(LAYERS.keys())}")

        return cls(
            layer_config=LAYERS[layer_name],
            opacity=opacity,
            blend_mode=blend_mode
        )
