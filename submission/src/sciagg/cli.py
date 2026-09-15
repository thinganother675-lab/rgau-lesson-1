import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from .exports import export
from .http import Http
from .normalization import h_index, normalize_issn
from .providers.base import ProviderError, attempt
from .providers.crossref import Crossref
from .providers.imports import import_journals, import_publications
from .providers.openalex import OpenAlex
from .providers.orcid import Orcid
from .providers.scopus import Scopus
from .providers.whitelist import Whitelist
from .services import discover, profile, publication
from .storage import Store


def parser():
    root = argparse.ArgumentParser(description="Агрегатор научной библиографии с происхождением данных")
    root.add_argument("--db", default="data/sciagg.sqlite", help="SQLite path")
    root.add_argument("--cache", default="data/cache")
    root.add_argument("--offline", action="store_true", help="Только ранее сохранённые ответы")
    commands = root.add_subparsers(dest="command", required=True)
    for name in (
        "search-author",
        "author-profile",
        "publication",
        "journal",
        "sources",
        "h-index",
        "import-vak",
        "import-whitelist",
        "import-ranking",
        "import-publications",
        "demo",
    ):
        child = commands.add_parser(name)
        child.add_argument("--json", action="store_true")
        child.add_argument("--export", help=".json, .csv, .xlsx")
        if name in ("search-author", "author-profile"):
            child.add_argument("query", help="ФИО для поиска; OpenAlex ID/ORCID/Scopus ID для профиля")
            child.add_argument("--limit", type=int, default=5 if name == "search-author" else 10)
            if name == "author-profile":
                child.add_argument("--source", choices=("openalex", "orcid", "scopus"), default="openalex")
        if name == "publication":
            child.add_argument("doi")
        if name == "journal":
            child.add_argument("--issn", required=True)
        if name == "h-index":
            child.add_argument("counts", type=int, nargs="*")
        if name.startswith("import-"):
            child.add_argument("path")
            child.add_argument("--source-url", required=True)
            if name == "import-publications":
                child.add_argument("--source", required=True, choices=("elibrary", "scopus", "institution"))
            else:
                child.add_argument("--snapshot-date", required=True, help="YYYY-MM-DD дата версии списка")
    return root


def journal_lookup(store, provider, issn):
    issn = normalize_issn(issn)
    if not issn:
        raise ValueError("Invalid ISSN format/checksum")
    remote, status = attempt(provider.name, lambda: provider.journal(issn))
    if remote:
        _, saved_status = attempt("journal_storage", lambda: store.save_journal(remote))
    else:
        saved_status = None
    saved = store.get_journal(issn)
    return {
        "journal": saved,
        "providers": [s for s in (status, saved_status) if s],
        "note": "Отсутствие локальной строки не доказывает отсутствие в ВАК; сверяйте версию и специальность",
    }


def sources():
    return {
        "sources": [
            {
                "source": "crossref",
                "mode": "live API",
                "credentials": "none; optional CROSSREF_MAILTO",
                "status": "configured",
                "role": "DOI metadata and ORCID-filtered works; no native author profiles",
            },
            {
                "source": "openalex",
                "mode": "live API",
                "credentials": "optional OPENALEX_API_KEY",
                "status": "configured",
                "role": "candidate profiles, selected ID works, citations",
            },
            {
                "source": "orcid",
                "mode": "live public record",
                "credentials": "optional ORCID_ACCESS_TOKEN",
                "status": "configured",
                "role": "public record by ORCID; not citation metrics",
            },
            {
                "source": "whitelist",
                "mode": "live API + official JSON/normalized CSV/XLSX",
                "credentials": "none",
                "status": "configured",
                "role": "ISSN lookup, explicit classification years",
            },
            {
                "source": "vak",
                "mode": "official PDF + normalized CSV/XLSX/JSON import",
                "credentials": "none",
                "status": "import",
                "role": "dated snapshot; specialty/date wording retained",
            },
            {
                "source": "scopus",
                "mode": "optional live API + normalized import",
                "credentials": "SCOPUS_API_KEY; institutional entitlement may be required",
                "status": "configured_unverified_entitlement"
                if os.getenv("SCOPUS_API_KEY")
                else "missing_credentials",
            },
            {
                "source": "elibrary",
                "mode": "normalized authorized export import",
                "credentials": "agreement-dependent",
                "status": "import_only",
                "reason": "public usable API contract not verified; website not scraped",
            },
            {
                "source": "ranking",
                "mode": "normalized CSV/XLSX/JSON import",
                "status": "import_only",
                "role": "quartiles require source system, category, metric year; no invented rankings",
            },
        ]
    }


