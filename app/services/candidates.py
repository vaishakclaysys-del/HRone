from __future__ import annotations
from datetime import timedelta, timezone, datetime
from math import ceil
import logging
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.models import Candidate, CandidateScreening, CandidateDecision, User
from app.pipeline.orchestrator import FLOWS
from app.pipeline.utils import log_progress
from fastapi import HTTPException
import app.pipeline as pipeline
from app.core.config import PIPELINES, MIN_REVIEWS_REQUIRED
logger = logging.getLogger(__name__)

def search_candidates(
    db: Session,
    q: str = "",
    fit: str = "",
    status: str = "",
    flow: str = "",
    page: int = 1,
    per_page: int = 10,
) -> tuple[list[Candidate], int, bool]:
    """
    Search and paginate candidates with optional filters.

    Returns (candidates, total_pages, has_next).
    """
    query = select(Candidate).order_by(Candidate.created_at.desc())

    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                Candidate.name.like(pattern),
                Candidate.email.like(pattern),
                Candidate.phone.like(pattern),
            )
        )

    if fit:
        query = query.join(CandidateScreening).where(
            CandidateScreening.fit_tag == fit
        )

    if status:
        # Special compound filters handled here:
        if status == "interview_completed":
            # anyone who completed interviews (passed or failed)
            query = query.where(Candidate.status.in_(["interview_passed", "interview_failed"]))
        elif status == "interview_passed":
            # include candidates who've passed interview and those moved to offer
            query = query.where(Candidate.status.in_(["interview_passed", "offer"]))
        else:
            query = query.where(Candidate.status == status)

    if flow:
        query = query.where(Candidate.flow == flow)

    total = len(list(db.scalars(query)))
    total_pages = ceil(total / per_page) if per_page else 0

    candidates = list(
        db.scalars(
            query.offset((page - 1) * per_page).limit(per_page)
        )
    )

    has_next = total > page * per_page

    return candidates, total_pages, has_next


def compute_acceptance_deadline(candidate: Candidate):
    """
    Business rule: once a candidate's status is set to 'accepted',
    they have 7 days (from their last update) to respond.

    Returns None when the rule doesn't apply.
    """
    if candidate.status == "accepted" and candidate.updated_at:
        return candidate.updated_at + timedelta(days=7)

    return None

def process_hr_decision(
    db: Session,
    candidate_id: int,
    decision: str,
    notes: str,
    flow: str | None,
    user: User,
) -> Candidate:

    candidate = db.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        )

    candidate.stage = 2
    candidate.status = (
        "accepted"
        if decision == "accept"
        else "rejected"
    )

    existing = db.scalar(
        select(CandidateDecision).where(
            CandidateDecision.candidate_id == candidate.id
        )
    )

    if existing:
        existing.decision = decision
        existing.notes = notes
        existing.acted_by = user.id
    else:
        db.add(
            CandidateDecision(
                candidate_id=candidate.id,
                decision=decision,
                notes=notes,
                acted_by=user.id,
            )
        )

    if decision == "accept":
        candidate.stage = 3

        if flow and flow in FLOWS:
            candidate.flow = flow

    log_progress(
        db,
        candidate.id,
        candidate.stage,
        f"hr_{decision}",
        notes or "Decision updated",
        user.id,
    )

    if (
        decision == "accept"
        and flow
        and flow in FLOWS
    ):
        pipeline.on_candidate_accepted(
            db,
            candidate,
        )

    db.commit()

    return candidate


# ---------------------------------------------------------
# Talent Pipeline (kanban board) data
# ---------------------------------------------------------

STATUS_TO_COLUMN = {
    "accepted": "Telephonic (HR)",
    "submitted": "Hackathon Submitted",
    "passed_stage4": "Hackathon Submitted",
    "failed_stage4": "Hackathon Submitted",
    "interview_scheduled": "Interview Scheduled",
    "interview_passed": "Interview Completed",
    "interview_failed": "Interview Completed",
    "offer": "Offer",
}
FLOW_META = {
    "ai_hackathon_flow": {"label": "AI Hackathon", "class": "purple"},
    "ai_interview_flow": {"label": "AI Interview", "class": "blue"},
}
DEFAULT_FLOW_META = {"label": "Standard", "class": "green"}


def get_candidates_by_department(db: Session, department: str):
    return db.scalars(
        select(Candidate)
        .where(Candidate.department == department)
        .order_by(Candidate.updated_at.desc())
    ).all()


