from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source_type: str  # webpage, rss, atom, api
    published_at: str | None = None


class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        ...

    @abstractmethod
    def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]:
        ...
