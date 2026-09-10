"""Import the official 2026 VAK PDF with explicit layout and rejection auditing.

Specialty/date columns are retained verbatim together: this importer does not
infer that historical specialty assignments still apply on the retrieval date.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from sciagg.models import Journal, Provenance


class VakJournalList(list):
    """List-compatible result; rejected rows must be reported by callers."""

    def __init__(self):
        super().__init__()
        self.rejected: list[dict] = []
        self.warnings: list[str] = []


def _valid_issn(value: str) -> bool:
    s = value.replace("-", "").upper()
    return (
        bool(re.fullmatch(r"\d{7}[\dX]", s))
        and (sum(int(c) * (8 - n) for n, c in enumerate(s[:7])) + (10 if s[-1] == "X" else int(s[-1]))) % 11
        == 0
    )


def parse_vak_text(text: str, source_url: str = "", effective_date: str = "") -> VakJournalList:
    """Parse six tab-separated layout columns: row,title,ISSN,specialty,date,page.

    This is the intermediate output of ``parse_vak_pdf``, not an arbitrary PDF
    text dump. Continuation lines have an empty row number. Old ISSNs in journal
    titles are deliberately not used as current journal identifiers.
    """
    result = VakJournalList()
    records: list[dict] = []
    current = None
    for line in text.splitlines():
        cells = line.split("\t")
        if len(cells) != 6:
            if line.strip():
                raise ValueError("VAK intermediate text must have six TSV columns")
            continue
        row, title, issn, specialty, dates, page = cells
        if re.fullmatch(r"\d+\.", row.strip()):
            current = {
                "row": int(row.rstrip(".")),
                "title": [],
                "issn": [],
                "specialty_date_lines": [],
                "pages": [],
            }
            records.append(current)
        if current is None:
            continue
        if title.strip():
            current["title"].append(title.strip())
        if issn.strip():
            current["issn"].append(issn.strip())
        if specialty.strip() or dates.strip():
            current["specialty_date_lines"].append(
                {"specialty": specialty.strip(), "date": dates.strip(), "page": page}
            )
        if page not in current["pages"]:
            current["pages"].append(page)
    if not records:
        raise ValueError("No numbered VAK rows found; unsupported PDF layout")
    for record in records:
        title = " ".join(record["title"])
        raw_issn = " ".join(record["issn"])
        # The official PDF sometimes uses Cyrillic Х for the visually identical
        # ISSN check symbol, or omits the hyphen. Preserve the original in raw.
        lookup_issn = raw_issn.upper().replace("Х", "X")
        values = re.findall(r"(?<!\d)\d{4}[\s–—-]*\d{3}[\dX](?!\d)", lookup_issn)
        compact = [re.sub(r"[\s–—-]", "", v) for v in values]
        issns = list(dict.fromkeys(v[:4] + "-" + v[4:] for v in compact))
        if not title or not issns or any(not _valid_issn(v) for v in issns):
            result.rejected.append({"reason": "missing_title_or_invalid_issn", **record})
            continue
        result.append(
            Journal(
                title=title,
                issns=issns,
                classifications=[
                    {
                        "source": "vak",
                        "status": "listed_in_snapshot",
                        "effective_date": effective_date,
                        "category": None,
                        "specialty_date_lines": record["specialty_date_lines"],
                    }
                ],
                provenance=[
                    Provenance(source="vak", external_id=str(record["row"]), url=source_url, raw=record)
                ],
            )
        )
    numbers = [r["row"] for r in records]
    if numbers != list(range(1, max(numbers) + 1)):
        result.warnings.append("Row numbers are not a complete sequence from 1; review source/layout")
    if not effective_date:
        result.warnings.append("Snapshot effective date is unknown; no current-date assumption made")
    return result


def parse_vak_pdf(path: str | Path, source_url: str = "", effective_date: str = "") -> VakJournalList:
    """Read known portrait VAK layout; checksum failures are quarantined.

    Requires optional pypdf. The official August 2026 document uses fixed
    physical columns (points): row<65, title<238, ISSN<300, specialty<510.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("VAK PDF import requires optional dependency pypdf") from exc
    path = Path(path)
    reader = PdfReader(path)
    first = reader.pages[0].extract_text()
    match = re.search(r"по\s+состоянию\s+на\s+(\d{2})\.(\d{2})\.(\d{4})", first)
    detected = "-".join(reversed(match.groups())) if match else ""
    if detected and effective_date and detected != effective_date:
        raise ValueError(f"Provided effective date {effective_date} disagrees with PDF {detected}")
    effective_date = effective_date or detected
    lines = []
    for page_number, page in enumerate(reader.pages, 1):
        if not 590 <= float(page.mediabox.width) <= 610:
            raise ValueError(f"Unsupported VAK page width on page {page_number}")
        spans = []

        def collect(t, cm, tm, font, size, spans=spans):
            if t.strip():
                spans.append((float(tm[4]), float(tm[5]), t.replace("\n", " ").replace("\t", " ")))

        page.extract_text(visitor_text=collect)
        grouped = []
        for x, y, content in sorted(spans, key=lambda s: (-s[1], s[0])):
            if not grouped or abs(grouped[-1][0] - y) > 2:
                grouped.append((y, []))
            grouped[-1][1].append((x, content))
        for _y, row_spans in grouped:
            columns = ["", "", "", "", ""]
            for x, content in sorted(row_spans):
                col = 0 if x < 65 else 1 if x < 238 else 2 if x < 300 else 3 if x < 510 else 4
                columns[col] += content
            lines.append("\t".join(c.strip() for c in columns) + "\t" + str(page_number))
    result = parse_vak_text("\n".join(lines), source_url, effective_date)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    for journal in result:
        journal.provenance[0].raw["file_sha256"] = sha
        journal.provenance[0].raw["pdf_layout"] = "vak_portrait_2026"
    return result