def run(args):
    if args.command == "sources":
        return sources()
    if args.command == "h-index":
        return {
            "citation_counts": args.counts,
            "h_index": h_index(args.counts),
            "note": "Для [10,8,5,4,3,1] h=4; пятая статья имеет только 3 цитирования",
        }
    if args.command == "demo":
        path = Path("examples/demo_profile.json")
        if not path.exists():
            raise ValueError("Run from project root; bundled examples/demo_profile.json required")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["demonstration_mode"] = "сохранённый реальный ответ, не свежий сетевой запрос"
        return data
    if hasattr(args, "limit") and not 1 <= args.limit <= 100:
        raise ValueError("--limit must be 1..100 for responsible demo usage")
    http = Http(args.cache, offline=args.offline)
    try:
        crossref, openalex, scopus = Crossref(http), OpenAlex(http), Scopus(http)
        whitelist = Whitelist(http)
        with Store(args.db) as store:
            if args.command == "search-author":
                return discover([openalex, crossref], args.query, args.limit)
            if args.command == "publication":
                works, info = publication([crossref, openalex, scopus], args.doi)
                store.save_publications(works)
                return {
                    "publications": [asdict(w) for w in works],
                    **info,
                    "journals": [
                        journal_lookup(store, whitelist, i)
                        for i in sorted({i for w in works for i in w.issns})
                    ],
                }
            if args.command == "journal":
                return journal_lookup(store, whitelist, args.issn)
            if args.command == "author-profile":
                primary = {"openalex": openalex, "orcid": Orcid(http), "scopus": scopus}[args.source]
                # Never silently choose the first namesake. The caller selects a persistent ID.
                if args.source == "openalex" and not (
                    args.query.rsplit("/", 1)[-1].startswith("A")
                    and args.query.rsplit("/", 1)[-1][1:].isdigit()
                ):
                    data = discover([openalex, crossref], args.query, args.limit)
                    data["requires_selection"] = True
                    return data
                author, status = attempt(primary.name, lambda: primary.author(args.query))
                if author is None:
                    return {"providers": [status], "publications": [], "error": "author_unavailable"}
                store.save_author(author)
                work_provider = crossref if args.source == "orcid" else primary
                enrichers = [crossref, openalex]
                if os.getenv("SCOPUS_API_KEY"):
                    enrichers.append(scopus)
                data, works = profile(work_provider, author, enrichers, args.limit)
                data["providers"].append(status)
                if not os.getenv("SCOPUS_API_KEY"):
                    data["providers"].append({"source": "scopus", "status": "missing_credentials"})
                store.save_publications(works)
                data["journals"] = [
                    journal_lookup(store, whitelist, i) for i in sorted({i for w in works for i in w.issns})
                ]
                return data
            if args.command == "import-publications":
                records = import_publications(args.path, source=args.source, source_url=args.source_url)
                from .resolution import deduplicate

                works, review = deduplicate(records)
                store.save_publications(works)
                return {
                    "imported": len(records),
                    "publications": [asdict(w) for w in works],
                    "reviews": review,
                }
            if args.command.startswith("import-"):
                source = args.command.removeprefix("import-")
                if source == "vak" and Path(args.path).suffix.lower() == ".pdf":
                    from .providers.vak_pdf import parse_vak_pdf

                    journals = parse_vak_pdf(
                        args.path, source_url=args.source_url, effective_date=args.snapshot_date
                    )
                    info = {
                        "source": "vak",
                        "accepted": len(journals),
                        "rejected": getattr(journals, "rejected", []),
                        "warnings": getattr(journals, "warnings", []),
                    }
                else:
                    journals, info = import_journals(
                        args.path, source, source_url=args.source_url, snapshot_date=args.snapshot_date
                    )
                storage_audit = store.save_journals(journals)
                info.update(stored=storage_audit["stored"], storage_rejected=storage_audit["rejected"])
                return info
        raise ValueError("Unknown command")
    finally:
        http.close()


def human(data):
    if "candidates" in data:
        lines = [data.get("note", "Кандидаты")]
        for candidate in data["candidates"]:
            lines.append(
                f"{candidate['id']} | {candidate['name']} | {', '.join(candidate['affiliations'][:2])}"
            )
        if data.get("requires_selection"):
            lines.append("Повторите author-profile с OpenAlex ID выбранного кандидата.")
    elif "publications" in data:
        author = data.get("author", {})
        lines = [f"Автор: {author['name']} ({author['id']})"] if author else []
        lines.append(f"Получено публикаций: {len(data['publications'])}")
        if data.get("coverage"):
            lines.append("Покрытие: " + json.dumps(data["coverage"], ensure_ascii=False))
        for work in data["publications"]:
            lines.append(f"{work.get('year') or '?'} | {work['title']} | DOI {work.get('doi') or '—'}")
            lines.append(
                "  "
                + "; ".join(
                    f"{m['source']}: {m['value']} цит. ({m['retrieved_at'][:10]})"
                    for m in work.get("citations", [])
                )
            )
        for metric in data.get("calculated_metrics", []):
            lines.append(
                f"h по выборке {metric['source']}: {metric['value']} ({metric['publications_with_citations']} работ)"
            )
    else:
        return json.dumps(data, ensure_ascii=False, indent=2)
    for status in data.get("providers", []):
        lines.append(f"Источник {status['source']}: {status['status']} {status.get('reason', '')}")
    return "\n".join(lines)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        data = run(args)
        if args.export:
            export(data, args.export)
        print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else human(data))
        if data.get("error") or data.get("requires_selection"):
            return 2
        if args.command in ("publication", "search-author") and not data.get(
            "publications", data.get("candidates")
        ):
            return 2
        if args.command == "journal" and data.get("journal") is None:
            return 2
        if args.command.startswith("import-") and (data.get("rejected") or data.get("storage_rejected")):
            return 2
        return 0
    except (ValueError, ProviderError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
