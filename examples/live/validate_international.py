"""Repeat the small live validation; requires network, writes public evidence only.

IDs were selected from OpenAlex candidate searches on 2026-09-10. They are
provider profiles, not an assertion that every linked work belongs to a person.
"""
import json
from dataclasses import asdict
from pathlib import Path

from sciagg.http import Http
from sciagg.models import utc_now
from sciagg.providers.crossref import Crossref
from sciagg.providers.openalex import OpenAlex


def main():
    output = Path(__file__).parent
    http = Http()
    openalex, crossref = OpenAlex(http), Crossref(http)
    results = {"validation_run_at": utc_now(), "mode": "bounded live validation",
               "selection": "Manually selected OpenAlex profiles from name-search candidates; identity and corpus not independently certified.",
               "authors": [], "crossref": {}}
    try:
        for query, identifier in [
            ("Jorge Hirsch", "A5036688434"),
            ("Konstantin Novoselov", "A5072248970"),
            ("Andre Geim", "A5058357018"),
        ]:
            candidates = openalex.search_authors(query, limit=3)
            author = openalex.author(identifier)
            works = openalex.publications(author, limit=3)
            results["authors"].append({
                "query": query, "candidates": asdict(candidates),
                "selected_provider_profile": asdict(author),
                "publication_sample": asdict(works),
                "interpretation": "Source profile metrics refer to the source profile; the 3-work sample is incomplete and is not used for an author h-index.",
            })
        work = crossref.publication("10.1073/pnas.0507655102")
        results["crossref"] = asdict(work)
        results["openalex_same_doi"] = asdict(openalex.publication(work.doi))
        (output / "international_validation.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        summary = {
            "validation_run_at": results["validation_run_at"],
            "authors": [{
                "query": entry["query"], "id": entry["selected_provider_profile"]["id"],
                "name": entry["selected_provider_profile"]["name"],
                "retrieved_at": entry["selected_provider_profile"]["provenance"][0]["retrieved_at"],
                "sample_count": len(entry["publication_sample"]["items"]),
                "source_reported_total": entry["publication_sample"]["total"],
                "sample_complete": entry["publication_sample"]["complete"],
            } for entry in results["authors"]],
            "doi": work.doi,
            "title": work.title,
            "crossref_citation_observation": [asdict(metric) for metric in work.citations],
            "openalex_citation_observation": results["openalex_same_doi"]["citations"],
            "warning": "Different citation providers and snapshots; do not sum these counts.",
        }
        (output / "international_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=True))
    finally:
        http.close()


if __name__ == "__main__":
    main()
