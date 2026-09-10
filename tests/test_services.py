from dataclasses import asdict

from sciagg.exports import export
from sciagg.models import Author, Metric, Publication
from sciagg.providers.base import Batch, ProviderError
from sciagg.services import discover, profile, publication


class Primary:
    name = "primary"

    def publications(self, author, limit):
        return Batch(
            [Publication("p1", "Title", doi="10.1000/a", citations=[Metric("citation_count", 6, "primary")])],
            total=20,
            complete=False,
        )

    def search_authors(self, query, limit):
        return Batch(
            [
                Author("a1", "Ivanov", affiliations=["Physics"]),
                Author("a2", "Ivanov", affiliations=["Linguistics"]),
            ]
        )


class Enricher:
    name = "secondary"

    def publication(self, doi):
        return Publication("p2", "Title", doi=doi, citations=[Metric("citation_count", 2, "secondary")])


class Failure:
    name = "failed"

    def publication(self, doi):
        raise ProviderError(self.name, "missing credentials")


def test_subset_coverage_not_mutated_by_enrichment_and_metrics_stay_separate():
    result, works = profile(Primary(), Author("a1", "Ivanov"), [Enricher(), Failure()], 1)
    assert result["coverage"]["retrieved"] == 1
    assert not result["coverage"]["complete_in_primary_source"]
    assert len(works) == 1
    assert {m.source: m.value for m in works[0].citations} == {"primary": 6, "secondary": 2}
    assert {m["source"] for m in result["calculated_metrics"]} == {"primary", "secondary"}
    assert all(m["scope"] == "retrieved_corpus_subset" for m in result["calculated_metrics"])
    assert any(x["status"] == "unavailable" for x in result["providers"])


def test_failure_does_not_remove_successful_provider():
    works, result = publication([Failure(), Enricher()], "10.1000/a")
    assert len(works) == 1 and result["providers"][0]["status"] == "unavailable"


def test_name_search_keeps_namesakes_separate():
    result = discover([Primary()], "Ivanov")
    assert len(result["candidates"]) == 2
    assert all(not match["merge"] for match in result["matches"])


def test_exports_preserve_source_metrics_and_protect_formula_text(tmp_path):
    from openpyxl import load_workbook

    data = {
        "publications": [asdict(Publication("1", "=2+2", citations=[Metric("citation_count", 3, "test")]))],
        "coverage": {"complete_in_primary_source": False},
    }
    csv = tmp_path / "out.csv"
    xlsx = tmp_path / "out.xlsx"
    export(data, csv)
    export(data, xlsx)
    assert "'=2+2" in csv.read_text(encoding="utf-8-sig")
    assert csv.with_suffix(".profile.json").exists()
    book = load_workbook(xlsx)
    assert book["Publications"]["C2"].data_type == "s"
    assert book["Publications"]["C2"].value == "'=2+2"
    book.close()
