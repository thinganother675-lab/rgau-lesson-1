"""Crossref metadata lookups; authorships are evidence, not author profiles."""

import os
from urllib.parse import quote

from ..models import Author, Metric, Provenance, Publication, utc_now
from ..normalization import normalize_doi, normalize_issn, normalize_name, normalize_orcid
from .base import Batch, ProviderError


class Crossref:
    name = "crossref"
    base_url = "https://api.crossref.org"

    def __init__(self, http, mailto=None):
        self.http = http
        self.mailto = mailto if mailto is not None else os.getenv("CROSSREF_MAILTO", "")

    def _get(self, path, params=None):
        params = dict(params or {})
        if self.mailto:
            params["mailto"] = self.mailto
        data = self.http.get(self.name, self.base_url + path, params=params)
        if data.get("status") != "ok" or "message" not in data:
            raise ProviderError(self.name, "неожиданный формат ответа")
        return data["message"]

    @staticmethod
    def _limit(limit):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer between 1 and 1000")

    def publication(self, doi):
        doi = normalize_doi(doi)
        if not doi:
            raise ValueError("Invalid DOI")
        data = self._get("/works/" + quote(doi, safe="/"))
        return self.parse_publication(data, self.http.last_retrieved_at)

    def search_authors(self, query, limit=5):
        self._limit(limit)
        tokens = set(normalize_name(query).split())
        if not tokens:
            raise ValueError("An author query is required")
        data = self._get("/works", {"query.author": query, "rows": min(100, limit * 5)})
        candidates = []
        for entry in data["items"]:
            work = self.parse_publication(entry, self.http.last_retrieved_at)
            for author in work.authors:
                if tokens.intersection(normalize_name(author.name).split()):
                    candidates.append(author)
                    if len(candidates) == limit:
                        break
            if len(candidates) == limit:
                break
        # Search returns works, not a total of persons. Do not invent the latter.
        return Batch(
            candidates,
            None,
            False,
            "Crossref возвращает авторские упоминания в работах, а не профили; требуется проверка.",
        )

    def publications(self, author, limit=20):
        self._limit(limit)
        orcid = normalize_orcid(author.identifiers.get("orcid"))
        if not orcid:
            return Batch(
                [],
                None,
                False,
                "Для точного фильтра Crossref нужен ORCID; поиск по имени не подтверждает корпус автора.",
            )
        cursor, cursors = "*", set()
        items, seen, total, complete = [], set(), None, False
        while len(items) < limit and len(cursors) < 20:
            cursors.add(cursor)
            data = self._get(
                "/works", {"filter": "orcid:" + orcid, "rows": min(100, limit - len(items)), "cursor": cursor}
            )
            rows = data["items"]
            total = data.get("total-results", total)
            for row in rows:
                if len(items) >= limit:
                    break
                work = self.parse_publication(row, self.http.last_retrieved_at)
                if work.id not in seen:
                    seen.add(work.id)
                    items.append(work)
            next_cursor = data.get("next-cursor")
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
            items,
            total,
            complete,
            "Все найденные Crossref записи с данным ORCID; это не гарантия полноты биографии."
            if complete
            else "Ограниченная или незавершённая выборка Crossref по ORCID.",
        )

    @classmethod
    def parse_publication(cls, data, retrieved_at=None):
        stamp = retrieved_at or utc_now()
        doi = normalize_doi(data.get("DOI"))
        if not doi:
            raise ProviderError(cls.name, "публикация без корректного DOI")
        url = "https://doi.org/" + doi
        authors = []
        for index, row in enumerate(data.get("author") or []):
            orcid = normalize_orcid(row.get("ORCID"))
            identifiers = {"orcid": orcid} if orcid else {}
            authors.append(
                Author(
                    id=f"crossref:{doi}#author-{index}",
                    name=row.get("name") or " ".join(x for x in (row.get("given"), row.get("family")) if x),
                    identifiers=identifiers,
                    affiliations=[x["name"] for x in row.get("affiliation") or [] if x.get("name")],
                    dois=[doi],
                    provenance=[Provenance(cls.name, doi, url, stamp, row)],
                )
            )
        year = None
        for field in ("published", "published-print", "published-online", "issued"):
            date_parts = (data.get(field) or {}).get("date-parts") or []
            if date_parts and date_parts[0]:
                year = date_parts[0][0]
                break
        titles = data.get("title") or []
        if isinstance(titles, str):
            titles = [titles]
        journals = data.get("container-title") or []
        if isinstance(journals, str):
            journals = [journals]
        citations = []
        if data.get("is-referenced-by-count") is not None:
            citations.append(Metric("citation_count", data["is-referenced-by-count"], cls.name, stamp))
        return Publication(
            id="crossref:" + doi,
            title=titles[0] if titles else "",
            doi=doi,
            year=year,
            authors=authors,
            issns=list(dict.fromkeys(x for value in data.get("ISSN") or [] if (x := normalize_issn(value)))),
            journal=journals[0] if journals else "",
            alternative_titles=titles[1:],
            source_ids={cls.name: doi},
            citations=citations,
            provenance=[Provenance(cls.name, doi, url, stamp, data)],
            extra={
                "type": data.get("type"),
                "relations": data.get("relation") or {},
                "references": data.get("reference") or [],
            },
        )
