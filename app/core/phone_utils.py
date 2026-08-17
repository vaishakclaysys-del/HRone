"""Normalize phone strings so submission lookup tolerates spaces, +91, dashes, etc."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Candidate


def canonical_phone_for_match(phone: str) -> str:
    """Digits only; strip leading zeros; if longer than 10 digits, use last 10 (e.g. country code)."""
    d = "".join(c for c in (phone or "").strip() if c.isdigit())
    if not d:
        return ""
    d = d.lstrip("0")
    if not d:
        return ""
    if len(d) > 10:
        return d[-10:]
    return d


def find_candidate_by_phone(db: Session, phone: str) -> Candidate | None:
    """Match stored phone to user input with exact (stripped) then canonical digit match."""
    raw = (phone or "").strip()
    if not raw:
        return None
    found = db.scalar(select(Candidate).where(Candidate.phone == raw))
    if found:
        return found
    key = canonical_phone_for_match(raw)
    if not key:
        return None
    for cand in db.scalars(select(Candidate)):
        if canonical_phone_for_match(cand.phone) == key:
            return cand
    return None
