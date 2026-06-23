"""Auto-discovering variant registry.

Scans ``wc_predictor.lab.variants`` for modules exposing the variant contract
(VARIANT_ID, DESCRIPTION, FEATURE_IDEA, build_model). Because discovery is by
file, variants developed in parallel git worktrees never edit a shared file.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from wc_predictor.lab import variants as _variants_pkg


@dataclass(frozen=True)
class VariantInfo:
    variant_id: str
    description: str
    feature_idea: str
    module: str


def _iter_variant_modules() -> list[ModuleType]:
    modules: list[ModuleType] = []
    for info in pkgutil.iter_modules(_variants_pkg.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{_variants_pkg.__name__}.{info.name}")
        if hasattr(module, "VARIANT_ID") and hasattr(module, "build_model"):
            modules.append(module)
    return modules


def discover() -> dict[str, ModuleType]:
    """Return {variant_id: module} for every well-formed variant module."""

    found: dict[str, ModuleType] = {}
    for module in _iter_variant_modules():
        variant_id = str(module.VARIANT_ID)
        if variant_id in found:
            raise ValueError(
                f"duplicate VARIANT_ID {variant_id!r} in {module.__name__} "
                f"and {found[variant_id].__name__}"
            )
        found[variant_id] = module
    return found


def list_variants() -> list[VariantInfo]:
    return sorted(
        (
            VariantInfo(
                variant_id=str(m.VARIANT_ID),
                description=str(getattr(m, "DESCRIPTION", "")),
                feature_idea=str(getattr(m, "FEATURE_IDEA", "")),
                module=m.__name__,
            )
            for m in discover().values()
        ),
        key=lambda v: v.variant_id,
    )


def build(variant_id: str, *, generated_at_utc: str) -> Any:
    """Construct a fresh (unfitted) model for ``variant_id``."""

    found = discover()
    if variant_id not in found:
        raise KeyError(
            f"unknown variant {variant_id!r}; known: {sorted(found)}"
        )
    return found[variant_id].build_model(generated_at_utc=generated_at_utc)
