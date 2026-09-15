"""Build the compact course submission from an explicit, reviewed file list."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ".env.example",
    ".gitattributes",
    ".gitignore",
    "DEFENSE_CHEATSHEET_RU.md",
    "README.md",
    "README_RU.md",
    "REPORT_RU.md",
    "RESEARCH_NOTES.md",
    "SOURCES.md",
    "START_HERE.md",
    "SUBMISSION_LINKS_RU.md",
    "SUBMISSION_NOTE_RU.txt",
    "VALIDATION.md",
    "data/README.md",
    "data/raw/whitelist_2079-3537_2026-09-10.json",
    "data/raw/whitelist_2079-3537_2026-09-10.json.meta.json",
    "docs/INTERNATIONAL_SOURCES_RESEARCH.md",
    "docs/RUSSIAN_SOURCES_RESEARCH.md",
    "docs/SOURCE_CAPABILITIES.md",
    "examples/README.md",
    "examples/demo.csv",
    "examples/demo.profile.json",
    "examples/demo.xlsx",
    "examples/demo_profile.json",
    "examples/hirsch_article.json",
    "examples/live/crossref_search_validation.json",
    "examples/live/international_summary.json",
    "examples/live/international_validation.json",
    "examples/live/orcid_record.json",
    "examples/live/validate_international.py",
    "examples/orcid_profile.json",
    "examples/rebuild_audit.json",
    "examples/templates/README.md",
    "examples/templates/elibrary.json",
    "examples/templates/rankings.csv",
    "examples/vak_import_audit.json",
    "examples/validation/demo.txt",
    "examples/validation/format.txt",
    "examples/validation/h-index.txt",
    "examples/validation/pytest.txt",
    "examples/validation/raw-hashes.txt",
    "examples/validation/results.json",
    "examples/validation/ruff.txt",
    "examples/validation/sources.txt",
    "pyproject.toml",
    "requirements-validated.txt",
    "scripts/__init__.py",
    "scripts/build_submission.py",
    "scripts/check_project.py",
    "scripts/download_sources.py",
    "scripts/rebuild_database.py",
    "src/sciagg/__init__.py",
    "src/sciagg/__main__.py",
    "src/sciagg/cli.py",
    "src/sciagg/exports.py",
    "src/sciagg/http.py",
    "src/sciagg/models.py",
    "src/sciagg/normalization.py",
    "src/sciagg/providers/__init__.py",
    "src/sciagg/providers/base.py",
    "src/sciagg/providers/crossref.py",
    "src/sciagg/providers/imports.py",
    "src/sciagg/providers/openalex.py",
    "src/sciagg/providers/orcid.py",
    "src/sciagg/providers/scopus.py",
    "src/sciagg/providers/vak_pdf.py",
    "src/sciagg/providers/whitelist.py",
    "src/sciagg/resolution.py",
    "src/sciagg/services.py",
    "src/sciagg/storage.py",
    "tests/test_cli_failures.py",
    "tests/test_domain.py",
    "tests/test_http.py",
    "tests/test_imports.py",
    "tests/test_international_providers.py",
    "tests/test_rebuild_scripts.py",
    "tests/test_services.py",
    "tests/test_services_review.py",
    "tests/test_storage.py",
    "tests/test_vak_pdf.py",
)


def main():
    destination = ROOT / "submission"
    archive = ROOT / "rgau-lesson-1-submission.zip"
    allowed = set(FILES) | {"SUBMISSION_MANIFEST.json"}
    if destination.is_symlink():
        raise ValueError("Submission directory must not be a symlink")
    if destination.exists():
        unexpected = [
            p.relative_to(destination).as_posix()
            for p in destination.rglob("*")
            if p.is_symlink() or (p.is_file() and p.relative_to(destination).as_posix() not in allowed)
        ]
        if unexpected:
            raise ValueError(f"Submission has unexpected files; review them before rebuilding: {unexpected}")
    contents = {}
    for name in FILES:
        source = ROOT / name
        if not source.resolve().is_relative_to(ROOT) or source.is_symlink():
            raise ValueError(f"File must stay within project: {name}")
        payload = source.read_bytes()
        if not name.startswith("data/raw/") and source.suffix not in {".xlsx", ".pdf"}:
            payload = payload.decode("utf-8-sig").replace("\r\n", "\n").encode("utf-8")
        contents[name] = payload
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    contents["SUBMISSION_MANIFEST.json"] = (
        json.dumps({"algorithm": "SHA-256", "files": manifest}, indent=2) + "\n"
    ).encode("utf-8")
    for name, payload in contents.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as zipped:
        for name, payload in sorted(contents.items()):
            info = ZipInfo(name, date_time=(2026, 9, 10, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, payload, compresslevel=9)
    with ZipFile(archive) as zipped:
        if zipped.testzip() is not None or set(zipped.namelist()) != set(contents):
            raise ValueError("Archive validation failed")
        for name, payload in contents.items():
            if zipped.read(name) != payload:
                raise ValueError(f"Archive differs from submission file: {name}")
    print(f"submission/: {len(contents)} files")
    print(f"{archive.name}: {archive.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
