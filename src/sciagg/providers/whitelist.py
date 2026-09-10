import re

from ..models import Journal, Provenance
from ..normalization import normalize_issn
from .base import ProviderError


class Whitelist:
    name = "whitelist"
    base = "https://journalrank.rcsi.science"

    def __init__(self, http):
        self.http = http

    @staticmethod
    def parse(data, *, url="", retrieved_at=None):
        identifiers = data.get("issn", data.get("issns", []))
        if not isinstance(identifiers, list) or not identifiers:
            raise ValueError("Whitelist response missing ISSNs")
        issns = [normalize_issn(x) for x in identifiers]
        if any(value is None for value in issns):
            raise ValueError("Whitelist response contains invalid ISSN checksum/format")
        titles = data.get("title", [])
        if isinstance(titles, str):
            titles = [titles]
        if (
            not isinstance(titles, list)
            or not titles
            or not isinstance(titles[0], str)
            or not titles[0].strip()
        ):
            raise ValueError("Whitelist response missing title")
        prov = Provenance("whitelist", str(data.get("id", "")), url, raw=data)
        if retrieved_at:
            prov.retrieved_at = retrieved_at
        classifications = []
        # Preserve each supplied year, including null; never borrow 2025 for 2026.
        for key, value in data.items():
            if re.fullmatch(r"level_\d{4}", key):
                if value is not None and (isinstance(value, bool) or value not in (1, 2, 3, 4)):
                    raise ValueError("Unexpected whitelist level")
                classifications.append(
                    {
                        "source": "whitelist",
                        "system": "Белый список",
                        "kind": "level",
                        "year": int(key[6:]),
                        "value": value,
                        "status": "observed" if value is not None else "not_assigned",
                        "retrieved_at": prov.retrieved_at,
                        "source_url": url,
                        "date_accepted": data.get("dateAccepted", data.get("date_accepted")),
                        "date_discontinued": data.get("dateDiscontinued", data.get("date_discontinued")),
                        "state": data.get("state"),
                        "notice": data.get("notice"),
                    }
                )
        return Journal(issns=issns, title=titles[0], classifications=classifications, provenance=[prov])

    def journal(self, issn):
        issn = normalize_issn(issn)
        if issn is None:
            raise ValueError("Invalid ISSN checksum/format")
        url = f"{self.base}/api/record-sources/{issn}/level"
        try:
            data = self.http.get(self.name, url)
        except ProviderError as exc:
            if exc.status == 400:
                raise ProviderError(self.name, "ISSN не найден в API; это не статус ВАК", 400) from None
            raise
        return self.parse(data, url=url, retrieved_at=self.http.last_retrieved_at)
