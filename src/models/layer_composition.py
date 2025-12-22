"""Layer composition model."""

from dataclasses import dataclass

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
