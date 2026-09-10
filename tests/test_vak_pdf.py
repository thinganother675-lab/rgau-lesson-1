"""VAK table boundaries and errors, without requiring a network or full PDF."""

import pytest

from sciagg.providers.vak_pdf import parse_vak_text


def row(*cells):
    return "\t".join(cells)


def test_vak_historical_issn_does_not_become_current_identifier():
    text = "\n".join(
        [
            row("1.", "Acta biomedica scientifica", "2541-9420", "3.1.21. Педиатрия", "с 01.02.2022", "1"),
            row("", "(прежнее название: ISSN 1811-0649)", "", "3.1.22. Урология", "", "2"),
            row("2.", "Other journal", "2079-3537", "5.1.1.", "с 01.01.2023", "2"),
        ]
    )
    parsed = parse_vak_text(text, "https://example.test/official.pdf", "2026-08-14")
    assert len(parsed) == 2
    assert parsed[0].issns == ["2541-9420"]
    assert "1811-0649" in parsed[0].title
    assert parsed[0].provenance[0].raw["pages"] == ["1", "2"]
    assert parsed[0].classifications[0]["effective_date"] == "2026-08-14"
    assert parsed[0].classifications[0]["category"] is None
    assert parsed[1].provenance[0].raw["specialty_date_lines"][0]["specialty"] == "5.1.1."


def test_vak_issn_typography_and_quarantine():
    parsed = parse_vak_text(
        "\n".join(
            [
                row("1.", "Alma mater", "1026-955Х", "", "", "1"),
                row("2.", "Radiology", "16823524", "", "", "1"),
                row("3.", "Invalid", "1234-5678", "", "", "1"),
                row("4.", "Missing", "", "", "", "1"),
            ]
        )
    )
    assert [j.issns for j in parsed] == [["1026-955X"], ["1682-3524"]]
    assert [r["row"] for r in parsed.rejected] == [3, 4]
    assert parsed[0].provenance[0].raw["issn"] == ["1026-955Х"]
    assert parsed.warnings


def test_vak_unsupported_text_fails_instead_of_silent_empty_import():
    with pytest.raises(ValueError, match="six TSV"):
        parse_vak_text("a random PDF text dump")
    with pytest.raises(ValueError, match="No numbered"):
        parse_vak_text(row("", "header", "", "", "", "1"))


def test_vak_missing_row_number_is_audited():
    parsed = parse_vak_text(row("2.", "Scientific visualization", "2079-3537", "", "", "1"))
    assert any("sequence" in s for s in parsed.warnings)