def _format_updated_at(updated_at: datetime | None) -> str:
    """Relative, human-friendly timestamp for the card footer."""
    if not updated_at:
        return "—"

    now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    delta = now - updated_at
    seconds = delta.total_seconds()

    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes}m ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours}h ago"
    if seconds < 86400 * 7:
        days = int(seconds // 86400)
        return f"{days}d ago"
    return updated_at.strftime("%b %-d, %Y")


def _initials_from_full_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _reviewer_initials(db: Session, candidate: Candidate) -> list[dict]:
    """
    Real reviewer/interviewer initials for the avatar stack, pulled from
    SubmissionReview.reviewer_id (Hackathon Submitted stage) and
    InterviewScore.interviewer_id (Interview stages) — resolved against
    User since neither table has a relationship() back to User.

    Returns a list of {"initials": str, "full_name": str} so the template
    can show initials with a real name on hover, instead of raw initials.
    """
    reviewer_ids: set[int] = set()

    submission = getattr(candidate, "submission", None)
    if submission:
        reviewer_ids.update(r.reviewer_id for r in submission.reviews)

    for interview in (candidate.interviews or []):
        reviewer_ids.update(s.interviewer_id for s in interview.scores)

    if not reviewer_ids:
        return []

    users = db.scalars(
        select(User).where(User.id.in_(reviewer_ids))
    ).all()

    return [
        {"initials": _initials_from_full_name(u.full_name), "full_name": u.full_name}
        for u in users
    ]
def _review_count(candidate) -> int:
    """Reviews submitted so far, regardless of whether that meets MIN_REVIEWS."""
    submission = getattr(candidate, "submission", None)
    if not submission:
        return 0
    return len(submission.reviews)
 

def _assessment_score(candidate) -> float | None:
    """
    Average weighted_total across this candidate's submission reviews.
    Returns None if there's no submission or no reviews yet.
    """
    submission = getattr(candidate, "submission", None)
    if not submission or not submission.reviews:
        return None

    totals = [r.weighted_total for r in submission.reviews]
    return round(sum(totals) / len(totals), 1)


def _interview_score(candidate) -> float | None:
    """
    Average InterviewScore.score across all interviewer scores for this
    candidate's interview(s). Returns None if not yet scored.
    """
    all_scores = [
        s.score
        for interview in (candidate.interviews or [])
        for s in interview.scores
    ]
    if not all_scores:
        return None
    return round(sum(all_scores) / len(all_scores), 1)


def get_pipeline_data(db: Session, department: str):
    candidates = get_candidates_by_department(db, department)

    # dict keyed by column title -> stable lookup regardless of PIPELINES order
    columns = {
        title: {"title": title, "candidates": []}
        for title in PIPELINES[department]
    }

    for candidate in candidates:
        flow_meta = FLOW_META.get(candidate.flow, DEFAULT_FLOW_META)

        card = {
            "id": candidate.id,
            "name": candidate.name,
            "role": candidate.department,
            "status": candidate.status,
            "flow": candidate.flow,
            "stage": candidate.stage,
            "assessment_score": _assessment_score(candidate),
            "review_count": _review_count(candidate),
            "interview_score": _interview_score(candidate),
            "flow_label": flow_meta["label"],
            "flow_class": flow_meta["class"],
            "updated_at_display": _format_updated_at(candidate.updated_at),
            "reviewers": _reviewer_initials(db, candidate),
        }

        column_title = STATUS_TO_COLUMN.get(candidate.status)
        if column_title and column_title in columns:
            columns[column_title]["candidates"].append(card)
        else:
            # candidate no longer silently disappears from the board
            logger.warning(
                "talent_pipeline: candidate %s has unmapped status %r for department %r",
                candidate.id,
                candidate.status,
                department,
            )

    # preserve the display order defined in PIPELINES[department]
    return [columns[title] for title in PIPELINES[department]]


# ---------------------------------------------------------
# Progress-card helpers (shared by the dashboard's featured
# candidates and the full department-pipeline list page)
# ---------------------------------------------------------

# Purely for display -- never used for branching logic. If you relabel
# these, nothing else in this file will break, because stage_colors()
# and current_score() below both switch on candidate.status directly,
# not on this text.
STAGE_LABELS = {
    "new": "Telephonic",
    "parsed": "Telephonic",
    "accepted": "Telephonic (HR)",
    "submitted": "Hackathon Submitted",
    "passed_stage4": "Hackathon Passed",
    "failed_stage4": "Hackathon Failed",
    "interview_scheduled": "Interview Scheduled",
    "interview_passed": "Interview Passed",
    "offer": "Offer",
    "interview_failed": "Interview Failed",
    "rejected": "Telephonic",
}

# `offer` is now a real backend status and maps to the Offer column.
STATUS_BADGE = {
    "new": ("pending", "Pending"),
    "parsed": ("pending", "Pending"),
    "accepted": ("active", "Active"),
    "submitted": ("review", "Review"),
    "passed_stage4": ("active", "Active"),
    "failed_stage4": ("rejected", "Rejected"),
    "interview_scheduled": ("active", "Active"),
    "interview_passed": ("offer", "Offer"),   # stage completed, next transition is actual Offer
    "offer": ("offer", "Offer"),
    "interview_failed": ("rejected", "Rejected"),
    "rejected": ("rejected", "Rejected"),
}


def stage_label(status: str) -> str:
    return STAGE_LABELS.get(status, "Telephonic")


def status_badge(status: str) -> tuple[str, str]:
    return STATUS_BADGE.get(status, ("pending", "Pending"))


def stage_colors(candidate: Candidate) -> list[str]:
    """
    Color for each of the 4 pipeline segments: Telephonic, Hackathon,
    Assessment, Interview.
      - "green" = completed (successfully)
      - "blue"  = current / in-progress (the next actual step)
      - "red"   = failed at that stage (terminal)
      - "grey"  = not reached yet

    Flow-aware: ai_interview_flow candidates skip Hackathon + Assessment
    entirely once accepted (per is_eligible_for_interview in
    app/pipeline/orchestrator.py), so their bar jumps straight to
    Interview instead of looking stuck at Telephonic.
    """
    status = candidate.status
    is_ai_interview_flow = candidate.flow == "ai_interview_flow"

    if status in ("new", "parsed"):
        return ["blue", "grey", "grey", "grey"]

    if status == "rejected":
        # Rejection stage isn't tracked distinctly on Candidate itself;
        # defaulting to Telephonic since that's the earliest/most common gate.
        return ["red", "grey", "grey", "grey"]

    if status == "accepted":
        if is_ai_interview_flow:
            return ["green", "green", "green", "blue"]
        return ["green", "blue", "grey", "grey"]

    if status == "submitted":
        return ["green", "blue", "grey", "grey"]

    if status == "passed_stage4":
        return ["green", "green", "green", "blue"]

    if status == "failed_stage4":
        return ["green", "green", "red", "grey"]

    if status == "interview_scheduled":
        return ["green", "green", "green", "blue"]

    if status == "interview_passed" or status == "offer":
        return ["green", "green", "green", "green"]

    if status == "interview_failed":
        return ["green", "green", "green", "red"]

    return ["grey", "grey", "grey", "grey"]


def current_score(candidate: Candidate) -> float | None:
    """
    Score shown depends on the candidate's CURRENT status directly --
    NOT on the display label from stage_label(). Checking the label
    text here was the bug: relabeling STAGE_LABELS (e.g. "Interview"
    -> "Interview Scheduled") silently broke this, since the string
    comparison stopped matching and this always fell through to None.
    """
    status = candidate.status

    if status in ("interview_scheduled", "interview_passed", "interview_failed"):
        return _interview_score(candidate)   # None until interview is actually scored

    if status in ("passed_stage4", "failed_stage4"):
        return _assessment_score(candidate)

    return None   # Telephonic / Hackathon (pending review) -- no score yet


def reviewer_count(candidate: Candidate) -> int:
    submission = getattr(candidate, "submission", None)
    submission_reviewers = len(submission.reviews) if submission else 0

    interview_reviewers = sum(
        len(interview.scores) for interview in (candidate.interviews or [])
    )

    return submission_reviewers + interview_reviewers


def days_ago_label(created_at: datetime | None) -> str:
    if not created_at:
        return "recently"

    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    days = (now - created_at).days
    if days <= 0:
        return "today"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


def build_candidate_progress_card(candidate: Candidate) -> dict:
    """
    Builds the dashboard-style progress card: flow tag, applied-ago,
    role (from screening.fit_tag), score, stage label + progress-bar
    colors, and reviewer count. Used by both the dashboard's featured
    candidates and the full department-pipeline list page.
    """
    flow_tag = {
        "ai_interview_flow": ("AI INTERVIEW FLOW", "blue"),
        "ai_hackathon_flow": ("AI HACKATHON FLOW", "purple"),
    }.get(candidate.flow, ("STANDARD", "green"))

    role_label = (
        candidate.screening.fit_tag
        if candidate.screening
        else "Unscreened"
    )

    score = current_score(candidate)

    if candidate.status == "submitted":
        score_display = f"{reviewer_count(candidate)}/2"
        score_sublabel = "REVIEWS"
    elif score is not None:
        score_display = str(score)
        score_sublabel = "AVG. SCORE"
    else:
        score_display = "—"
        score_sublabel = "AVG. SCORE"

    return {
        "id": candidate.id,
        "name": candidate.name,
        "flow_tag_label": flow_tag[0],
        "flow_tag_class": flow_tag[1],
        "applied_ago": days_ago_label(candidate.created_at),
        "role_label": role_label,
        "department": candidate.department or "—",
        "score": score,
        "score_display": score_display,
        "score_sublabel": score_sublabel,
        "stage_label": stage_label(candidate.status),
        "stage_colors": stage_colors(candidate),
        "reviewer_count": reviewer_count(candidate),
        "badge_class": status_badge(candidate.status)[0],
        "badge_label": status_badge(candidate.status)[1],
    }