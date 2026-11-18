"""Signature generation contract; actual pen-stroke engine is pending."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedAssets:
    """Identifier for an existing, validated PNG and WebM asset pair."""

    asset_id: str


async def generate_signature(
    full_name: str,
    portrait: bytes,
    api_key: str,
) -> GeneratedAssets:
    """Generate handwritten PNG and matching pen-trace WebM.

    The rendering engine is intentionally not fabricated: producing a
    real handwritten Hebrew signature and synchronized pen animation
    requires an implementation that does not yet exist in this project.
    """
    raise NotImplementedError("Signature and pen-animation engine not implemented")
