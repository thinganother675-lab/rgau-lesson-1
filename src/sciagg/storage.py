"""SQLite persistence with normalized relations and full JSON source payloads."""

import hashlib
import json
import sqlite3
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path

from .models import Author, Journal, Metric, Provenance, Publication
from .normalization import normalize_doi, normalize_issn
from .resolution import _merge


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _key(prefix: str, value: dict) -> str:
    return prefix + ":" + hashlib.sha256(_json(value).encode()).hexdigest()[:24]


def _publication_from_payload(payload: dict) -> Publication:
    data = dict(payload)
    data["provenance"] = [Provenance(**p) for p in data.get("provenance", [])]
    data["citations"] = [Metric(**m) for m in data.get("citations", [])]
    data["authors"] = [
        Author(
            **{
                **a,
                "provenance": [Provenance(**p) for p in a.get("provenance", [])],
                "metrics": [Metric(**m) for m in a.get("metrics", [])],
            }
        )
        for a in data.get("authors", [])
    ]
    return Publication(**data)


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS publications (
                id TEXT PRIMARY KEY, doi TEXT, title TEXT NOT NULL, year INTEGER,
                journal TEXT, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS publications_doi ON publications(doi);
            CREATE TABLE IF NOT EXISTS authors (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS authorships (
                publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
                author_id TEXT NOT NULL REFERENCES authors(id), position INTEGER NOT NULL,
                PRIMARY KEY(publication_id, position));
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY, owner_type TEXT NOT NULL, owner_id TEXT NOT NULL,
                kind TEXT NOT NULL, value TEXT, source TEXT NOT NULL, retrieved_at TEXT NOT NULL,
                year INTEGER, category TEXT, scope TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS metrics_owner ON metrics(owner_type, owner_id);
            CREATE TABLE IF NOT EXISTS provenance (
                id INTEGER PRIMARY KEY, owner_type TEXT NOT NULL, owner_id TEXT NOT NULL,
                source TEXT NOT NULL, external_id TEXT, url TEXT, retrieved_at TEXT NOT NULL,
                raw TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS provenance_owner ON provenance(owner_type, owner_id);
            CREATE TABLE IF NOT EXISTS journals (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS journal_issns (
                issn TEXT PRIMARY KEY, journal_id TEXT NOT NULL REFERENCES journals(id));
            CREATE TABLE IF NOT EXISTS journal_classifications (
                id INTEGER PRIMARY KEY, journal_id TEXT NOT NULL REFERENCES journals(id),
                source TEXT, year INTEGER, category TEXT, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS journal_classifications_owner
                ON journal_classifications(journal_id);
        """)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self) -> None:
        self.connection.close()

    def _metadata(self, owner_type: str, owner_id: str, metrics: list, provenance: list) -> None:
        db = self.connection
        db.execute("DELETE FROM metrics WHERE owner_type=? AND owner_id=?", (owner_type, owner_id))
        db.execute("DELETE FROM provenance WHERE owner_type=? AND owner_id=?", (owner_type, owner_id))
        for metric in metrics:
            data = asdict(metric) if not isinstance(metric, dict) else metric
            db.execute(
                "INSERT INTO metrics(owner_type,owner_id,kind,value,source,retrieved_at,year,category,scope,payload) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    owner_type,
                    owner_id,
                    data["kind"],
                    _json(data["value"]),
                    data["source"],
                    data["retrieved_at"],
                    data.get("year"),
                    data.get("category"),
                    data.get("scope", "source"),
                    _json(data),
                ),
            )
        for record in provenance:
            data = asdict(record) if not isinstance(record, dict) else record
            db.execute(
                "INSERT INTO provenance(owner_type,owner_id,source,external_id,url,retrieved_at,raw,payload) VALUES(?,?,?,?,?,?,?,?)",
                (
                    owner_type,
                    owner_id,
                    data["source"],
                    data.get("external_id", ""),
                    data.get("url", ""),
                    data["retrieved_at"],
                    _json(data.get("raw", {})),
                    _json(data),
                ),
            )

    def _save_author(self, author: Author) -> str:
        payload = asdict(author)
        identifier = author.id or _key("author", payload)
        payload["id"] = identifier
        row = self.connection.execute("SELECT payload FROM authors WHERE id=?", (identifier,)).fetchone()
        if row:
            previous = json.loads(row[0])
            for key, value in previous["identifiers"].items():
                if key in payload["identifiers"] and payload["identifiers"][key] != value:
                    raise ValueError(f"conflicting {key} for stored author {identifier}")
                payload["identifiers"][key] = value
            for field in (
                "variants",
                "affiliations",
                "subjects",
                "dois",
                "coauthors",
                "metrics",
                "provenance",
            ):
                payload[field] = previous[field] + [v for v in payload[field] if v not in previous[field]]
            if (
                previous["name"]
                and previous["name"] != payload["name"]
                and previous["name"] not in payload["variants"]
            ):
                payload["variants"].append(previous["name"])
            if not payload["name"]:
                payload["name"] = previous["name"]
        self.connection.execute(
            "INSERT INTO authors(id,name,payload) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,payload=excluded.payload",
            (identifier, payload["name"], _json(payload)),
        )
        self._metadata("author", identifier, payload["metrics"], payload["provenance"])
        return identifier

    def save_author(self, author: Author) -> str:
        with self.connection:
            return self._save_author(author)

    def save_publications(self, publications: list[Publication]) -> None:
        with self.connection:
            for publication in publications:
                payload = asdict(publication)
                identifier = publication.id or _key("publication", payload)
                payload["id"] = identifier
                row = self.connection.execute(
                    "SELECT payload FROM publications WHERE id=?", (identifier,)
                ).fetchone()
                if row:
                    previous = _publication_from_payload(json.loads(row[0]))
                    old_doi, new_doi = normalize_doi(previous.doi), normalize_doi(publication.doi)
                    if old_doi and new_doi and old_doi != new_doi:
                        raise ValueError(f"conflicting DOI for stored publication {identifier}")
                    if publication.doi and new_doi is None:
                        raise ValueError(f"invalid DOI for stored publication {identifier}")
                    # Stable source identity authorizes refresh, but history remains additive.
                    publication = _merge(previous, publication)
                    payload = asdict(publication)
                    payload["id"] = identifier
                self.connection.execute(
                    "INSERT INTO publications(id,doi,title,year,journal,payload) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET doi=excluded.doi,title=excluded.title,year=excluded.year,journal=excluded.journal,payload=excluded.payload",
                    (
                        identifier,
                        publication.doi,
                        publication.title,
                        publication.year,
                        publication.journal,
                        _json(payload),
                    ),
                )
                self.connection.execute("DELETE FROM authorships WHERE publication_id=?", (identifier,))
                for position, author in enumerate(publication.authors, 1):
                    author_id = self._save_author(author)
                    self.connection.execute(
                        "INSERT INTO authorships VALUES(?,?,?)", (identifier, author_id, position)
                    )
                self._metadata("publication", identifier, publication.citations, publication.provenance)

    def get_publication(self, identifier: str) -> dict | None:
        row = self.connection.execute("SELECT payload FROM publications WHERE id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_publications(self) -> list[dict]:
        return [
            json.loads(row[0])
            for row in self.connection.execute("SELECT payload FROM publications ORDER BY id")
        ]

    def get_author(self, identifier: str) -> dict | None:
        row = self.connection.execute("SELECT payload FROM authors WHERE id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_journal(self, journal: Journal, *, _autocommit: bool = True) -> str:
        payload = asdict(journal)
        normalized = []
        for value in journal.issns:
            issn = normalize_issn(value)
            if issn is None:
                raise ValueError(f"invalid journal ISSN: {value!r}")
            if issn not in normalized:
                normalized.append(issn)
        if not normalized and not journal.title.strip():
            raise ValueError("journal requires an ISSN or title")
        payload["issns"] = normalized
        existing_ids = set()
        for issn in normalized:
            row = self.connection.execute(
                "SELECT journal_id FROM journal_issns WHERE issn=?", (issn,)
            ).fetchone()
            if row:
                existing_ids.add(row[0])
        # Do not silently combine journals when an ISSN pair bridges known records.
        if len(existing_ids) > 1:
            raise ValueError("ISSNs belong to different stored journals; manual review required")
        identifier = (
            next(iter(existing_ids))
            if existing_ids
            else _key(
                "journal", {"issns": sorted(normalized), "title": journal.title if not normalized else ""}
            )
        )
        with self.connection if _autocommit else nullcontext():
            row = self.connection.execute("SELECT payload FROM journals WHERE id=?", (identifier,)).fetchone()
            if row:
                previous = json.loads(row[0])
                for field in ("issns", "classifications", "provenance"):
                    payload[field] = previous[field] + [v for v in payload[field] if v not in previous[field]]
                if not payload["title"]:
                    payload["title"] = previous["title"]
            self.connection.execute(
                "INSERT INTO journals VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,payload=excluded.payload",
                (identifier, payload["title"], _json(payload)),
            )
            for issn in payload["issns"]:
                self.connection.execute(
                    "INSERT INTO journal_issns VALUES(?,?) ON CONFLICT(issn) DO NOTHING", (issn, identifier)
                )
            self.connection.execute("DELETE FROM journal_classifications WHERE journal_id=?", (identifier,))
            for classification in payload["classifications"]:
                self.connection.execute(
                    "INSERT INTO journal_classifications(journal_id,source,year,category,payload) VALUES(?,?,?,?,?)",
                    (
                        identifier,
                        classification.get("source"),
                        classification.get("year"),
                        classification.get("category"),
                        _json(classification),
                    ),
                )
            self._metadata("journal", identifier, [], payload["provenance"])
        return identifier

    def save_journals(self, journals: list[Journal], *, batch_size: int = 500) -> dict:
        """Write bounded transactions with per-record rollback and quarantine.

        ``index`` is one-based in the supplied list. Expected data errors quarantine
        only the affected record. Operational/database failures propagate instead
        of being disguised as data errors. Existing caller transactions are kept
        open; otherwise each batch commits normally with SQLite's durability on.
        """
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        report = {"stored": 0, "rejected": []}
        db = self.connection
        borrowed_transaction = db.in_transaction
        for start in range(0, len(journals), batch_size):
            # Explicit BEGIN prevents RELEASE of the row savepoint committing it.
            if not borrowed_transaction:
                db.execute("BEGIN")
            db.execute("SAVEPOINT journal_batch")
            try:
                for index, journal in enumerate(journals[start : start + batch_size], start + 1):
                    db.execute("SAVEPOINT journal_row")
                    try:
                        self.save_journal(journal, _autocommit=False)
                    except (ValueError, TypeError, sqlite3.IntegrityError) as exc:
                        db.execute("ROLLBACK TO SAVEPOINT journal_row")
                        report["rejected"].append(
                            {
                                "index": index,
                                "source_ids": [
                                    {"source": p.source, "external_id": p.external_id}
                                    for p in journal.provenance
                                ],
                                "issns": list(journal.issns),
                                "reason": str(exc),
                            }
                        )
                    else:
                        report["stored"] += 1
                    finally:
                        db.execute("RELEASE SAVEPOINT journal_row")
                db.execute("RELEASE SAVEPOINT journal_batch")
                if not borrowed_transaction:
                    db.commit()
            except BaseException:
                if borrowed_transaction:
                    db.execute("ROLLBACK TO SAVEPOINT journal_batch")
                    db.execute("RELEASE SAVEPOINT journal_batch")
                else:
                    db.rollback()
                raise
        return report

    def get_journal(self, issn: str) -> dict | None:
        normalized = normalize_issn(issn)
        if normalized is None:
            return None
        row = self.connection.execute(
            "SELECT j.payload FROM journals j JOIN journal_issns i ON j.id=i.journal_id WHERE i.issn=?",
            (normalized,),
        ).fetchone()
        return json.loads(row[0]) if row else None
