from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from app.core.auth import (
    get_current_user,
    verify_password,
)
from app.core.db import get_db
from app.core.models import User, Candidate, Submission, Interview
from app.core.config import templates
from app.core.constants import DEPARTMENTS
from app.services.candidates import build_candidate_progress_card

router = APIRouter(
    tags=["Authentication"],
)

@router.get("/")
def index(
    request: Request,
):
    return RedirectResponse(
        request.url_for("dashboard")
    )

@router.get("/login")
def login_page(
    request: Request,
):
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "error": None,
        },
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(
            User.username == username
        )
    )

    if (
        not user
        or not verify_password(
            password,
            user.password_hash,
        )
    ):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Invalid credentials",
            },
            status_code=400,
        )

    request.session["user_id"] = user.id

    return RedirectResponse(
        request.url_for("dashboard"),
        status_code=303,
    )


@router.get("/logout")
def logout(
    request: Request,
):
    request.session.clear()

    return RedirectResponse(
        request.url_for("login_page"),
        status_code=303,
    )


def _active_candidate_count(db: Session, department: str) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Candidate)
        .where(
            Candidate.department == department,
            Candidate.status != "rejected",
        )
    ) or 0


def _status_count(db: Session, department: str, statuses: list[str]) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Candidate)
        .where(
            Candidate.department == department,
            Candidate.status.in_(statuses),
        )
    ) or 0


@router.get("/dashboard", name="dashboard")
def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dept_ids = [d["id"] for d in DEPARTMENTS]

    selected_department = request.query_params.get("department", "AI / ML")
    if selected_department not in dept_ids:
        selected_department = "AI / ML"

    selected_department_label = next(
        (d["label"] for d in DEPARTMENTS if d["id"] == selected_department),
        selected_department,
    )

    dept_counts = {
        dept["id"]: _active_candidate_count(db, dept["id"])
        for dept in DEPARTMENTS
    }

    total_candidates = dept_counts.get(selected_department, 0)

    telephonic_count = _status_count(db, selected_department, ["accepted"])

    # Assessment only applies to AI / ML (the hackathon-review stage) --
    # everyone else skips straight from Telephonic to Interview per
    # PIPELINES in core/config.py, so this stays 0/unused for them.
    assessment_count = _status_count(db, selected_department, ["submitted"])

    # Interview applies to every department.
    interview_count = _status_count(
        db,
        selected_department,
        ["interview_scheduled", "interview_passed", "interview_failed"],
    )

    # NOTE: candidates can now enter a real Offer status.
    offer_count = _status_count(db, selected_department, ["offer"])

    # --- Featured pipeline cards (top 2 most recently active in selected dept) ---
    featured_query = (
        select(Candidate)
        .where(
            Candidate.department == selected_department,
            Candidate.status.notin_(["rejected", "new", "parsed"]),
        )
        .options(
            selectinload(Candidate.submission).selectinload(Submission.reviews),
            selectinload(Candidate.interviews).selectinload(Interview.scores),
            selectinload(Candidate.screening),
        )
        .order_by(Candidate.updated_at.desc())
        .limit(2)
    )
    featured_candidates = [
        build_candidate_progress_card(c) for c in db.scalars(featured_query).all()
    ]

    # --- Recent candidates table (kept cross-department on purpose) ---
    recent_query = (
        select(Candidate)
        .options(
            selectinload(Candidate.submission).selectinload(Submission.reviews),
            selectinload(Candidate.interviews).selectinload(Interview.scores),
            selectinload(Candidate.screening),
        )
        .order_by(Candidate.updated_at.desc())
        .limit(5)
    )
    recent_candidates = [
        build_candidate_progress_card(c) for c in db.scalars(recent_query).all()
    ]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "departments": DEPARTMENTS,
            "selected_department": selected_department,
            "selected_department_label": selected_department_label,
            "total_candidates": total_candidates,
            "dept_counts": dept_counts,
            "telephonic_count": telephonic_count,
            "assessment_count": assessment_count,
            "interview_count": interview_count,
            "offer_count": offer_count,
            "featured_candidates": featured_candidates,
            "recent_candidates": recent_candidates,
        },
    )