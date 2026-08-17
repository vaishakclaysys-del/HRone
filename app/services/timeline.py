"""
Flow-driven timeline builder — single source of truth for how a
candidate's progress renders, regardless of which page includes it.

Row order comes from each flow's step definition (mirroring
app.pipeline.orchestrator.FLOWS), never from sorting timestamps.
Each step reads its own authoritative record for its timestamp, so
there is exactly one place that "knows" when a thing happened.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Candidate, CandidateProgress, Submission, Interview, User
from app.core.config import MIN_REVIEWS_REQUIRED
from app.pipeline.orchestrator import FLOWS

@dataclass
class TimelineRow:
    time: Optional[datetime]
    label: str
    description: str
    completed: bool


class _Ctx:
    """Everything a step needs, fetched once per build_timeline() call."""

    def __init__(self, db: Session, candidate: Candidate):
        self.db = db
        self.candidate = candidate

        self.progress_by_event: dict[str, list[CandidateProgress]] = {}
        for p in db.scalars(
            select(CandidateProgress)
            .where(CandidateProgress.candidate_id == candidate.id)
            .order_by(CandidateProgress.created_at)
        ):
            self.progress_by_event.setdefault(p.event, []).append(p)

        self.submission = db.scalar(
            select(Submission).where(Submission.candidate_id == candidate.id)
        )
        self.reviews = (
            sorted(self.submission.reviews, key=lambda r: r.created_at)
            if self.submission else []
        )
        self.interviews = list(
            db.scalars(
                select(Interview)
                .where(Interview.candidate_id == candidate.id)
                .order_by(Interview.created_at)
            )
        )
        self._users: dict[int, str] = {}

    def user_label(self, user_id: int) -> str:
        if user_id not in self._users:
            u = self.db.get(User, user_id)
            self._users[user_id] = f"{u.full_name} ({u.username})" if u else f"user #{user_id}"
        return self._users[user_id]

    def first(self, event: str) -> Optional[CandidateProgress]:
        rows = self.progress_by_event.get(event)
        return rows[0] if rows else None

    def first_starting_with(self, prefix: str) -> Optional[CandidateProgress]:
        for evt, rows in self.progress_by_event.items():
            if evt.startswith(prefix):
                return rows[0]
        return None


# ---------------------------------------------------------------
# Steps shared by every flow
# ---------------------------------------------------------------

def _step_hr_decision(ctx: _Ctx) -> list[TimelineRow]:
    p = ctx.first("hr_accept") or ctx.first("hr_reject")
    if not p:
        return []
    label = "Hr Accept" if p.event == "hr_accept" else "Hr Reject"
    return [TimelineRow(p.created_at, label, p.details or "—", True)]


def _step_flow_assigned(ctx: _Ctx) -> list[TimelineRow]:
    p = ctx.first("flow_assigned")
    if not p:
        return []
    return [TimelineRow(p.created_at, "Flow Assigned", p.details or "—", True)]


# ---------------------------------------------------------------
# "hackathon" module steps
# ---------------------------------------------------------------

def _step_hackathon_submitted(ctx: _Ctx) -> list[TimelineRow]:
    if ctx.submission:
        return [TimelineRow(
            ctx.submission.submitted_at, "Hackathon Submitted",
            f"Github: {ctx.submission.github_link}", True,
        )]
    return [TimelineRow(None, "Hackathon Submitted", "Awaiting candidate submission", False)]


def _step_senior_reviews(ctx: _Ctx) -> list[TimelineRow]:
    rows = []

    for i in range(MIN_REVIEWS_REQUIRED):
        label = f"Senior Review {i + 1}"

        if not ctx.submission:
            rows.append(
                TimelineRow(
                    None,
                    label,
                    f"Awaiting hackathon submission before review #{i + 1}",
                    False,
                )
            )
            continue

        if i < len(ctx.reviews):
            r = ctx.reviews[i]
            rows.append(
                TimelineRow(
                    r.created_at,
                    label,
                    f"{ctx.user_label(r.reviewer_id)} — Score: {r.weighted_total}",
                    True,
                )
            )
        else:
            rows.append(
                TimelineRow(
                    None,
                    label,
                    f"Awaiting review #{i + 1}",
                    False,
                )
            )

    return rows

def _step_hackathon_outcome(ctx: _Ctx) -> list[TimelineRow]:
    p = ctx.first("hackathon_passed") or ctx.first("hackathon_failed")
    if not p:
        return []
    label = "Hackathon Passed" if p.event == "hackathon_passed" else "Hackathon Failed"
    return [TimelineRow(p.created_at, label, p.details or "—", True)]


# ---------------------------------------------------------------
# "interview" module steps
# ---------------------------------------------------------------

def _step_interview_scheduled(ctx: _Ctx) -> list[TimelineRow]:
    p = ctx.first_starting_with("interview_scheduled")
    if p:
        return [TimelineRow(p.created_at, "Interview Scheduled", p.details or "—", True)]
    if ctx.interviews:
        first = min(ctx.interviews, key=lambda i: i.created_at)
        return [TimelineRow(
            first.created_at, "Interview Scheduled",
            f"Scheduled with {len(ctx.interviews)} interviewer(s)", True,
        )]
    return [TimelineRow(None, "Interview Scheduled", "Awaiting HR to schedule the interview", False)]


def _step_interview_scores(ctx: _Ctx) -> list[TimelineRow]:
    rows = []
    for interview in ctx.interviews:
        if interview.scores:
            score = interview.scores[0]
            rows.append(TimelineRow(
                score.created_at, "Interview Score Submitted",
                f"{ctx.user_label(interview.interviewer_id)} — Score: {score.score}", True,
            ))
        else:
            rows.append(TimelineRow(
                None, "Interview Score Submitted",
                f"{ctx.user_label(interview.interviewer_id)} — Score: pending", False,
            ))
    return rows


def _step_interview_outcome(ctx: _Ctx) -> list[TimelineRow]:
    if ctx.candidate.status in ("interview_passed", "interview_failed"):
        event = "interview_passed" if ctx.candidate.status == "interview_passed" else "interview_failed"
        p = ctx.first(event)
        if p:
            label = "Interview Passed" if event == "interview_passed" else "Interview Failed"
            return [TimelineRow(p.created_at, label, p.details or "—", True)]
    return []


# ---------------------------------------------------------------
# Module name -> step list. Keys match app.pipeline.orchestrator.FLOWS
# module names exactly, so this can never silently drift from the
# real flow definition.
# ---------------------------------------------------------------

_MODULE_STEPS: dict[str, list[Callable[[_Ctx], list[TimelineRow]]]] = {
    "hackathon": [_step_hackathon_submitted, _step_senior_reviews, _step_hackathon_outcome],
    "interview": [_step_interview_scheduled, _step_interview_scores, _step_interview_outcome],
}


def build_timeline(db: Session, candidate: Candidate) -> list[TimelineRow]:
    ctx = _Ctx(db, candidate)
    steps = [_step_hr_decision, _step_flow_assigned]

    for module_name in FLOWS.get(candidate.flow, []):

        # Stop the timeline after hackathon failure
        if candidate.status == "failed_stage4" and module_name == "interview":
            break

        steps.extend(_MODULE_STEPS.get(module_name, []))

    rows: list[TimelineRow] = []
    for step in steps:
        rows.extend(step(ctx))

    return rows