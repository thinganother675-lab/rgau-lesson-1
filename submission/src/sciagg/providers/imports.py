"""Validated user-supplied exports, with row-level quarantine and snapshot provenance."""

import csv
import hashlib
import json
from pathlib import Path

from openpyxl import load_workbook

from ..models import Author, Journal, Metric, Provenance, Publication
from ..normalization import normalize_doi, normalize_issn
from .whitelist import Whitelist


def _integer(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        result = int(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f"{field} must be an integer") from None
    if isinstance(value, float) and result != value:
        raise ValueError(f"{field} must be an integer")
    return result


def _array(value, field):
    if value is None or value == "":
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ValueError(
                f"{field} must be a JSON array; encode arrays as JSON in CSV/XLSX cells"
            ) from None
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _issn(value):
    normalized = normalize_issn(str(value))
    if normalized is None:
        raise ValueError(f"Invalid ISSN checksum/format: {value!r}")
    return normalized


def read_rows(path):
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list):
            raise ValueError("JSON import must be an array of records")
        return data
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            sample = stream.read(8192)
            stream.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(stream, dialect=dialect)
            headers = reader.fieldnames or []
            if not headers or len(headers) != len(set(headers)) or not all(headers):
                raise ValueError("CSV requires unique nonempty headers")
            return list(reader)
    if path.suffix.lower() == ".xlsx":
        book = load_workbook(path, read_only=True, data_only=True)
        try:
            rows = iter(book.active.values)
            headers = [str(x).strip() if x is not None else "" for x in next(rows, ())]
            if not headers or len(headers) != len(set(headers)) or not all(headers):
                raise ValueError("XLSX requires unique nonempty headers")
            return [dict(zip(headers, row, strict=True)) for row in rows if any(x is not None for x in row)]
        finally:
            book.close()
    raise ValueError("Supported formats: .csv, .xlsx, .json; VAK PDF has a separate adapter")


def import_journals(path, source, *, source_url, snapshot_date):
    from datetime import date

    date.fromisoformat(snapshot_date)
    if not source_url:
        raise ValueError("source_url is required to distinguish official and synthetic imports")
    rows = read_rows(path)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    accepted, rejected = [], []
    for number, row in enumerate(rows, 1):
        try:
            if not isinstance(row, dict):
                raise ValueError("Each row must be an object with named columns")
            if source == "whitelist" and isinstance(row.get("title"), list):
                journal = Whitelist.parse(row, url=source_url)
            else:
                title = str(row.get("title") or "").strip()
                identifiers = row.get("issns") or row.get("issn") or ""
                if isinstance(identifiers, str):
                    identifiers = identifiers.replace(",", ";").split(";")
                identifiers = [_issn(x) for x in identifiers if x]
                if row.get("eissn"):
                    identifiers.append(_issn(row["eissn"]))
                if not title or not identifiers:
                    raise ValueError("title and issn(s) are required; map native columns to import template")
                value = row.get("value", row.get("category", row.get("level")))
                year = _integer(row["year"], "year") if row.get("year") else None
                kind = "quartile" if source == "ranking" else ("level" if source == "whitelist" else "status")
                if source == "ranking" and (
                    value not in ("Q1", "Q2", "Q3", "Q4")
                    or not year
                    or not row.get("subject_category")
                    or not row.get("system")
                ):
                    raise ValueError("Quartile requires Q1-Q4, system, year and subject_category")
                if source == "whitelist" and (not year or str(value) not in ("1", "2", "3", "4")):
                    raise ValueError("Whitelist requires explicit metric year and level 1-4")
                if source == "vak" and not row.get("status"):
                    raise ValueError("VAK normalized import requires explicit status")
                classification = {
                    "source": source,
                    "kind": kind,
                    "system": row.get("system", source),
                    "value": value,
                    "year": year,
                    "status": row.get("status", "observed"),
                    "category": row.get("subject_category"),
                    "specialties": row.get("specialties"),
                    "effective_from": row.get("effective_from"),
                    "effective_to": row.get("effective_to"),
                    "source_url": source_url,
                }
                journal = Journal(
                    list(dict.fromkeys(identifiers)),
                    title,
                    [classification],
                    [Provenance(source, str(number), source_url, raw=row)],
                )
            for p in journal.provenance:
                p.raw = {
                    "row": p.raw,
                    "file_sha256": digest,
                    "snapshot_date": snapshot_date,
                    "import_file": Path(path).name,
                    "row_number": number,
                }
            for c in journal.classifications:
                c.update(
                    snapshot_date=snapshot_date,
                    file_sha256=digest,
                    retrieved_at=journal.provenance[0].retrieved_at,
                )
            accepted.append(journal)
        except (ValueError, TypeError, KeyError) as exc:
            rejected.append({"row": number, "reason": str(exc), "raw": row})
    return accepted, {
        "source": source,
        "file_sha256": digest,
        "snapshot_date": snapshot_date,
        "accepted": len(accepted),
        "rejected": rejected,
        "rows": len(rows),
    }


def import_publications(path, *, source, source_url):
    """Neutral template for legal eLIBRARY/Scopus/institutional exports; not a site scraper."""
    if not source_url or not source:
        raise ValueError("source and source_url are required")
    result = []
    for number, row in enumerate(read_rows(path), 1):
        if not isinstance(row, dict):
            raise ValueError(f"Row {number}: each row must be an object")
        if not row.get("title") or not row.get("external_id") or not row.get("retrieved_at"):
            raise ValueError(f"Row {number}: title, external_id, retrieved_at required")
        from datetime import datetime

        stamp = str(row["retrieved_at"])
        parsed_stamp = datetime.fromisoformat(stamp)
        if parsed_stamp.tzinfo is None:
            raise ValueError(f"Row {number}: retrieved_at must include a timezone")
        provenance = Provenance(source, str(row["external_id"]), source_url, stamp, row)
        authors = []
        for a in _array(row.get("authors"), "authors"):
            if not isinstance(a, dict) or not a.get("id") or not a.get("name"):
                raise ValueError(f"Row {number}: each author requires id and name")
            identifiers = a.get("identifiers", {})
            if not isinstance(identifiers, dict):
                raise ValueError("author identifiers must be an object")
            authors.append(
                Author(
                    id=f"{source}:{a['id']}",
                    name=a["name"],
                    identifiers=identifiers,
                    affiliations=_array(a.get("affiliations"), "affiliations"),
                    provenance=[provenance],
                )
            )
        citations = []
        if row.get("citations") not in (None, ""):
            count = _integer(row["citations"], "citations")
            if count < 0:
                raise ValueError("Negative citations")
            citations = [Metric("citation_count", count, source, stamp)]
        doi = normalize_doi(row["doi"]) if row.get("doi") else None
        if row.get("doi") and doi is None:
            raise ValueError(f"Row {number}: invalid DOI")
        year = _integer(row["year"], "year") if row.get("year") else None
        result.append(
            Publication(
                id=f"{source}:{row['external_id']}",
                title=row["title"],
                doi=doi,
                year=year,
                authors=authors,
                issns=[_issn(x) for x in _array(row.get("issns"), "issns")],
                journal=row.get("journal", ""),
                source_ids={source: str(row["external_id"])},
                citations=citations,
                provenance=[provenance],
            )
        )
    return result
