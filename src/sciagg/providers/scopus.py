"""Optional Elsevier integration. API key does not imply institutional entitlement."""

import os
import re

from ..models import Author, Metric, Provenance, Publication
from ..normalization import normalize_doi, normalize_issn
from .base import Batch, ProviderError


class Scopus:
    name = "scopus"
    base = "https://api.elsevier.com/content"

    def __init__(self, http):
        self.http = http

    def request(self, path, params=None):
        if not os.getenv("SCOPUS_API_KEY"):
            raise ProviderError(self.name, "SCOPUS_API_KEY не задан; подписные права проверяются отдельно")
        headers = {"X-ELS-APIKey": os.environ["SCOPUS_API_KEY"], "Accept": "application/json"}
        if token := os.getenv("SCOPUS_INST_TOKEN"):
            headers["X-ELS-Insttoken"] = token
        return self.http.get(self.name, self.base + path, params=params, headers=headers)

    def author(self, identifier):
        if not re.fullmatch(r"\d+", identifier):
            raise ValueError("Scopus Author ID must contain digits only")
        path = f"/author/author_id/{identifier}"
        data = self.request(path)
        record = data["author-retrieval-response"]
        if isinstance(record, list):
            record = record[0]
        profile = record.get("author-profile") or {}
        preferred = profile.get("preferred-name") or {}
        full = " ".join(preferred.get(k, "") for k in ("given-name", "surname")).strip()
        core = record.get("coredata") or {}
        metrics = []
        for field, kind in (
            ("citation-count", "citation_count"),
            ("document-count", "publication_count"),
            ("h-index", "h_index"),
        ):
            value = record.get(field, core.get(field))
            if value is not None:
                metrics.append(Metric(kind, int(value), self.name, self.http.last_retrieved_at))
        return Author(
            id=f"scopus:{identifier}",
            name=full or identifier,
            identifiers={"scopus": identifier},
            metrics=metrics,
            provenance=[
                Provenance(self.name, identifier, self.base + path, self.http.last_retrieved_at, data)
            ],
        )

    def parse_work(self, record, url):
        if record.get("error"):
            raise ProviderError(self.name, "ошибка в ответе Search API")
        identifier = str(record.get("dc:identifier") or record.get("eid") or "")
        if not identifier or not record.get("dc:title"):
            raise ValueError("Scopus result lacks identifier/title")
        issns = []
        for key in ("prism:issn", "prism:eIssn"):
            if record.get(key):
                normalized = normalize_issn(record[key])
                if normalized:
                    issns.append(normalized)
        citations = []
        if record.get("citedby-count") is not None:
            citations.append(
                Metric("citation_count", int(record["citedby-count"]), self.name, self.http.last_retrieved_at)
            )
        return Publication(
            id=f"scopus:{identifier}",
            title=record["dc:title"],
            doi=normalize_doi(record["prism:doi"]) if record.get("prism:doi") else None,
            year=int(record["prism:coverDate"][:4]) if record.get("prism:coverDate") else None,
            journal=record.get("prism:publicationName", ""),
            issns=issns,
            source_ids={self.name: identifier},
            citations=citations,
            provenance=[Provenance(self.name, identifier, url, self.http.last_retrieved_at, record)],
        )

    def publication(self, doi):
        doi = normalize_doi(doi)
        if doi is None:
            raise ValueError("Invalid DOI")
        # Query literal excludes control/query delimiters; escaped quotes are not portable in Scopus QL.
        if any(c in doi for c in ('"', "{", "}", "\\")):
            raise ValueError("DOI contains unsupported Scopus query delimiters")
        data = self.request("/search/scopus", {"query": f'DOI("{doi}")', "count": 5})
        for item in data["search-results"].get("entry", []):
            if item.get("prism:doi") and normalize_doi(item["prism:doi"]) == doi:
                return self.parse_work(item, self.base + "/search/scopus")
        raise ProviderError(self.name, "DOI не найден в доступной выдаче", 404)

    def publications(self, author, limit=20):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer between 1 and 1000")
        identifier = author.identifiers.get("scopus", "")
        if not re.fullmatch(r"\d+", identifier):
            raise ValueError("Scopus Author ID required")
        data = self.request("/search/scopus", {"query": f"AU-ID({identifier})", "count": min(limit, 200)})
        results = data["search-results"]
        total = int(results["opensearch:totalResults"])
        items = [
            self.parse_work(x, self.base + "/search/scopus")
            for x in results.get("entry", [])
            if not x.get("error")
        ][:limit]
        return Batch(items, total, len(items) >= total, "Scopus Search STANDARD; ограниченная выборка")

    def journal(self, issn):
        issn = normalize_issn(issn)
        if issn is None:
            raise ValueError("Invalid ISSN checksum/format")
        data = self.request(f"/serial/title/issn/{issn}")
        from ..models import Journal

        return Journal(
            [issn],
            provenance=[
                Provenance(
                    self.name,
                    issn,
                    self.base + f"/serial/title/issn/{issn}",
                    self.http.last_retrieved_at,
                    data,
                )
            ],
        )
