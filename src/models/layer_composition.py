"""Layer composition model."""

from dataclasses import dataclass, replace, field
from typing import Dict, Any, Union, Set

from src.core.config import LayerConfig


@dataclass
class LayerComposition:
    """Composition settings for a single layer."""

    layer_config: LayerConfig
    opacity: int  # 0-100
    blend_mode: str  # 'normal', 'multiply', 'screen', 'overlay'
    export_mode: str = "composite"  # 'composite' or 'separate'
    lod_mode: str = "all_zooms"  # 'all_zooms' or 'select_zooms'
    selected_zooms: Set[int] = field(default_factory=set)  # Used when lod_mode = "select_zooms"
    enabled: bool = True  # Whether this layer is active in the composition

    def __post_init__(self):
        """Validate composition settings."""
        if not 0 <= self.opacity <= 100:
            raise ValueError(f"Opacity must be between 0 and 100, got {self.opacity}")

        valid_modes = {'normal', 'multiply', 'screen', 'overlay'}
        if self.blend_mode not in valid_modes:
            raise ValueError(f"Blend mode must be one of {valid_modes}, got {self.blend_mode}")

        valid_export_modes = {'composite', 'separate'}
        if self.export_mode not in valid_export_modes:
            raise ValueError(f"Export mode must be one of {valid_export_modes}, got {self.export_mode}")

        valid_lod_modes = {'all_zooms', 'select_zooms'}
        if self.lod_mode not in valid_lod_modes:
            raise ValueError(f"LOD mode must be one of {valid_lod_modes}, got {self.lod_mode}")

    def get_available_zooms(self) -> Set[int]:
        """
        Get zoom levels available for this layer.

        IMPORTANT RESAMPLING ARCHITECTURE:
        ===================================
        This method returns ALL zoom levels that the layer can provide based on:
        1. Layer's native zoom range (min_zoom to max_zoom from layer config)
        2. LOD configuration (all_zooms or select_zooms with selected_zooms set)

        This method does NOT restrict by output zoom range. This is intentional to support
        comprehensive resampling capabilities.

        RESAMPLING BEHAVIOR:
        -------------------
        When generating tiles at any target zoom level, the compositor can resample from
        the nearest available source zoom, even if that source zoom is outside the output
        range. The find_best_source_zoom() method finds the nearest available zoom with
        preference for HIGHER zoom levels when equidistant (quality preservation).

        Example scenarios that require resampling:
        - Layer max zoom 15, generating zoom 16 → upsample from zoom 15
        - Layer select_zooms [15,16], generating zoom 14 → downsample from zoom 15 (nearest)
        - Layer select_zooms [10,11], generating zoom 14 → upsample from zoom 11 (nearest)
        - Layer select_zooms [12,14], generating zoom 13 → downsample from zoom 14 (equidistant, prefer higher)

        LOD select_zooms DESELECTION:
        ----------------------------
        When a layer has lod_mode='select_zooms' and certain zoom levels are NOT selected:
        - Those deselected zooms are NOT available as source zooms
        - When generating at a deselected zoom, the nearest selected zoom is used
        - Resampling (up or down) occurs automatically to reach the target zoom
        - Preference is given to higher zoom when distances are equal (better quality)

        Returns:
            Set of zoom levels available for this layer as source zooms
        """
        if self.lod_mode == "all_zooms":
            # Use all zooms within layer's native capability range
            return set(range(
                self.layer_config.min_zoom,
                self.layer_config.max_zoom + 1
            ))
        else:
            # Use only selected zooms, filtered to layer's native capability
            # No output range restriction - allow resampling to any target zoom
            return {
                z for z in self.selected_zooms
                if self.layer_config.min_zoom <= z <= self.layer_config.max_zoom
            }

    def find_best_source_zoom(self, target_zoom: int, available_zooms: Set[int]) -> int:
        """
        Find the best available zoom level to use for a target zoom.

        When the target zoom isn't available, finds the closest zoom and determines
        whether to upsample or downsample. When equidistant, prefers downsampling.

        Args:
            target_zoom: The desired zoom level
            available_zooms: Set of available zoom levels for this layer

        Returns:
            Best zoom level to use (may require resampling)
        """
        if target_zoom in available_zooms:
            return target_zoom

        if not available_zooms:
            # Fall back to layer's max zoom if no zooms available
            return min(self.layer_config.max_zoom, target_zoom)

        # Find closest zoom level
        lower_zooms = [z for z in available_zooms if z < target_zoom]
        higher_zooms = [z for z in available_zooms if z > target_zoom]

        if not lower_zooms:
            # Only higher zooms available - downsample from lowest available
            return min(higher_zooms)

        if not higher_zooms:
            # Only lower zooms available - upsample from highest available
            return max(lower_zooms)

        # Both directions available - check distances
        closest_lower = max(lower_zooms)
        closest_higher = min(higher_zooms)

        lower_distance = target_zoom - closest_lower
        higher_distance = closest_higher - target_zoom

        if lower_distance < higher_distance:
            return closest_lower  # Upsample
        elif higher_distance < lower_distance:
            return closest_higher  # Downsample
        else:
            # Equidistant - prefer downsampling (higher zoom)
            return closest_higher

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert composition to dictionary for YAML serialization.

        Returns:
            Dictionary with name, opacity, blend_mode, and optional export_mode/LOD/enabled keys
        """
        result = {
            'name': self.layer_config.name,
            'opacity': self.opacity,
            'blend_mode': self.blend_mode,
        }

        # Only include export_mode if not default
        if self.export_mode != "composite":
            result['export_mode'] = self.export_mode

        # Only include enabled if False (not default)
        if not self.enabled:
            result['enabled'] = False

        # Only include LOD config if not default
        if self.lod_mode != "all_zooms":
            result['lod_mode'] = self.lod_mode
            if self.lod_mode == "select_zooms" and self.selected_zooms:
                result['selected_zooms'] = sorted(list(self.selected_zooms))

        return result

    @classmethod
    def from_dict(cls, data: Union[str, Dict[str, Any]]) -> 'LayerComposition':
        """
        Create composition from dictionary (loaded from YAML).

        Args:
            data: Dictionary with name, opacity (optional), blend_mode (optional),
                  lod_mode (optional), selected_zooms (optional),
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
            export_mode = 'composite'
            lod_mode = 'all_zooms'
            selected_zooms = set()
            enabled = True
        else:
            layer_name = data['name']
            opacity = data.get('opacity', 100)
            blend_mode = data.get('blend_mode', 'normal')
            export_mode = data.get('export_mode', 'composite')
            lod_mode = data.get('lod_mode', 'all_zooms')
            selected_zooms = set(data.get('selected_zooms', []))
            enabled = data.get('enabled', True)

        if layer_name not in LAYERS:
            raise ValueError(f"Unknown layer: {layer_name}. Valid layers: {', '.join(LAYERS.keys())}")

        return cls(
            layer_config=LAYERS[layer_name],
            opacity=opacity,
            blend_mode=blend_mode,
            export_mode=export_mode,
            lod_mode=lod_mode,
            selected_zooms=selected_zooms,
            enabled=enabled
        )

    def copy(self) -> 'LayerComposition':
        """
        Create a copy of this layer composition.

        Returns:
            New LayerComposition instance with same values

        Note:
            LayerConfig is immutable (frozen), so shallow copy is safe
            selected_zooms set is explicitly copied to avoid shared references
        """
        return replace(self, selected_zooms=self.selected_zooms.copy())
