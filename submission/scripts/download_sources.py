"""Download public official snapshots without replacing existing files.

VAK URL is the researched August 2026 snapshot, not a promise of the latest
future edition. Whitelist URL returns the server's state at acquisition time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

VAK_URL = (
    "https://vak.gisnauka.ru/s3-files/01cc80c69fae4988a0246a8f5e2774e7:fisgna/public/"
    "media/uploaded/news_files/2094e02c-d851-48cd-9d57-fe7ebd34a039/"
    "ec5260d0-14d5-49b8-9f76-a5037e0e1c80.pdf"
)
SOURCES = {
    "whitelist": ("https://journalrank.rcsi.science/ru/record-sources/download/?dataType=Json", ".json"),
    "whitelist-schema": (
        "https://journalrank.rcsi.science/ru/record-sources/download-description/?dataType=Json",
        ".json",
    ),
    "vak": (VAK_URL, ".pdf"),
}


def download_one(source: str, output: Path, timeout: float = 60) -> dict:
    url, extension = SOURCES[source]
    started = time.monotonic()
    stamp = datetime.now(timezone.utc)
    output.mkdir(parents=True, exist_ok=True)
    name = f"{source}_{stamp.strftime('%Y-%m-%dT%H%M%S%fZ')}{extension}"
    target = output / name
    request = urllib.request.Request(url, headers={"User-Agent": "sciagg-ru/0.1 academic-metadata-research"})
    # Python's default HTTPS certificate verification remains enabled.
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if not response.url.startswith("https://"):
            raise ValueError("Refusing a redirect to a non-HTTPS resource")
        chunks, size = [], 0
        while block := response.read(1024 * 1024):
            size += len(block)
            if size > 100 * 1024 * 1024:
                raise ValueError("Source exceeds the 100 MiB download cap")
            if time.monotonic() - started > timeout:
                raise TimeoutError("Total download deadline exceeded")
            chunks.append(block)
        body = b"".join(chunks)
        if extension == ".pdf" and not body.startswith(b"%PDF-"):
            raise ValueError("Expected a PDF; refusing to save an error/login page")
        if extension == ".json":
            json.loads(body.decode("utf-8-sig"))
        meta = {
            "source": source,
            "source_url": url,
            "final_url": response.url,
            "retrieved_at": stamp.isoformat(),
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
            "content_type": response.headers.get("Content-Type"),
        }
        if source == "vak":
            meta["list_date"] = "2026-08-14"
            meta["note"] = "Static researched official snapshot; verify the VAK site for newer versions"
    # Exclusive creation means a previous source is never overwritten.
    with target.open("xb") as stream:
        stream.write(body)
    with Path(str(target) + ".meta.json").open("x", encoding="utf-8") as stream:
        json.dump(meta, stream, ensure_ascii=False, indent=2)
    return {"path": str(target.resolve()), **meta}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Directory for new timestamped files")
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    parser.add_argument(
        "--timeout", type=float, default=60, help="Socket timeout and total deadline, 1–120 seconds"
    )
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 120:
        parser.error("--timeout must be between 1 and 120 seconds")
    results, failures = [], []
    for source in SOURCES if args.source == "all" else [args.source]:
        try:
            results.append(download_one(source, args.output, args.timeout))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            failures.append({"source": source, "error": str(exc)})
    print(json.dumps({"downloaded": results, "failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
