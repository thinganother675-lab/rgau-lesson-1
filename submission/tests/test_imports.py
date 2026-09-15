"""Synthetic imports are generated locally and are not assertions of official status."""

import csv
import json

import pytest
from openpyxl import Workbook

from sciagg.providers.imports import import_journals, import_publications, read_rows
from sciagg.providers.whitelist import Whitelist


def save_json(tmp_path, rows):
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def test_ranking_import_keeps_year_category_system_and_quarantines_invalid_rows(tmp_path):
    valid = {
        "title": "Synthetic Journal",
        "issn": "0028-0836",
        "value": "Q2",
        "year": 2024,
        "subject_category": "Synthetic category",
        "system": "Synthetic SJR",
    }
    path = save_json(
        tmp_path,
        [
            valid,
            {**valid, "issn": "0028-0837"},
            {**valid, "subject_category": ""},
            {**valid, "year": None},
            {**valid, "value": "Q5"},
        ],
    )
    journals, report = import_journals(
        path, "ranking", source_url="https://example.invalid/synthetic", snapshot_date="2026-09-10"
    )
    assert report["accepted"] == 1 and len(report["rejected"]) == 4
    classification = journals[0].classifications[0]
    assert classification["year"] == 2024 and classification["value"] == "Q2"
    assert classification["system"] == "Synthetic SJR" and classification["category"] == "Synthetic category"
    assert classification["snapshot_date"] == "2026-09-10"
    assert len(classification["file_sha256"]) == 64
    assert journals[0].provenance[0].raw["row"] == valid


def test_xlsx_import_preserves_native_integer_year_and_quarantines_invalid_eissn(tmp_path):
    path = tmp_path / "synthetic.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.append(["title", "issn", "eissn", "value", "year"])
    sheet.append(["Synthetic A", "0028-0836", "1476-4687", 2, 2025])
    sheet.append(["Synthetic B", "0028-0836", "1476-4688", 1, 2025])
    book.save(path)
    book.close()
    journals, report = import_journals(
        path, "whitelist", source_url="https://example.invalid/synthetic", snapshot_date="2026-09-10"
    )
    assert len(journals) == 1 and len(report["rejected"]) == 1
    assert journals[0].issns == ["0028-0836", "1476-4687"]
    assert journals[0].classifications[0]["year"] == 2025


def test_vak_import_requires_explicit_status(tmp_path):
    path = save_json(tmp_path, [{"title": "Synthetic", "issn": "0028-0836"}])
    journals, report = import_journals(
        path, "vak", source_url="https://example.invalid/synthetic", snapshot_date="2026-09-10"
    )
    assert journals == [] and len(report["rejected"]) == 1


def test_whitelist_null_year_is_not_filled_from_previous_year():
    journal = Whitelist.parse(
        {"issn": ["0028-0836"], "title": ["Synthetic"], "level_2025": 2, "level_2026": None}
    )
    levels = {item["year"]: item for item in journal.classifications}
    assert levels[2026]["value"] is None and levels[2026]["status"] == "not_assigned"
    assert levels[2025]["value"] == 2
    with pytest.raises(ValueError):
        Whitelist.parse({"issn": ["0028-0837"], "title": ["Synthetic"], "level_2026": 1})


def test_xlsx_duplicate_headers_rejected(tmp_path):
    path = tmp_path / "duplicate.xlsx"
    book = Workbook()
    book.active.append(["title", "title"])
    book.save(path)
    book.close()
    with pytest.raises(ValueError, match="headers"):
        read_rows(path)


def test_publication_import_keeps_source_and_snapshot(tmp_path):
    row = {
        "title": "Synthetic work",
        "external_id": "123",
        "retrieved_at": "2026-09-10T09:00:00+00:00",
        "doi": "https://doi.org/10.1234/ABC",
        "year": 2025,
        "citations": 7,
        "authors": [{"id": "a1", "name": "Ivan Petrov"}],
        "issns": ["0028-0836"],
    }
    records = import_publications(
        save_json(tmp_path, [row]), source="synthetic-elibrary", source_url="https://example.invalid/export"
    )
    assert records[0].doi == "10.1234/abc"
    assert records[0].citations[0].source == "synthetic-elibrary"
    assert records[0].citations[0].value == 7
    assert records[0].provenance[0].raw == row


@pytest.mark.parametrize("count", [-1, 1.5, True])
def test_publication_import_rejects_invalid_counts(tmp_path, count):
    row = {
        "title": "Synthetic work",
        "external_id": "123",
        "retrieved_at": "2026-09-10T09:00:00+00:00",
        "citations": count,
    }
    with pytest.raises(ValueError):
        import_publications(
            save_json(tmp_path, [row]), source="synthetic", source_url="https://example.invalid/export"
        )


def test_csv_publication_parses_json_array_cells_and_integer_year(tmp_path):
    path = tmp_path / "synthetic.csv"
    row = {
        "title": "Synthetic work",
        "external_id": "123",
        "retrieved_at": "2026-09-10T09:00:00+00:00",
        "citations": "7",
        "year": "2025",
        "authors": json.dumps([{"id": "a1", "name": "Ivan Petrov"}]),
        "issns": json.dumps(["0028-0836"]),
    }
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=row.keys())
        writer.writeheader()
        writer.writerow(row)
    records = import_publications(path, source="synthetic", source_url="https://example.invalid/export")
    assert records[0].year == 2025
    assert records[0].authors[0].name == "Ivan Petrov"
    assert records[0].issns == ["0028-0836"]


def test_invalid_nested_publication_cells_have_helpful_error(tmp_path):
    row = {
        "title": "Synthetic work",
        "external_id": "123",
        "retrieved_at": "2026-09-10T09:00:00+00:00",
        "authors": "Ivan Petrov",
    }
    with pytest.raises(ValueError, match="JSON array"):
        import_publications(
            save_json(tmp_path, [row]), source="synthetic", source_url="https://example.invalid/export"
        )


def test_orcid_filters_invalid_external_dois_and_retains_raw_evidence():
    from sciagg.providers.orcid import Orcid

    row = {
        "person": {"name": {"given-names": {"value": "Ivan"}, "family-name": {"value": "Petrov"}}},
        "activities-summary": {
            "works": {
                "group": [
                    {
                        "external-ids": {
                            "external-id": [
                                {
                                    "external-id-type": "doi",
                                    "external-id-relationship": "self",
                                    "external-id-value": value,
                                }
                                for value in ("10.1234/a", "invalid")
                            ]
                        }
                    }
                ]
            }
        },
    }

    class FixtureHttp:
        last_retrieved_at = "2026-09-10T00:00:00+00:00"

        def get(self, *args, **kwargs):
            return row

    author = Orcid(FixtureHttp()).author("0000-0002-1825-0097")
    assert author.dois == ["10.1234/a"]
    assert author.provenance[0].raw == row


def test_invalid_provider_identifiers_rejected_before_network():
    from sciagg.providers.orcid import Orcid
    from sciagg.providers.scopus import Scopus

    class NoNetwork:
        def get(self, *args, **kwargs):
            pytest.fail("Invalid identifier must be rejected before network")

    for operation in (
        lambda: Orcid(NoNetwork()).author("invalid"),
        lambda: Scopus(NoNetwork()).publication("invalid"),
        lambda: Scopus(NoNetwork()).journal("0028-0837"),
        lambda: Whitelist(NoNetwork()).journal("0028-0837"),
    ):
        with pytest.raises(ValueError):
            operation()
