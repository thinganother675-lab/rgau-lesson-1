"""Rebuild journal records from checked-in, hash-verified source snapshots.

Existing databases are updated additively, never deleted. Use a new --db path
for a clean reconstruction. Acquisition timestamps are not replaced by now.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sciagg.models import Journal, Provenance, utc_now  # noqa: E402
from sciagg.providers.imports import import_journals  # noqa: E402
from sciagg.providers.vak_pdf import parse_vak_pdf  # noqa: E402
from sciagg.storage import Store  # noqa: E402

WHITELIST = "whitelist_2026-09-10.json"
VAK_PDF = "vak_2026-08-14.pdf"
VAK_JSON = "vak_parsed_2026-08-14.json"
VAK_AUDIT = "vak_parse_audit_2026-09-10.json"
VAK_AUDIT_SHA256 = "ad8318ea95f7696e4b95dff1e07b0ef206257e28584742352fc394f92cd733a3"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_manifest(path: Path) -> dict:
    meta = json.loads(Path(str(path) + ".meta.json").read_text(encoding="utf-8"))
    if not isinstance(meta, dict) or meta.get("sha256") != digest(path):
        raise ValueError(f"SHA-256 mismatch or invalid manifest: {path}")
    if "bytes" in meta and meta["bytes"] != path.stat().st_size:
        raise ValueError(f"Byte count disagrees with manifest: {path}")
    return meta


def validate_acquisition(meta: dict, label: str) -> None:
    if not str(meta.get("source_url", "")).startswith("https://"):
        raise ValueError(f"{label}: HTTPS source URL is required")
    stamp = datetime.fromisoformat(meta["retrieved_at"])
    if stamp.tzinfo is None:
        raise ValueError(f"{label}: source timestamp must include its timezone")


def load_validated_vak(raw_dir: Path, pdf_meta: dict) -> tuple[list[Journal], dict]:
    meta = verify_manifest(raw_dir / VAK_JSON)
    if meta.get("input") != VAK_PDF or meta.get("source_sha256") != pdf_meta["sha256"]:
        raise ValueError("Derived VAK JSON does not identify the verified source PDF")
    audit_path = raw_dir / VAK_AUDIT
    if digest(audit_path) != VAK_AUDIT_SHA256:
        raise ValueError("VAK quarantine audit hash mismatch")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    records = json.loads((raw_dir / VAK_JSON).read_text(encoding="utf-8"))
    if not isinstance(records, list) or len(records) != meta["accepted"]:
        raise ValueError("Derived VAK row count disagrees with manifest")
    if len(audit["rejected"]) != meta["rejected"] or audit["accepted"] != len(records):
        raise ValueError("VAK quarantine audit count disagrees with manifest")
    journals = []
    for record in records:
        # Rehydrate exactly: preserve original timestamps, source URL and raw.
        data = dict(record)
        data["provenance"] = [Provenance(**p) for p in data["provenance"]]
        if not data["provenance"]:
            raise ValueError("Derived VAK record has no provenance")
        for provenance in data["provenance"]:
            if (
                provenance.source != "vak"
                or provenance.url != pdf_meta["source_url"]
                or provenance.raw.get("file_sha256") != pdf_meta["sha256"]
            ):
                raise ValueError("Derived VAK provenance disagrees with source PDF")
            if datetime.fromisoformat(provenance.retrieved_at).tzinfo is None:
                raise ValueError("Derived VAK timestamp must include its timezone")
        if any(c.get("effective_date") != pdf_meta["list_date"] for c in data["classifications"]):
            raise ValueError("Derived VAK effective date disagrees with source PDF")
        journals.append(Journal(**data))
    return journals, {
        "source": "vak",
        "mode": "validated_derived_json",
        "accepted": len(journals),
        "rejected": audit["rejected"],
        "warnings": audit["warnings"],
        "file_sha256": pdf_meta["sha256"],
        "derived_sha256": meta["sha256"],
        "snapshot_date": pdf_meta["list_date"],
    }


def save_records(store: Store, journals: list[Journal]) -> dict:
    result = store.save_journals(journals)
    return {"saved_records": result["stored"], "storage_rejected": result["rejected"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data/sciagg.sqlite")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--audit", type=Path, default=ROOT / "examples/rebuild_audit.json")
    parser.add_argument(
        "--use-validated-vak-json",
        action="store_true",
        help="Use the hash-verified result of the already executed PDF parse",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Check input hashes/provenance; do not open SQLite or write files",
    )
    args = parser.parse_args(argv)
    try:
        whitelist_meta = verify_manifest(args.raw_dir / WHITELIST)
        pdf_meta = verify_manifest(args.raw_dir / VAK_PDF)
        validate_acquisition(whitelist_meta, "whitelist")
        validate_acquisition(pdf_meta, "vak")
        vak_journals, vak_audit = None, None
        if args.use_validated_vak_json:
            vak_journals, vak_audit = load_validated_vak(args.raw_dir, pdf_meta)
        if args.verify_only:
            print(
                json.dumps(
                    {
                        "verified": True,
                        "whitelist_sha256": whitelist_meta["sha256"],
                        "vak_sha256": pdf_meta["sha256"],
                        "validated_vak_records": len(vak_journals) if vak_journals is not None else None,
                    },
                    indent=2,
                )
            )
            return 0
        whitelist_journals, whitelist_audit = import_journals(
            args.raw_dir / WHITELIST,
            "whitelist",
            source_url=whitelist_meta["source_url"],
            snapshot_date=whitelist_meta["retrieved_at"][:10],
        )
        for journal in whitelist_journals:
            for provenance in journal.provenance:
                provenance.retrieved_at = whitelist_meta["retrieved_at"]
            for classification in journal.classifications:
                classification["retrieved_at"] = whitelist_meta["retrieved_at"]
        if vak_journals is None:
            print("Parsing verified VAK PDF (1,277 pages; approximately 2–3 minutes)...", file=sys.stderr)
            vak_journals = parse_vak_pdf(
                args.raw_dir / VAK_PDF, pdf_meta["source_url"], pdf_meta["list_date"]
            )
            vak_audit = {
                "source": "vak",
                "mode": "pdf",
                "accepted": len(vak_journals),
                "rejected": vak_journals.rejected,
                "warnings": vak_journals.warnings,
                "snapshot_date": pdf_meta["list_date"],
                "file_sha256": pdf_meta["sha256"],
            }
            for journal in vak_journals:
                for provenance in journal.provenance:
                    provenance.retrieved_at = pdf_meta["retrieved_at"]
        # Parsing and all source verification precede database mutations.
        audit = {
            "rebuilt_at": utc_now(),
            "db": str(args.db.resolve()),
            "mode": "additive_upsert_no_database_deletion",
            "sources": [],
        }
        with Store(args.db) as store:
            whitelist_audit.update(save_records(store, whitelist_journals))
            vak_audit.update(save_records(store, vak_journals))
            audit["sources"] = [whitelist_audit, vak_audit]
            audit["stored_journals"] = store.connection.execute("SELECT COUNT(*) FROM journals").fetchone()[0]
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "db": audit["db"],
                    "stored_journals": audit["stored_journals"],
                    "audit": str(args.audit.resolve()),
                    "whitelist_quarantined": len(whitelist_audit["rejected"]),
                    "vak_quarantined": len(vak_audit["rejected"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"Rebuild failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
