"""Snapshot provenance and tamper detection in reproducible imports."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts import download_sources, rebuild_database


def write_manifest(path: Path, **extra):
    meta = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **extra}
    Path(str(path) + ".meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def test_manifest_rejects_modified_snapshot(tmp_path):
    path = tmp_path / "source.json"
    path.write_text("[]", encoding="utf-8")
    write_manifest(path)
    assert rebuild_database.verify_manifest(path)["sha256"]
    path.write_text('[{"changed":true}]', encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        rebuild_database.verify_manifest(path)


def test_validated_vak_preserves_acquisition_and_raw(tmp_path, monkeypatch):
    pdf = tmp_path / rebuild_database.VAK_PDF
    pdf.write_bytes(b"synthetic PDF bytes, not parsed in this test")
    pdf_meta = write_manifest(pdf, source_url="https://example.test/vak.pdf", list_date="2026-08-14")
    record = {
        "issns": ["2079-3537"],
        "title": "Synthetic test journal",
        "classifications": [{"source": "vak", "effective_date": "2026-08-14"}],
        "provenance": [
            {
                "source": "vak",
                "external_id": "1",
                "url": pdf_meta["source_url"],
                "retrieved_at": "2026-09-10T06:00:00+00:00",
                "raw": {"file_sha256": pdf_meta["sha256"], "unaltered": [1, "history"]},
            }
        ],
    }
    data = tmp_path / rebuild_database.VAK_JSON
    data.write_text(json.dumps([record]), encoding="utf-8")
    write_manifest(data, input=pdf.name, source_sha256=pdf_meta["sha256"], accepted=1, rejected=1)
    audit = tmp_path / rebuild_database.VAK_AUDIT
    audit.write_text(
        json.dumps({"accepted": 1, "rejected": [{"row": 2, "reason": "missing ISSN"}], "warnings": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(rebuild_database, "VAK_AUDIT_SHA256", rebuild_database.digest(audit))
    journals, result = rebuild_database.load_validated_vak(tmp_path, pdf_meta)
    assert journals[0].provenance[0].retrieved_at == record["provenance"][0]["retrieved_at"]
    assert journals[0].provenance[0].raw == record["provenance"][0]["raw"]
    assert journals[0].provenance[0].url == pdf_meta["source_url"]
    assert result["rejected"][0]["row"] == 2
    pdf_meta["sha256"] = "different-original"
    with pytest.raises(ValueError, match="verified source PDF"):
        rebuild_database.load_validated_vak(tmp_path, pdf_meta)


def test_downloader_refuses_login_html_as_pdf(tmp_path, monkeypatch):
    class Response:
        url = download_sources.VAK_URL
        headers = {"Content-Type": "text/html"}
        sent = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, size):
            if self.sent:
                return b""
            self.sent = True
            return b"<html>login required</html>"

    monkeypatch.setattr(download_sources.urllib.request, "urlopen", lambda *a, **k: Response())
    with pytest.raises(ValueError, match="Expected a PDF"):
        download_sources.download_one("vak", tmp_path)
    assert not list(tmp_path.iterdir())
