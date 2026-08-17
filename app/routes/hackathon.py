from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_optional_user, require_role
from app.core.config import templates
from app.core.db import get_db
from app.core.models import Candidate, User, CandidateProgress
from app.core.phone_utils import find_candidate_by_phone
from app.modules.hackathon import core as hackathon_core
from app.pipeline.orchestrator import THRESHOLDS
import app.pipeline as pipeline
from app.services.timeline import build_timeline

router = APIRouter(
    prefix="/hackathon",
    tags=["Hackathon"],
)

hackathon_threshold = THRESHOLDS["hackathon"]


# ---------------------------------------------------------
# Candidate — submission page
# ---------------------------------------------------------

@router.get(
    "/candidate/submit",
    response_class=HTMLResponse,
)
def candidate_submit_page(
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    return templates.TemplateResponse(
        request,
        "candidate_submit.html",
        {
            "user": user,
            "message": None,
            "deadline_passed": False,
        },
    )


# ---------------------------------------------------------
# Candidate — submit hackathon project
# ---------------------------------------------------------

@router.post(
    "/submit",
    name="submit_hackathon_route",
    response_class=HTMLResponse,
)
def submit_hackathon_route(
    request: Request,
    phone: str = Form(...),
    github_link: str = Form(...),
    video_link: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    candidate = find_candidate_by_phone(db, phone)

    validation = hackathon_core.validate_submission(candidate)

    if not validation["ok"]:
        return templates.TemplateResponse(
            request,
            "candidate_submit.html",
            {
                "user": user,
                "message": validation["reason"],
                "deadline_passed": validation["deadline_passed"],
            },
            status_code=400,
        )

    input_data = {
        "github_link": github_link,
        "video_link": video_link,
        "notes": notes,
    }

    hackathon_core.save_submission(db, candidate, input_data)
    pipeline.on_hackathon_submitted(db, candidate, input_data)

    db.commit()

    return templates.TemplateResponse(
        request,
        "candidate_submit.html",
        {
            "user": user,
            "message": "Submission saved",
            "deadline_passed": False,
        },
        status_code=200,
    )


# ---------------------------------------------------------
# Senior — pending reviews dashboard
# ---------------------------------------------------------

@router.get(
    "/senior/reviews",
    response_class=HTMLResponse,
)
def senior_reviews(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("senior_dev", "admin")),
):
    data = hackathon_core.get_pending_submissions_for_review(
        db,
        user.id,
    )

    return templates.TemplateResponse(
        request,
        "senior_reviews.html",
        {
            "user": user,
            "candidates": data,
        },
    )


# ---------------------------------------------------------
# Senior — review detail page
# ---------------------------------------------------------

@router.get(
    "/senior/review/{candidate_id}",
    response_class=HTMLResponse,
)
def senior_review_page(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("senior_dev")),
):
    candidate = db.get(Candidate, candidate_id)

    if not candidate or not candidate.submission:
        raise HTTPException(
            status_code=404,
            detail="Submission not found",
        )

    return templates.TemplateResponse(
        request,
        "senior_review_detail.html",
        {
            "user": user,
            "candidate": candidate,
        },
    )


# ---------------------------------------------------------
# Senior — submit review
# ---------------------------------------------------------

@router.post(
    "/review/{candidate_id}",
    name="submit_hackathon_review",
)
def submit_hackathon_review_route(
    request: Request,
    candidate_id: int,
    creativity: int = Form(...),
    technical_execution: int = Form(...),
    feasibility: int = Form(...),
    problem_fit_demo: int = Form(...),
    comments: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("senior_dev")),
):
    candidate = db.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        )

    input_data = {
        "reviewer_id": user.id,
        "creativity": creativity,
        "technical_execution": technical_execution,
        "feasibility": feasibility,
        "problem_fit_demo": problem_fit_demo,
        "comments": comments,
    }

    pipeline.advance(db, candidate, "hackathon", input_data)

    return RedirectResponse(
        request.url_for("senior_reviews"),
        status_code=303,
    )


# ---------------------------------------------------------
# HR — review summary
# ---------------------------------------------------------

@router.get(
    "/hr/review-summary/{candidate_id}",
    name="hr_review_summary",
    response_class=HTMLResponse,
)

def hr_review_summary(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr","admin")),
):
    candidate = db.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    summary = hackathon_core.get_review_summary(db, candidate, hackathon_threshold)

    progress_entries = list(
        db.scalars(
            select(CandidateProgress)
            .where(CandidateProgress.candidate_id == candidate_id)
            .order_by(CandidateProgress.created_at)
        )
    )
    seniors = list(
        db.scalars(select(User).where(User.role == "senior_dev").order_by(User.full_name.asc()))
    )

    return templates.TemplateResponse(
        request,
        "hr_review_summary.html",
        {
            "request": request,
            "user": user,
            "candidate": candidate,
            "progress_entries": progress_entries,
            "seniors": seniors,
            "timeline_rows": build_timeline(db, candidate), 
            **summary,
        },
    )
