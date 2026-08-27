"""
EnrichmentProvider abstraction — third-party company/contact data enrichment
(e.g. Clearbit-style lookups). No free-tier default is wired in; the
research engine (SearxNG + evidence-backed extraction) is the primary,
free-first path to company/contact data. This interface exists so a paid
enrichment adapter can be added later without touching business logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EnrichmentResult:
    found: bool
    data: dict
    source: str = ""


class EnrichmentProvider(ABC):
    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        ...

    @abstractmethod
    def enrich_company(self, *, domain: str) -> EnrichmentResult:
        ...


class DisabledEnrichmentProvider(EnrichmentProvider):
    name = "disabled"

    def configured(self) -> bool:
        return False

    def enrich_company(self, *, domain: str) -> EnrichmentResult:
        return EnrichmentResult(found=False, data={}, source="disabled")
