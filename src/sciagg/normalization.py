"""Conservative normalization; invalid identifiers are represented by None."""

import re
import unicodedata
from collections.abc import Iterable
from urllib.parse import unquote, urlsplit


def normalize_doi(value: str | None) -> str | None:
    """Accept a DOI or doi.org URL, retaining legal suffix punctuation.

    This is syntactic validation, not a DOI registration lookup. URL query and
    fragment components are excluded; encoded characters in the path are decoded.
    A final period is not blindly removed because it can belong to a DOI suffix.
    """
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFC", value).strip()
    if re.match(r"https?://", text, flags=re.I):
        try:
            parts = urlsplit(text)
        except ValueError:
            return None
        if parts.hostname not in {"doi.org", "dx.doi.org", "www.doi.org"}:
            return None
        text = unquote(parts.path.lstrip("/"))
    elif text.lower().startswith(("doi.org/", "dx.doi.org/")):
        text = unquote(text.split("/", 1)[1])
    elif text.lower().startswith("doi:"):
        text = text[4:].strip()
    text = text.lower()
    if not re.fullmatch(r"10\.[0-9]{4,9}/\S+", text):
        return None
    if any(unicodedata.category(char).startswith("C") for char in text):
        return None
    return text


def normalize_issn(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    token = re.sub(r"[\s-]", "", value).upper()
    if not re.fullmatch(r"[0-9]{7}[0-9X]", token):
        return None
    digits = [int(c) for c in token[:7]] + [10 if token[7] == "X" else int(token[7])]
    if sum(digit * weight for digit, weight in zip(digits, range(8, 0, -1), strict=True)) % 11:
        return None
    return token[:4] + "-" + token[4:]


def normalize_orcid(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    token = re.sub(r"^https?://orcid\.org/", "", value.strip(), flags=re.I)
    token = token.replace("-", "").upper()
    if not re.fullmatch(r"[0-9]{15}[0-9X]", token):
        return None
    total = 0
    for char in token[:15]:
        total = (total + int(char)) * 2
    result = (12 - total % 11) % 11
    if token[-1] != ("X" if result == 10 else str(result)):
        return None
    return "-".join(token[i : i + 4] for i in range(0, 16, 4))


def normalize_name(value: str | None) -> str:
    """Normalize Unicode/case/punctuation without reordering or transliteration."""
    text = unicodedata.normalize("NFKC", value or "").casefold()
    return " ".join(
        "".join(c if c.isalnum() or unicodedata.category(c).startswith("M") else " " for c in text).split()
    )


def normalize_title(value: str | None) -> str:
    return normalize_name(value)


def transliterate_name(value: str | None) -> str:
    """Explicit, lossy Russian transliteration for candidate generation only.

    It is not identity evidence: spelling conventions vary and names collide.
    """
    table = dict(
        zip(
            "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
            (
                "a",
                "b",
                "v",
                "g",
                "d",
                "e",
                "e",
                "zh",
                "z",
                "i",
                "i",
                "k",
                "l",
                "m",
                "n",
                "o",
                "p",
                "r",
                "s",
                "t",
                "u",
                "f",
                "kh",
                "ts",
                "ch",
                "sh",
                "shch",
                "",
                "y",
                "",
                "e",
                "yu",
                "ya",
            ),
            strict=True,
        )
    )
    return normalize_name("".join(table.get(c, c) for c in (value or "").casefold()))


def h_index(citations: Iterable[int | float]) -> int:
    """Hirsch h for one defined corpus; never combine database counters.

    Missing, negative, fractional, boolean or nonfinite citation counts are errors.
    """
    values = list(citations)
    for count in values:
        if isinstance(count, bool) or not isinstance(count, (int, float)) or count < 0:
            raise ValueError("citation counts must be nonnegative integers")
        try:
            valid = int(count) == count
        except (ValueError, OverflowError):
            valid = False
        if not valid:
            raise ValueError("citation counts must be nonnegative integers")
    return max(
        (rank for rank, count in enumerate(sorted(values, reverse=True), 1) if count >= rank), default=0
    )
