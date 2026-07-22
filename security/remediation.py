# security/remediation.py
"""Turn a BLOCK into a next step instead of a dead end.

When the guardrail stops an agent because a dataset is deprecated, the useful
answer is rarely "no" — it is "not that one, use this one". This module looks
for a likely replacement and always reports *why* it thinks so, so neither the
agent nor a human is asked to trust an unexplained redirect.

Evidence is ranked, strongest first:

  1. deprecation_note  - a human wrote "use X instead" in DataHub. Highest
                         confidence because it is an intentional statement.
  2. lineage           - a downstream dataset sharing the deprecated table's
                         name stem, which is the shape a v1 -> v2 backfill
                         migration leaves behind.
  3. naming_convention - a catalog sibling with the same stem and a higher
                         version suffix. Weakest: a coincidence of naming.

Deliberately NOT done here: schema compatibility. We have no column-level
metadata in DatasetContext, so claiming the successor is drop-in would be a
guess dressed as a fact. Suggestions are advisory and never auto-applied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# "use X instead", "replaced by X", "migrate to X", "superseded by X", "see X"
_NOTE_PATTERNS = [
    re.compile(r"\buse\s+([\w.\-]+)\s+instead\b", re.I),
    re.compile(r"\breplaced\s+by\s+([\w.\-]+)", re.I),
    re.compile(r"\bsuperseded\s+by\s+([\w.\-]+)", re.I),
    re.compile(r"\bmigrat\w*\s+to\s+([\w.\-]+)", re.I),
]

_VERSION_SUFFIX = re.compile(r"_v(\d+)$", re.I)
_LEGACY_AFFIX = re.compile(r"(^legacy[_\-]|[_\-]legacy$|[_\-]old$|^old[_\-])", re.I)


@dataclass
class Suggestion:
    dataset: str                       # urn when we have one, else a bare name
    basis: str                         # deprecation_note | lineage | naming_convention
    confidence: str                    # high | medium | low
    evidence: str = ""
    caveats: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {"suggested_dataset": self.dataset, "basis": self.basis,
                "confidence": self.confidence, "evidence": self.evidence,
                "caveats": self.caveats}


def _name_of(urn_or_name: str) -> str:
    """Pull the dataset name out of a URN; pass plain names through."""
    m = re.search(r"urn:li:dataset:\([^,]+,([^,]+),[^)]*\)", urn_or_name or "")
    return (m.group(1) if m else (urn_or_name or "")).strip()


def _stem(name: str) -> str:
    """Strip version and legacy affixes so v1/v2/legacy_x share a stem."""
    name = _name_of(name).lower()
    name = _VERSION_SUFFIX.sub("", name)
    name = _LEGACY_AFFIX.sub("", name)
    return name.strip("_-")


def _version(name: str) -> int:
    m = _VERSION_SUFFIX.search(_name_of(name))
    return int(m.group(1)) if m else 0


_UNVERIFIED = "successor is unverified: schema compatibility was not checked"


def suggest_successor(context, catalog: Optional[List[str]] = None
                      ) -> Optional[Suggestion]:
    """Best replacement for a deprecated dataset, or None if we cannot tell.

    context: DatasetContext (or anything exposing name/deprecation_note/downstream)
    catalog: optional list of known dataset URNs or names, for the weakest path.
    """
    if context is None:
        return None

    note = (getattr(context, "deprecation_note", "") or "").strip()
    for pattern in _NOTE_PATTERNS:
        m = pattern.search(note)
        if m:
            return Suggestion(m.group(1), "deprecation_note", "high",
                              evidence=f"deprecation note: {note}",
                              caveats=[_UNVERIFIED])

    own_stem = _stem(getattr(context, "name", ""))
    own_version = _version(getattr(context, "name", ""))

    # 2. downstream lineage entry that looks like the same table, newer
    candidates = [d for d in (getattr(context, "downstream", None) or [])
                  if _stem(d) == own_stem and _version(d) > own_version]
    if candidates:
        best = max(candidates, key=_version)
        return Suggestion(
            best, "lineage", "medium",
            evidence=(f"downstream of {_name_of(getattr(context, 'name', ''))} "
                      f"and shares its name stem '{own_stem}'"),
            caveats=[_UNVERIFIED])

    # 3. catalog sibling with the same stem and a higher version
    siblings = [c for c in (catalog or [])
                if _stem(c) == own_stem and _version(c) > own_version
                and _name_of(c) != _name_of(getattr(context, "name", ""))]
    if siblings:
        best = max(siblings, key=_version)
        return Suggestion(
            best, "naming_convention", "low",
            evidence=f"catalog entry sharing name stem '{own_stem}'",
            caveats=[_UNVERIFIED,
                     "matched on naming alone; no lineage or owner statement "
                     "links it to the deprecated dataset"])

    return None
