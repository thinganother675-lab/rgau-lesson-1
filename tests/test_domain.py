import unittest
from dataclasses import asdict

from sciagg.models import Author, Metric, Provenance, Publication
from sciagg.normalization import (
    h_index,
    normalize_doi,
    normalize_issn,
    normalize_name,
    normalize_orcid,
    transliterate_name,
)
from sciagg.resolution import deduplicate, match_authors, match_publications


class NormalizationTests(unittest.TestCase):
    def test_doi_url_and_legal_punctuation(self):
        self.assertEqual(
            normalize_doi(" HTTPS://DOI.ORG/10.1234/ABC%28A%29.?tracking=yes "), "10.1234/abc(a)."
        )
        self.assertEqual(normalize_doi("doi:10.1234/Статья;A"), "10.1234/статья;a")
        for value in (
            None,
            "10.123/no",
            "https://evil.example/10.1234/a",
            "10.1234/has space",
            "10.１２３４/a",
            "https://[bad/10.1234/a",
        ):
            self.assertIsNone(normalize_doi(value))

    def test_issn_checksum(self):
        self.assertEqual(normalize_issn("00280836"), "0028-0836")
        self.assertEqual(normalize_issn("2434-561x"), "2434-561X")
        self.assertIsNone(normalize_issn("0028-0837"))
        self.assertIsNone(normalize_issn("0000000"))

    def test_orcid_and_names(self):
        self.assertEqual(normalize_orcid("https://orcid.org/0000-0002-1825-0097"), "0000-0002-1825-0097")
        self.assertIsNone(normalize_orcid("0000-0002-1825-0098"))
        self.assertEqual(normalize_name("  Иванов, И. И. "), "иванов и и")
        self.assertEqual(normalize_name("Jose\u0301"), normalize_name("José"))
        self.assertNotEqual(normalize_name("Иванов"), normalize_name("Ivanov"))
        self.assertEqual(transliterate_name("Иванов"), "ivanov")

    def test_h_index_boundaries(self):
        self.assertEqual(h_index([10, 8, 5, 4, 3, 1]), 4)
        self.assertEqual(h_index([]), 0)
        self.assertEqual(h_index([0, 0]), 0)
        self.assertEqual(h_index([100]), 1)
        self.assertEqual(h_index([3, 3, 3]), 3)
        for bad in (-1, 1.5, float("nan"), float("inf"), True, None):
            with self.assertRaises(ValueError):
                h_index([bad])


