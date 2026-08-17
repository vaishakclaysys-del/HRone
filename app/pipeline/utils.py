from sqlalchemy.orm import Session
from datetime import datetime, UTC
from app.core.models import (
    Candidate,
    CandidateProgress,
)
from datetime import datetime


def update_candidate_status(
    db: Session,
    candidate: Candidate,
    status: str,
    stage: int,
) -> None:

    candidate.status = status
    candidate.stage = stage

    db.flush()


def log_progress(
    db: Session,
    candidate_id: int,
    stage: int,
    event: str,
    notes: str,
    actor_id: int | None,
) -> None:

    db.add(
        CandidateProgress(
            candidate_id=candidate_id,
            stage=stage,
            event=event,
            details=notes,
            acted_by=actor_id,
            created_at=datetime.now(UTC).replace(microsecond=0),        )
    )

    db.flush()