import os

from ..models import Author, Provenance
from ..normalization import normalize_orcid


class Orcid:
    name = "orcid"

    def __init__(self, http):
        self.http = http

    def author(self, orcid):
        orcid = normalize_orcid(orcid)
        if orcid is None:
            raise ValueError("Invalid ORCID checksum/format")
        url = f"https://pub.orcid.org/v3.0/{orcid}/record"
        headers = {"Accept": "application/vnd.orcid+json"}
        if token := os.getenv("ORCID_ACCESS_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
        data = self.http.get(self.name, url, headers=headers)
        person = data.get("person") or {}
        name = person.get("name") or {}
        full = " ".join(
            (name.get(key) or {}).get("value", "") for key in ("given-names", "family-name")
        ).strip()
        full = (name.get("credit-name") or {}).get("value") or full or orcid
        variants = [x["content"] for x in (person.get("other-names") or {}).get("other-name", [])]
        activities = data.get("activities-summary") or {}
        affiliations = []
        for group in (activities.get("employments") or {}).get("affiliation-group", []):
            for summary in group.get("summaries", []):
                organization = (summary.get("employment-summary") or {}).get("organization") or {}
                if organization.get("name"):
                    affiliations.append(organization["name"])
        dois = set()
        for group in (activities.get("works") or {}).get("group", []):
            for external in (group.get("external-ids") or {}).get("external-id", []):
                if (
                    external.get("external-id-type") == "doi"
                    and external.get("external-id-relationship") == "self"
                ):
                    from ..normalization import normalize_doi

                    doi = normalize_doi(external.get("external-id-value"))
                    if doi:
                        dois.add(doi)
        return Author(
            id=f"orcid:{orcid}",
            name=full,
            identifiers={"orcid": orcid},
            variants=variants,
            affiliations=list(dict.fromkeys(affiliations)),
            dois=sorted(dois),
            provenance=[Provenance(self.name, orcid, url, self.http.last_retrieved_at, data)],
        )
