"""OpenAlex graph records, always labelled as OpenAlex evidence."""

import os
import re
from urllib.parse import quote

from ..models import Author, Metric, Provenance, Publication, utc_now
from ..normalization import normalize_doi, normalize_issn, normalize_orcid
from .base import Batch, ProviderError


class OpenAlex:
    name = "openalex"
    base_url = "https://api.openalex.org"

    def __init__(self, http, api_key=None):
        self.http = http
        self.api_key = api_key if api_key is not None else os.getenv("OPENALEX_API_KEY", "")

    def _get(self, path, params=None):
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        return self.http.get(self.name, self.base_url + path, params=params, headers=headers)

    @staticmethod
    def _limit(limit):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer between 1 and 1000")
        return limit

    @staticmethod
    def _author_id(value):
        token = str(value).removeprefix("https://openalex.org/")
        if not re.fullmatch(r"A\d+", token):
            raise ValueError("Expected an OpenAlex author ID (A followed by digits)")
        return token

    def author(self, identifier):
        identifier = self._author_id(identifier)
        data = self._get("/authors/" + identifier)
        return self.parse_author(data, self.http.last_retrieved_at)

    def search_authors(self, query, limit=5):
        self._limit(limit)
        if not query.strip():
            raise ValueError("An author query is required")
        # Candidate search stays one request; profile identity needs independent evidence.
        data = self._get("/authors", {"search": query, "per_page": min(limit, 100)})
        items = [self.parse_author(row, self.http.last_retrieved_at) for row in data["results"]]
        total = data.get("meta", {}).get("count")
        return Batch(
            items,
            total,
            total is not None and len(items) >= total,
            "Кандидаты OpenAlex; совпадение имени не подтверждает личность.",
        )

    def publication(self, doi):
        doi = normalize_doi(doi)
        if not doi:
            raise ValueError("Invalid DOI")
        data = self._get("/works/" + quote("https://doi.org/" + doi, safe="/:"))
        return self.parse_publication(data, self.http.last_retrieved_at)

    def publications(self, author, limit=20):
        self._limit(limit)
        identifier = self._author_id(author.identifiers.get("openalex") or author.id)
        items, seen, cursors = [], set(), set()
        cursor, total, complete = "*", None, False
        while len(items) < limit and len(cursors) < 20:
            cursors.add(cursor)
            data = self._get(
                "/works",
                {
                    "filter": "authorships.author.id:" + identifier,
                    "per_page": min(100, limit - len(items)),
                    "cursor": cursor,
                },
            )
            rows = data["results"]
            total = data.get("meta", {}).get("count", total)
            for row in rows:
                if len(items) >= limit:
                    break
                work = self.parse_publication(row, self.http.last_retrieved_at)
                if work.id not in seen:
                    seen.add(work.id)
                    items.append(work)
            next_cursor = data.get("meta", {}).get("next_cursor")
            if total is not None and len(items) >= total:
                complete = True
                break
            if not rows or not next_cursor:
                complete = total is None
                break
            if next_cursor in cursors:
                break
            cursor = next_cursor
        return Batch(
            items, total, complete, "" if complete else "Ограниченная или незавершённая выборка OpenAlex."
        )

    @classmethod
    def parse_author(cls, data, retrieved_at=None):
        stamp = retrieved_at or utc_now()
        identifier = data.get("id", "")
        if not identifier:
            raise ProviderError(cls.name, "профиль без идентификатора")
        identifiers = {"openalex": identifier}
        orcid = normalize_orcid(data.get("orcid") or (data.get("ids") or {}).get("orcid"))
        if orcid:
            identifiers["orcid"] = orcid
        institutions = list(data.get("last_known_institutions") or [])
        institutions.extend(entry.get("institution") or {} for entry in data.get("affiliations") or [])
        affiliations = list(dict.fromkeys(x["display_name"] for x in institutions if x.get("display_name")))
        metrics = []
        for field, kind in (("works_count", "publication_count"), ("cited_by_count", "citation_count")):
            if data.get(field) is not None:
                metrics.append(Metric(kind, data[field], cls.name, stamp))
        summary = data.get("summary_stats") or {}
        if summary.get("h_index") is not None:
            metrics.append(Metric("h_index", summary["h_index"], cls.name, stamp))
        return Author(
            id=identifier,
            name=data.get("display_name") or "",
            identifiers=identifiers,
            variants=data.get("display_name_alternatives") or [],
            affiliations=affiliations,
            subjects=[x["display_name"] for x in data.get("topics") or [] if x.get("display_name")],
            metrics=metrics,
            provenance=[Provenance(cls.name, identifier, identifier, stamp, data)],
        )

    @classmethod
    def parse_publication(cls, data, retrieved_at=None):
        stamp = retrieved_at or utc_now()
        identifier = data.get("id", "")
        if not identifier:
            raise ProviderError(cls.name, "публикация без идентификатора")
        authors = []
        for authorship in data.get("authorships") or []:
            entry = authorship.get("author") or {}
            if not entry.get("id"):
                continue
            person = cls.parse_author(entry, stamp)
            person.affiliations = [
                x["display_name"] for x in authorship.get("institutions") or [] if x.get("display_name")
            ]
            if authorship.get("raw_author_name"):
                person.variants.append(authorship["raw_author_name"])
            person.provenance = [Provenance(cls.name, entry["id"], identifier, stamp, authorship)]
            authors.append(person)
        source = (data.get("primary_location") or {}).get("source") or {}
        issns = list(dict.fromkeys(x for value in source.get("issn") or [] if (x := normalize_issn(value))))
        citations = []
        if data.get("cited_by_count") is not None:
            citations.append(Metric("citation_count", data["cited_by_count"], cls.name, stamp))
        return Publication(
            id=identifier,
            title=data.get("display_name") or data.get("title") or "",
            doi=normalize_doi(data.get("doi")),
            year=data.get("publication_year"),
            authors=authors,
            issns=issns,
            journal=source.get("display_name") or "",
            source_ids={cls.name: identifier},
            citations=citations,
            provenance=[Provenance(cls.name, identifier, identifier, stamp, data)],
            extra={
                "type": data.get("type"),
                "source_id": source.get("id"),
                "referenced_works": data.get("referenced_works") or [],
            },
        )
