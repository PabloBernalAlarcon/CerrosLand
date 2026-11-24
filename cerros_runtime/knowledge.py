"""Knowledge layer: load only the packs a component declares, by status.

Packs are versioned metadata (v0.1 registry, decision E1). Source content is attached
separately; a partial or incomplete pack is reported, never completed (Handoff §8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .catalog import Catalog

AVAILABLE_PREFIXES = ("FUENTE CANÓNICA DISPONIBLE", "FUENTE DISPONIBLE", "FUENTES DISPONIBLES")


@dataclass
class PackView:
    knowledge_id: str
    name: str
    version: str
    status: str
    authority_class: str
    complete: bool
    forbidden_reasoning: list[str]
    attached_sources: list[Path] = field(default_factory=list)

    @property
    def warning(self) -> str | None:
        if self.complete:
            return None
        return (f"{self.knowledge_id} ({self.name}) está {self.status}. No completar con conocimiento "
                f"general; señalar los vacíos (CORE-01, CORE-05).")


class KnowledgeLayer:
    def __init__(self, cat: Catalog, sources_dir: Path | None = None):
        self.cat = cat
        self.sources_dir = sources_dir

    def pack(self, kp_id: str) -> PackView:
        p = self.cat.knowledge_registry[kp_id]
        attached = []
        if self.sources_dir and (self.sources_dir / kp_id).is_dir():
            attached = sorted(x for x in (self.sources_dir / kp_id).iterdir() if x.is_file())
        return PackView(kp_id, p["name"], str(p.get("version")), p["status"], p.get("authority_class", ""),
                        p["status"].startswith(AVAILABLE_PREFIXES), list(p.get("forbidden_reasoning") or []),
                        attached)

    def for_component(self, cid: str) -> list[PackView]:
        return [self.pack(k) for k in self.cat.specs[cid].get("knowledge_dependencies") or []]
