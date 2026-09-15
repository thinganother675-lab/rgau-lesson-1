"""Offline contract tests with deliberately small, synthetic provider responses."""

import pytest

from sciagg.models import Author
from sciagg.providers.crossref import Crossref
from sciagg.providers.openalex import OpenAlex

STAMP = "2026-09-10T00:00:00+00:00"
ORCID = "0000-0002-1825-0097"


class FakeHttp:
    last_retrieved_at = STAMP

    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def get(self, source, url, *, params=None, headers=None):
        self.calls.append((source, url, params, headers))
        return next(self.replies)


def cr(doi="10.1234/test", **kwargs):
    return {"DOI": doi, "title": ["Example"], **kwargs}


def oa(identifier="W1", **kwargs):
    return {"id": "https://openalex.org/" + identifier, "display_name": "Example", **kwargs}


def test_crossref_citations_are_not_reference_count_and_preserve_zero():
    record = cr(**{"is-referenced-by-count": 0, "references-count": 999})
    work = Crossref.parse_publication(record, STAMP)
    assert [(x.value, x.source, x.retrieved_at) for x in work.citations] == [(0, "crossref", STAMP)]
    assert Crossref.parse_publication(cr(), STAMP).citations == []
    assert work.provenance[0].raw == record


def test_crossref_authorships_with_same_name_remain_distinct():
    row = cr(author=[{"given": "A", "family": "Smith"}, {"given": "A", "family": "Smith"}])
    work = Crossref.parse_publication(row, STAMP)
    assert work.authors[0].id != work.authors[1].id
    assert not work.authors[0].identifiers


def test_crossref_exact_orcid_and_dates():
    record = cr(
        author=[{"ORCID": "https://orcid.org/" + ORCID}],
        published={"date-parts": [[2020]]},
        ISSN=["1234-5679", "bad"],
    )
    work = Crossref.parse_publication(record, STAMP)
    assert work.authors[0].identifiers["orcid"] == ORCID
    assert work.year == 2020 and work.issns == ["1234-5679"]


def test_crossref_refuses_name_only_corpus_without_network():
    http = FakeHttp([])
    batch = Crossref(http).publications(Author(name="Smith"))
    assert not batch.complete and not batch.items and not http.calls


def test_crossref_cursor_cap_does_not_claim_complete():
    http = FakeHttp(
        [{"status": "ok", "message": {"items": [cr()], "total-results": 50, "next-cursor": "next"}}]
    )
    batch = Crossref(http, mailto="").publications(Author(identifiers={"orcid": ORCID}), limit=1)
    assert not batch.complete and batch.total == 50
    assert http.calls[0][2]["filter"] == "orcid:" + ORCID
    assert http.calls[0][2]["cursor"] == "*"


def test_openalex_work_handles_null_source_and_preserves_doi():
    work = OpenAlex.parse_publication(oa(doi="https://doi.org/10.1234/ABC", primary_location=None), STAMP)
    assert work.doi == "10.1234/abc" and work.issns == [] and work.citations == []


def test_openalex_author_uses_only_openalex_metrics_and_valid_orcid():
    person = OpenAlex.parse_author(
        oa("A1", orcid="invalid", cited_by_count=0, summary_stats={"h_index": 0, "2yr_mean_citedness": 99}),
        STAMP,
    )
    assert "orcid" not in person.identifiers
    assert {m.kind for m in person.metrics} == {"citation_count", "h_index"}
    assert all(m.source == "openalex" and m.value == 0 for m in person.metrics)


def test_openalex_pagination_deduplicates_and_completes():
    http = FakeHttp(
        [
            {"results": [oa("W1")], "meta": {"count": 2, "next_cursor": "next"}},
            {"results": [oa("W1"), oa("W2")], "meta": {"count": 2, "next_cursor": None}},
        ]
    )
    batch = OpenAlex(http, api_key="").publications(Author(id="https://openalex.org/A1"), limit=3)
    assert batch.complete and len(batch.items) == 2
    assert http.calls[1][2]["cursor"] == "next"


def test_openalex_partial_no_cursor_with_higher_total_is_not_complete():
    http = FakeHttp([{"results": [oa()], "meta": {"count": 100, "next_cursor": None}}])
    batch = OpenAlex(http, api_key="").publications(Author(id="A1"), limit=20)
    assert not batch.complete


def test_openalex_api_key_stays_in_header_and_page_size_supported():
    http = FakeHttp([{"results": [], "meta": {"count": 0}}])
    OpenAlex(http, api_key="fixture-token").search_authors("Smith", limit=101)
    _, url, params, headers = http.calls[0]
    assert params["per_page"] == 100 and "api_key" not in params
    assert "fixture-token" not in url and headers == {"Authorization": "Bearer fixture-token"}


@pytest.mark.parametrize("provider", [Crossref, OpenAlex])
def test_invalid_doi_does_not_reach_http(provider):
    http = FakeHttp([])
    with pytest.raises(ValueError):
        provider(http).publication("https://malicious.example/10.1234/a")
    assert not http.calls


def test_openalex_repeated_cursor_is_bounded():
    http = FakeHttp(
        [
            {"results": [oa()], "meta": {"count": 50, "next_cursor": "next"}},
            {"results": [oa()], "meta": {"count": 50, "next_cursor": "next"}},
        ]
    )
    batch = OpenAlex(http, api_key="").publications(Author(id="A1"), limit=20)
    assert len(http.calls) == 2 and not batch.complete and len(batch.items) == 1
