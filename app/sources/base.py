from __future__ import annotations

import importlib
import pkgutil
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.config import Settings

SOURCE_REGISTRY: list[type["Source"]] = []


class RawItem(BaseModel):
    title: str
    organizer: str = "unknown"
    description: str = ""
    url: str | None = None
    source: str


class Source(ABC):
    """Base contract for a source; register subclasses to enable plug-in discovery."""

    registry: ClassVar[list[type["Source"]]] = SOURCE_REGISTRY

    @classmethod
    def from_settings(cls, settings: "Settings") -> "Source | None":
        raise NotImplementedError

    @abstractmethod
    def fetch(self) -> list[RawItem]:
        """Return currently available source items without analyzing them."""


def register_source(source_class: type[Source]) -> type[Source]:
    SOURCE_REGISTRY.append(source_class)
    return source_class


def discover_sources(settings: "Settings") -> list[Source]:
    """Import source modules and construct registered sources.

    A new adapter only needs to live in ``app/sources`` and use ``@register_source``.
    """
    package = importlib.import_module("app.sources")
    for module in pkgutil.iter_modules(package.__path__):
        if module.name not in {"base"}:
            importlib.import_module(f"{package.__name__}.{module.name}")
    return [source for source_class in SOURCE_REGISTRY if (source := source_class.from_settings(settings)) is not None]
