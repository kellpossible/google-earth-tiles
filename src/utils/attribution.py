"""Attribution utilities for MBTiles metadata."""

from src.models.layer_composition import LayerComposition


def build_attribution_from_layers(layer_compositions: list[LayerComposition]) -> str:
    """Build attribution string from layer sources.

    Collects unique attributions from all enabled layers and joins them.

    Args:
        layer_compositions: List of layer compositions

    Returns:
        Attribution string with de-duplicated layer attributions joined by "; "
    """
    attributions = []
    seen = set()

    for comp in layer_compositions:
        if comp.enabled:
            attr = comp.layer_config.attribution
            if attr and attr not in seen:
                attributions.append(attr)
                seen.add(attr)

    return "; ".join(attributions) if attributions else ""
