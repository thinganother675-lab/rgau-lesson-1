from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderError(Exception):
    """Public safe provider failure, never contains credentials or response bodies."""

    def __init__(self, source: str, reason: str, status: int | None = None):
        self.source, self.reason, self.status = source, reason, status
        super().__init__(f"{source}: {reason}" + (f" (HTTP {status})" if status else ""))


@dataclass
class Batch:
    items: list = field(default_factory=list)
    total: int | None = None
    complete: bool = False
    note: str = ""


class Provider(Protocol):
    name: str

    def publication(self, doi: str) -> Any: ...

    def search_authors(self, query: str, limit: int = 5) -> Batch: ...


def attempt(source, operation):
    """Isolate malformed remote responses as well as network failures."""
    try:
        return operation(), {"source": source, "status": "ok"}
    except ProviderError as exc:
        return None, {
            "source": source,
            "status": "unavailable",
            "reason": exc.reason,
            "http_status": exc.status,
        }
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        return None, {"source": source, "status": "invalid_response", "reason": type(exc).__name__}
