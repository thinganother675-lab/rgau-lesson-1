"""Explainable, deliberately conservative record linkage."""

from copy import deepcopy
from dataclasses import asdict
from difflib import SequenceMatcher

from .models import Author, Publication
from .normalization import normalize_doi, normalize_name, normalize_orcid, normalize_title


def _result(confidence: float, merge: bool, *reasons: str) -> dict:
    return {"confidence": confidence, "merge": merge, "reasons": list(reasons)}


def _identifiers(author: Author) -> dict[str, str]:
    result = {}
    for key, value in author.identifiers.items():
        key = key.strip().casefold()
        if not value:
            continue
        normalized = normalize_orcid(value) if key == "orcid" else str(value).strip()
        if normalized:
            result[key] = normalized
    return result


def match_authors(left: Author, right: Author) -> dict:
    a, b = _identifiers(left), _identifiers(right)
    conflicts = [key for key in a.keys() & b.keys() if a[key] != b[key]]
    if conflicts:
        return _result(0.0, False, "conflicting identifiers: " + ", ".join(sorted(conflicts)))
    shared = [key for key in a.keys() & b.keys() if a[key] == b[key]]
    if shared:
        return _result(1.0, True, "matching identifiers: " + ", ".join(sorted(shared)))
    names_a = {normalize_name(n) for n in [left.name, *left.variants]} - {""}
    names_b = {normalize_name(n) for n in [right.name, *right.variants]} - {""}
    name_match = bool(names_a & names_b)
    dois_a = {normalize_doi(d) for d in left.dois} - {None}
    dois_b = {normalize_doi(d) for d in right.dois} - {None}
    affiliations = (
        {normalize_name(n) for n in left.affiliations} & {normalize_name(n) for n in right.affiliations}
    ) - {""}
    coauthors = (
        {normalize_name(n) for n in left.coauthors} & {normalize_name(n) for n in right.coauthors}
    ) - {""}
    reasons = []
    if name_match:
        reasons.append("normalized name agrees; homonyms remain possible")
    if dois_a & dois_b:
        reasons.append("publication DOI overlap")
    if affiliations:
        reasons.append("affiliation overlap")
    if coauthors:
        reasons.append("coauthor overlap")
    score = 0.2 * name_match + 0.3 * bool(dois_a & dois_b) + 0.2 * bool(affiliations) + 0.2 * bool(coauthors)
    return _result(
        round(score, 2), False, *(reasons + ["manual review required without a shared identifier"])
    )


def _author_lists_agree(left: list[Author], right: list[Author]) -> bool:
    if not left or len(left) != len(right):
        return False
    for a, b in zip(left, right, strict=True):
        match = match_authors(a, b)
        if any(reason.startswith("conflicting identifiers") for reason in match["reasons"]):
            return False
        if match["merge"]:
            continue
        name_a, name_b = normalize_name(a.name), normalize_name(b.name)
        if not name_a or name_a != name_b:
            return False
        # An isolated surname or initials are too weak for automatic linkage.
        tokens = name_a.split()
        if len(tokens) < 2 or sum(len(token) > 1 for token in tokens) < 2:
            return False
    return True


def match_publications(left: Publication, right: Publication) -> dict:
    doi_a, doi_b = normalize_doi(left.doi), normalize_doi(right.doi)
    if doi_a and doi_b and doi_a != doi_b:
        return _result(0.0, False, "conflicting DOI values; keep separate")
    ids_a = {
        str(key).strip().casefold(): str(value).strip() for key, value in left.source_ids.items() if value
    }
    ids_b = {
        str(key).strip().casefold(): str(value).strip() for key, value in right.source_ids.items() if value
    }
    conflicts = [key for key in ids_a.keys() & ids_b.keys() if ids_a[key] != ids_b[key]]
    if conflicts:
        return _result(0.0, False, "conflicting source-specific identifiers: " + ", ".join(sorted(conflicts)))
    # Malformed supplied identifiers cannot quietly become missing evidence.
    if (left.doi and not doi_a) or (right.doi and not doi_b):
        return _result(0.0, False, "invalid supplied DOI; manual review required")
    if doi_a and doi_b:
        return _result(1.0, True, "exact normalized DOI")
    shared = [key for key in ids_a.keys() & ids_b.keys() if ids_a[key] == ids_b[key]]
    if shared:
        return _result(1.0, True, "exact source-specific identifiers: " + ", ".join(sorted(shared)))
    title_a, title_b = normalize_title(left.title), normalize_title(right.title)
    if not title_a or not title_b:
        return _result(0.0, False, "missing title and no shared DOI")
    same_year = left.year is not None and left.year == right.year
    same_authors = _author_lists_agree(left.authors, right.authors)
    if title_a == title_b and same_year and same_authors:
        return _result(0.97, True, "exact normalized title, year and ordered author evidence")
    score = SequenceMatcher(None, title_a, title_b).ratio()
    reasons = ["title similarity %.3f" % score]
    if left.year is not None and right.year is not None and not same_year:
        reasons.append("conflicting publication years")
    elif not same_year:
        reasons.append("missing publication year")
    if not same_authors:
        reasons.append("insufficient or conflicting author evidence")
    reasons.append("manual review required; fuzzy similarity is not identity")
    return _result(round(min(score * 0.8, 0.89), 3), False, *reasons)


