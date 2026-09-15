from dataclasses import asdict
from datetime import datetime, timezone

from .models import Metric
from .normalization import h_index
from .providers.base import attempt
from .resolution import deduplicate, match_authors


def discover(providers, query, limit=5):
    authors, statuses = [], []
    for provider in providers:
        if not hasattr(provider, "search_authors"):
            continue
        batch, status = attempt(provider.name, lambda p=provider: p.search_authors(query, limit))
        statuses.append(status)
        if batch:
            authors.extend(batch.items)
    matches = []
    for i, author in enumerate(authors):
        for other in authors[i + 1 :]:
            decision = match_authors(author, other)
            matches.append({"left": author.id, "right": other.id, **decision})
    return {
        "query": query,
        "candidates": [asdict(a) for a in authors],
        "matches": matches,
        "providers": statuses,
        "note": "Выберите устойчивый ID; ФИО само по себе не подтверждает личность",
    }


def publication(providers, doi):
    records, statuses = [], []
    for provider in providers:
        if not hasattr(provider, "publication"):
            continue
        item, status = attempt(provider.name, lambda p=provider: p.publication(doi))
        statuses.append(status)
        if item:
            records.append(item)
    merged, reviews = deduplicate(records)
    return merged, {"providers": statuses, "reviews": reviews}


def _observation_time(value):
    """Require an unambiguous instant; imported timestamps may use different offsets."""
    if not isinstance(value, str):
        raise ValueError("citation timestamp must be an ISO datetime")
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("citation timestamp must include a timezone")
    return instant.astimezone(timezone.utc)


def profile(primary, author, providers, limit=20):
    batch, status = attempt(primary.name, lambda: primary.publications(author, limit))
    records = list(batch.items) if batch else []
    statuses = [status]
    # The selected source ID determines the corpus. Enrichment never adds namesake search hits.
    for work in list(records):
        if work.doi:
            for provider in providers:
                if provider.name == primary.name or not hasattr(provider, "publication"):
                    continue
                item, response = attempt(provider.name, lambda p=provider, d=work.doi: p.publication(d))
                # Suppress repeating the same missing credentials error for every DOI.
                if response not in statuses:
                    statuses.append(response)
                if item:
                    records.append(item)
    works, review = deduplicate(records)
    metrics = []
    sources = {m.source for work in works for m in work.citations if m.kind == "citation_count"}
    if batch is not None:
        sources.add(primary.name)
    # An explicitly complete, zero-record primary result defines a known empty corpus.
    # Missing counts on nonempty records do not define zero citations or h=0.
    empty_corpus = bool(batch is not None and batch.complete and batch.total == 0 and not works)
    for source in sorted(sources):
        counts, snapshots = [], set()
        conflicts, invalid, invalid_timestamps = [], [], []
        for work in works:
            observations = [m for m in work.citations if m.source == source and m.kind == "citation_count"]
            if not observations:
                continue
            # Compare instants, not strings: 10:00+03:00 precedes 09:00+00:00.
            # If a timestamp is malformed, do not silently fall back to an older observation.
            try:
                dated = [(_observation_time(m.retrieved_at), m) for m in observations]
            except (ValueError, TypeError, OverflowError):
                invalid_timestamps.append(work.id)
                continue
            latest = max(instant for instant, _ in dated)
            latest_values = [m.value for instant, m in dated if instant == latest]
            # Validate before hashing: remote JSON may contain lists/dicts instead of counts.
            if any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in latest_values
            ):
                invalid.append(work.id)
                continue
            values = set(latest_values)
            if len(values) != 1:
                conflicts.append(work.id)
                continue
            value = values.pop()
            counts.append(value)
            snapshots.add(latest.isoformat())
        scope = "retrieved_corpus_subset"
        sufficient = bool(counts) or (empty_corpus and source == primary.name)
        value = h_index(counts) if sufficient else None
        metrics.append(
            {
                **asdict(Metric("h_index", value, source, scope=scope)),
                "status": "ok" if sufficient else "insufficient_data",
                "publications_with_citations": len(counts),
                "retrieved_publications": len(works),
                "citation_snapshot_dates": sorted(snapshots),
                "excluded_conflicts": conflicts,
                "excluded_invalid_counts": invalid,
                "excluded_invalid_timestamps": invalid_timestamps,
                "note": (
                    "h=0 для явно пустой завершённой выборки первичного источника"
                    if empty_corpus and sufficient
                    else "h по полученной выборке; не объявляется полным h-index автора"
                    if sufficient
                    else "Нет пригодных наблюдений цитирований; h не рассчитан"
                ),
            }
        )
    result = {
        "author": asdict(author),
        "publications": [asdict(w) for w in works],
        "calculated_metrics": metrics,
        "providers": statuses,
        "reviews": review,
        "coverage": {
            "source": primary.name,
            "reported_total": batch.total if batch else None,
            "retrieved": len(batch.items) if batch else 0,
            "complete_in_primary_source": bool(batch and batch.complete),
            "requested_limit": limit,
        },
    }
    if batch is None:
        result["error"] = "primary_publications_unavailable"
    return result, works
