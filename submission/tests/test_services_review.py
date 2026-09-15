"""Regression cases found in independent review of profile calculations."""

import pytest

from sciagg.models import Author, Metric, Publication
from sciagg.providers.base import Batch, ProviderError
from sciagg.services import profile

STAMP = "2026-09-10T09:00:00+00:00"


class Primary:
    name = "primary"

    def __init__(self, batch):
        self.batch = batch

    def publications(self, author, limit):
        return self.batch


def calculate(observations):
    work = Publication(id="p1", title="Work", citations=observations)
    result, _ = profile(Primary(Batch([work], total=1, complete=True)), Author(id="a1"), [])
    return result["calculated_metrics"][0]


def count(value, stamp=STAMP):
    return Metric("citation_count", value, "primary", stamp)


def test_latest_uses_chronology_across_timezones():
    metric = calculate([count(0, "2026-09-10T10:00:00+03:00"), count(10)])
    assert metric["value"] == 1
    assert metric["citation_snapshot_dates"] == [STAMP]


def test_equal_instants_with_conflicting_values_are_excluded():
    metric = calculate([count(0, "2026-09-10T12:00:00+03:00"), count(10)])
    assert metric["value"] is None and metric["status"] == "insufficient_data"
    assert metric["excluded_conflicts"] == ["p1"]


def test_equal_instants_same_value_are_one_observation():
    metric = calculate([count(10, "2026-09-10T12:00:00+03:00"), count(10, "2026-09-10T09:00:00Z")])
    assert metric["value"] == 1 and metric["publications_with_citations"] == 1
    assert not metric["excluded_conflicts"]


@pytest.mark.parametrize("value", [{}, [], None, True, -1, "10", 1.5])
def test_malformed_latest_counts_are_reported_without_crashing(value):
    metric = calculate([count(10, "2026-09-09T09:00:00Z"), count(value)])
    assert metric["value"] is None
    assert metric["status"] == "insufficient_data"
    assert metric["excluded_invalid_counts"] == ["p1"]
    assert metric["publications_with_citations"] == 0


def test_missing_observations_do_not_imply_zero_h():
    metric = calculate([])
    assert metric["value"] is None and metric["status"] == "insufficient_data"


def test_observed_zero_is_a_valid_zero_h():
    metric = calculate([count(0)])
    assert metric["value"] == 0 and metric["status"] == "ok"
    assert metric["publications_with_citations"] == 1


@pytest.mark.parametrize("stamp", ["invalid", "2026-09-10T09:00:00", None])
def test_invalid_or_timezone_free_timestamp_does_not_choose_fallback(stamp):
    metric = calculate([count(10, "2026-09-09T09:00:00Z"), count(0, stamp)])
    assert metric["value"] is None and metric["excluded_invalid_timestamps"] == ["p1"]


def test_known_complete_empty_corpus_has_zero_h():
    result, _ = profile(Primary(Batch([], total=0, complete=True)), Author(id="a1"), [])
    metric = result["calculated_metrics"][0]
    assert metric["value"] == 0 and metric["status"] == "ok"
    assert "error" not in result


def test_empty_unknown_corpus_has_no_numeric_h():
    result, _ = profile(Primary(Batch([], total=None, complete=False)), Author(id="a1"), [])
    metric = result["calculated_metrics"][0]
    assert metric["value"] is None and metric["status"] == "insufficient_data"


def test_primary_failure_marks_profile_error_but_preserves_author():
    class Failed:
        name = "primary"

        def publications(self, author, limit):
            raise ProviderError(self.name, "offline cache miss")

    result, works = profile(Failed(), Author(id="a1", name="Known author"), [])
    assert result["error"] == "primary_publications_unavailable"
    assert result["author"]["id"] == "a1" and works == []
    assert result["calculated_metrics"] == []