class ResolutionTests(unittest.TestCase):
    def publication(self, identifier, doi=None, year=2024, name="Ivan Petrov"):
        return Publication(
            id=identifier, title="Soil carbon: results", doi=doi, year=year, authors=[Author(name=name)]
        )

    def test_name_or_transliteration_never_sufficient_for_authors(self):
        self.assertFalse(match_authors(Author(name="Ivan Petrov"), Author(name="Ivan Petrov"))["merge"])
        self.assertFalse(match_authors(Author(name="Иван Петров"), Author(name="Ivan Petrov"))["merge"])

    def test_author_id_conflict_overrides_shared_id(self):
        left = Author(identifiers={"orcid": "0000-0002-1825-0097", "openalex": "A1"})
        right = Author(identifiers={"orcid": "https://orcid.org/0000-0002-1825-0097", "openalex": "A2"})
        self.assertFalse(match_authors(left, right)["merge"])
        right.identifiers.pop("openalex")
        self.assertTrue(match_authors(left, right)["merge"])

    def test_multiple_weak_signals_require_review(self):
        left = Author(
            name="Ivan Petrov", dois=["10.1234/a"], affiliations=["University"], coauthors=["Anna Ivanova"]
        )
        result = match_authors(left, left)
        self.assertGreaterEqual(result["confidence"], 0.8)
        self.assertFalse(result["merge"])

    def test_publication_fallback_and_conflicts(self):
        left, right = self.publication("a"), self.publication("b")
        self.assertTrue(match_publications(left, right)["merge"])
        right.year = 2025
        self.assertFalse(match_publications(left, right)["merge"])
        right.year = None
        self.assertFalse(match_publications(left, right)["merge"])
        left.doi, right.doi = "10.1234/a", "10.1234/b"
        self.assertFalse(match_publications(left, right)["merge"])
        right.doi = "https://doi.org/10.1234/A"
        self.assertTrue(match_publications(left, right)["merge"])

    def test_initials_fuzzy_and_invalid_doi_not_auto_merged(self):
        left, right = self.publication("a", name="I Petrov"), self.publication("b", name="I Petrov")
        self.assertFalse(match_publications(left, right)["merge"])
        left, right = self.publication("a"), self.publication("b")
        right.title += " revised"
        self.assertFalse(match_publications(left, right)["merge"])
        right.title = left.title
        right.doi = "invalid"
        self.assertFalse(match_publications(left, right)["merge"])

    def test_merge_preserves_source_metrics_and_conflicts_without_mutation(self):
        left, right = self.publication("a", "10.1234/a"), self.publication("b", "10.1234/a", 2025)
        left.citations = [Metric("citations", 10, "crossref")]
        right.citations = [Metric("citations", 17, "openalex")]
        left.provenance, right.provenance = [Provenance("crossref")], [Provenance("openalex")]
        left.source_ids, right.source_ids = {"crossref": "a"}, {"openalex": "b"}
        left.extra, right.extra = {"type": "article"}, {"type": "review"}
        before = asdict(left)
        publications, audit = deduplicate([left, right])
        self.assertEqual(len(publications), 1)
        self.assertEqual([m.value for m in publications[0].citations], [10, 17])
        self.assertEqual(len(publications[0].provenance), 2)
        fields = {c["field"] for c in publications[0].extra["merge_conflicts"]}
        self.assertIn("year", fields)
        self.assertIn("extra.type", fields)
        self.assertEqual(publications[0].source_ids, {"crossref": "a", "openalex": "b"})
        self.assertEqual(asdict(left), before)
        self.assertTrue(audit[0]["merge"])

    def test_missing_doi_cannot_bridge_conflicting_dois(self):
        a, bridge, b = (
            self.publication("a", "10.1234/a"),
            self.publication("bridge"),
            self.publication("b", "10.1234/b"),
        )
        for order in ([a, bridge, b], [bridge, a, b], [a, b, bridge]):
            records, _ = deduplicate(order)
            self.assertGreaterEqual(len(records), 2)
            for record in records:
                dois = {p["doi"] for p in record.extra.get("merged_records", []) if p["doi"]}
                self.assertLessEqual(len(dois), 1)

    def test_conflicting_dois_have_audit_and_snapshots_do_not_nest(self):
        records = [self.publication(str(i), "10.1234/a") for i in range(4)]
        merged, _ = deduplicate(records)
        self.assertEqual(len(merged[0].extra["merged_records"]), 4)
        self.assertTrue(all("merged_records" not in p["extra"] for p in merged[0].extra["merged_records"]))
        separate, audit = deduplicate([records[0], self.publication("different", "10.1234/b")])
        self.assertEqual(len(separate), 2)
        self.assertFalse(audit[0]["merge"])
        self.assertIn("conflicting DOI", audit[0]["reasons"][0])

    def test_source_specific_ids_prove_record_identity_and_conflicts_take_precedence(self):
        left = Publication(id="left", title="Earlier title", year=2024, source_ids={"openalex": "W123"})
        right = Publication(id="right", title="Updated title", year=2025, source_ids={"openalex": "W123"})
        self.assertTrue(match_publications(left, right)["merge"])
        merged, _ = deduplicate([left, right])
        self.assertEqual(len(merged), 1)
        self.assertIn("Updated title", merged[0].alternative_titles)
        left.doi, right.doi = "10.1234/a", "10.1234/b"
        self.assertFalse(match_publications(left, right)["merge"])
        right.doi = left.doi
        right.source_ids["openalex"] = "W456"
        self.assertFalse(match_publications(left, right)["merge"])
        right.source_ids = {"scopus": "W123"}
        left.doi, right.doi = None, None
        self.assertFalse(match_publications(left, right)["merge"])


if __name__ == "__main__":
    unittest.main()