def _union(left: list, right: list) -> list:
    out = deepcopy(left)
    for value in right:
        if value not in out:
            out.append(deepcopy(value))
    return out


def _merge(left: Publication, right: Publication) -> Publication:
    merged = deepcopy(left)
    conflicts = deepcopy(merged.extra.get("merge_conflicts", []))
    for name in ("title", "year", "journal", "id"):
        old, new = getattr(merged, name), getattr(right, name)
        if not old and new:
            setattr(merged, name, deepcopy(new))
        elif old and new and old != new:
            conflicts = _union(conflicts, [{"field": name, "values": [old, new]}])
    merged.doi = normalize_doi(left.doi) or normalize_doi(right.doi)
    merged.alternative_titles = _union(left.alternative_titles, right.alternative_titles)
    if right.title and right.title != merged.title:
        merged.alternative_titles = _union(merged.alternative_titles, [right.title])
    merged.issns = _union(left.issns, right.issns)
    merged.citations = _union(left.citations, right.citations)
    merged.provenance = _union(left.provenance, right.provenance)
    if not merged.authors:
        merged.authors = deepcopy(right.authors)
    elif right.authors:
        if _author_lists_agree(merged.authors, right.authors):
            for author, other in zip(merged.authors, right.authors, strict=True):
                author.identifiers.update(other.identifiers)
                for field in (
                    "variants",
                    "affiliations",
                    "subjects",
                    "dois",
                    "coauthors",
                    "metrics",
                    "provenance",
                ):
                    setattr(author, field, _union(getattr(author, field), getattr(other, field)))
                if other.name != author.name:
                    author.variants = _union(author.variants, [other.name])
        elif merged.authors != right.authors:
            conflicts = _union(
                conflicts,
                [
                    {
                        "field": "authors",
                        "values": [[asdict(a) for a in merged.authors], [asdict(a) for a in right.authors]],
                    }
                ],
            )
    for key, value in right.source_ids.items():
        if key in merged.source_ids and merged.source_ids[key] != value:
            conflicts = _union(
                conflicts, [{"field": "source_ids." + key, "values": [merged.source_ids[key], value]}]
            )
        else:
            merged.source_ids[key] = value
    for key, value in right.extra.items():
        if key == "merge_conflicts":
            conflicts = _union(conflicts, value)
        elif key == "merged_records":
            continue
        elif key in merged.extra and merged.extra[key] != value:
            conflicts = _union(conflicts, [{"field": "extra." + key, "values": [merged.extra[key], value]}])
        else:
            merged.extra[key] = deepcopy(value)
    # Original member snapshots make every conflicting value reconstructible.
    members = []
    for record in (left, right):
        originals = record.extra.get("merged_records") or [asdict(record)]
        for original in originals:
            payload = deepcopy(original)
            payload["extra"].pop("merged_records", None)
            if payload not in members:
                members.append(payload)
    merged.extra["merged_records"] = members
    if conflicts:
        merged.extra["merge_conflicts"] = conflicts
    return merged


def deduplicate(publications: list[Publication]) -> tuple[list[Publication], list[dict]]:
    """Complete-link groups prevent a missing DOI bridging conflicting DOI records.

    Returns merged records and audit decisions for examined candidate groups.
    O(n²) intentionally targets bounded academic/demo corpora.
    """
    groups: list[tuple[Publication, list[Publication]]] = []
    decisions = []
    for publication in publications:
        eligible = []
        for index, (representative, members) in enumerate(groups):
            results = [match_publications(member, publication) for member in members]
            compatible = all(result["merge"] for result in results)
            if compatible:
                eligible.append(index)
            same_title = bool(normalize_title(publication.title)) and any(
                normalize_title(member.title) == normalize_title(publication.title) for member in members
            )
            if compatible or same_title or any(result["confidence"] >= 0.6 for result in results):
                decisions.append(
                    {
                        "left_id": representative.id,
                        "right_id": publication.id,
                        "merge": compatible,
                        "confidence": min(result["confidence"] for result in results),
                        "reasons": sorted({reason for result in results for reason in result["reasons"]}),
                    }
                )
        if len(eligible) == 1:
            index = eligible[0]
            representative, members = groups[index]
            groups[index] = (_merge(representative, publication), [*members, deepcopy(publication)])
        else:
            if len(eligible) > 1:
                decisions.append(
                    {
                        "left_id": "",
                        "right_id": publication.id,
                        "merge": False,
                        "confidence": 0.0,
                        "reasons": ["ambiguous membership in multiple groups; kept separate"],
                    }
                )
                for decision in decisions:
                    if decision["right_id"] == publication.id:
                        decision["merge"] = False
            groups.append((deepcopy(publication), [deepcopy(publication)]))
    return [representative for representative, _ in groups], decisions
