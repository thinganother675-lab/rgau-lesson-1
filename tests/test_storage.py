import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sciagg.models import Author, Journal, Metric, Provenance, Publication
from sciagg.storage import Store


class StorageTests(unittest.TestCase):
    def test_roundtrip_relations_and_idempotent_publications(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.sqlite"
            publication = Publication(
                id="p1",
                title="Почва",
                authors=[Author(id="a1", name="Иван Петров")],
                citations=[Metric("citations", 4, "crossref"), Metric("citations", 7, "openalex")],
                provenance=[Provenance("crossref", raw={"untouched": [1, 2]})],
            )
            with Store(path) as store:
                store.save_publications([publication])
                store.save_publications([publication])
                self.assertEqual(
                    store.connection.execute("SELECT count(*) FROM authorships").fetchone()[0], 1
                )
                self.assertEqual(store.connection.execute("SELECT count(*) FROM metrics").fetchone()[0], 2)
                self.assertEqual(store.connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            with Store(path) as store:
                result = store.get_publication("p1")
                self.assertEqual(result["title"], "Почва")
                self.assertEqual([m["value"] for m in result["citations"]], [4, 7])
                self.assertEqual(result["provenance"][0]["raw"], {"untouched": [1, 2]})
                self.assertIsNone(store.get_publication("missing"))

    def test_journal_alias_lookup_preserves_classification_dimensions(self):
        with Store(":memory:") as store:
            store.save_journal(
                Journal(
                    issns=["00280836", "1476-4687"],
                    title="Nature",
                    classifications=[{"source": "fixture", "year": 2023, "category": "A", "quartile": "Q1"}],
                    provenance=[Provenance("fixture")],
                )
            )
            store.save_journal(
                Journal(
                    issns=["0028-0836"],
                    classifications=[{"source": "fixture", "year": 2024, "category": "B", "quartile": "Q2"}],
                )
            )
            result = store.get_journal("14764687")
            self.assertEqual(len(result["classifications"]), 2)
            self.assertEqual(result["title"], "Nature")
            self.assertEqual(
                store.connection.execute("SELECT count(*) FROM journal_classifications").fetchone()[0], 2
            )
            self.assertIsNone(store.get_journal("0028-0837"))
            with self.assertRaises(ValueError):
                store.save_journal(Journal(issns=["0028-0837"]))

    def test_author_updates_preserve_metrics_and_reject_identifier_conflicts(self):
        with Store(":memory:") as store:
            store.save_author(
                Author(
                    id="a",
                    name="Ivan Petrov",
                    identifiers={"openalex": "A1"},
                    metrics=[Metric("h_index", 2, "openalex")],
                )
            )
            store.save_author(Author(id="a", name="Иван Петров", metrics=[Metric("h_index", 3, "fixture")]))
            self.assertEqual(len(store.get_author("a")["metrics"]), 2)
            self.assertIn("Ivan Petrov", store.get_author("a")["variants"])
            with self.assertRaises(ValueError):
                store.save_author(Author(id="a", identifiers={"openalex": "A2"}))
            self.assertEqual(store.get_author("a")["identifiers"]["openalex"], "A1")

    def test_publication_batch_atomicity(self):
        with Store(":memory:") as store:
            with self.assertRaises(ValueError):
                store.save_publications(
                    [
                        Publication(id="good", title="Good"),
                        Publication(
                            id="bad", title="Bad", citations=[Metric("citations", float("nan"), "fixture")]
                        ),
                    ]
                )
            self.assertEqual(store.list_publications(), [])

    def test_publication_refresh_retains_history_and_rejects_doi_collision(self):
        with Store(":memory:") as store:
            first = Publication(
                id="stable",
                title="Original title",
                doi="10.1234/a",
                year=2025,
                authors=[Author(id="a1", name="Ivan Petrov")],
                citations=[Metric("citation_count", 4, "fixture", "2025-01-01T00:00:00+00:00")],
                provenance=[Provenance("fixture", raw={"version": 1})],
            )
            store.save_publications([first])
            store.save_publications(
                [
                    Publication(
                        id="stable",
                        citations=[Metric("citation_count", 7, "fixture", "2026-01-01T00:00:00+00:00")],
                        provenance=[Provenance("fixture", raw={"version": 2})],
                    )
                ]
            )
            saved = store.get_publication("stable")
            self.assertEqual(saved["title"], "Original title")
            self.assertEqual(saved["doi"], "10.1234/a")
            self.assertEqual(saved["year"], 2025)
            self.assertEqual(saved["authors"][0]["name"], "Ivan Petrov")
            self.assertEqual([m["value"] for m in saved["citations"]], [4, 7])
            self.assertEqual(len(saved["provenance"]), 2)
            self.assertEqual(
                store.connection.execute(
                    "SELECT count(*) FROM metrics WHERE owner_type='publication'"
                ).fetchone()[0],
                2,
            )
            with self.assertRaises(ValueError):
                store.save_publications([Publication(id="stable", doi="10.1234/b")])
            self.assertEqual(store.get_publication("stable"), saved)

    def test_journal_batch_quarantines_bridge_without_partial_issn_mappings(self):
        with Store(":memory:") as store:
            records = [
                Journal(["0028-0836"], "A"),
                Journal(["2434-561X"], "B"),
                Journal(
                    ["1476-4687", "0028-0836", "2434-561X"],
                    "Ambiguous bridge",
                    provenance=[Provenance("fixture", "bridge-id")],
                ),
                Journal(["0036-8075"], "C"),
            ]
            report = store.save_journals(records, batch_size=3)
            self.assertEqual(report["stored"], 3)
            self.assertEqual(len(report["rejected"]), 1)
            self.assertEqual(report["rejected"][0]["index"], 3)
            self.assertEqual(
                report["rejected"][0]["source_ids"], [{"source": "fixture", "external_id": "bridge-id"}]
            )
            self.assertIn("different stored journals", report["rejected"][0]["reason"])
            self.assertIsNone(store.get_journal("1476-4687"))
            for issn, title in (("0028-0836", "A"), ("2434-561X", "B"), ("0036-8075", "C")):
                self.assertEqual(store.get_journal(issn)["title"], title)
            self.assertEqual(store.connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_journal_batch_rolls_back_late_row_failure_and_keeps_good_rows(self):
        with Store(":memory:") as store:
            original_metadata = store._metadata

            def fail_late(owner_type, owner_id, metrics, provenance):
                if provenance and provenance[0]["external_id"] == "bad":
                    raise ValueError("Synthetic late metadata failure")
                return original_metadata(owner_type, owner_id, metrics, provenance)

            records = [
                Journal(["0028-0836"], "A"),
                Journal(["1476-4687"], "Bad", provenance=[Provenance("fixture", "bad")]),
                Journal(["2434-561X"], "B"),
            ]
            with patch.object(store, "_metadata", side_effect=fail_late):
                report = store.save_journals(records)
            self.assertEqual(report["stored"], 2)
            self.assertEqual(len(report["rejected"]), 1)
            self.assertIsNone(store.get_journal("1476-4687"))
            self.assertEqual(store.connection.execute("SELECT count(*) FROM journals").fetchone()[0], 2)

    def test_journal_batches_commit_per_chunk_and_respect_caller_transaction(self):
        with Store(":memory:") as store:
            statements = []
            store.connection.set_trace_callback(statements.append)
            report = store.save_journals([Journal(title=f"Synthetic {i}") for i in range(5)], batch_size=2)
            self.assertEqual(report, {"stored": 5, "rejected": []})
            self.assertEqual(sum(sql == "COMMIT" for sql in statements), 3)
            store.connection.execute("BEGIN")
            store.save_journals([Journal(["0028-0836"], "Uncommitted")])
            self.assertTrue(store.connection.in_transaction)
            store.connection.rollback()
            self.assertIsNone(store.get_journal("0028-0836"))


if __name__ == "__main__":
    unittest.main()
