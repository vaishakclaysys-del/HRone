from __future__ import annotations
from select import select

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.config import templates
from app.core.db import get_db
from app.core.models import Candidate, Interview, User
from app.modules.interview import ai_interview_service, core as interview_core
from app.pipeline.orchestrator import THRESHOLDS
from app.pipeline.utils import log_progress, update_candidate_status
from app.services import offer_letter as offer_service
import app.pipeline as pipeline
from sqlalchemy import select
from app.core.models import Interview, User
# from tests.test_pipeline import db
router = APIRouter(
    prefix="/ai-interview",
    tags=["AI Interview"],
)

hackathon_threshold = THRESHOLDS["hackathon"]

DEPARTMENT_RUBRIC_MAP = {
    "AI / ML": "aiml_engineer",
    # future: "QA": "qa_interview",
}

def get_rubric_name_for_candidate(candidate: Candidate) -> str | None:
    department = (candidate.department or "").strip()
    return DEPARTMENT_RUBRIC_MAP.get(department)

# ---------------------------------------------------------
# HR — interviews dashboard
# ---------------------------------------------------------

@router.get(
    "/hr/interviews",
    response_class=HTMLResponse,
)
def hr_interviews(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr")),
):
    data = interview_core.get_interview_dashboard(
        db,
        threshold=hackathon_threshold,
        skip_reviews_fn=pipeline.should_skip_reviews,
    )

    return templates.TemplateResponse(
        request,
        "hr_interviews.html",
        {
            "user": user,
            "review_cutoff": hackathon_threshold,
            **data,
        },
    )


# ---------------------------------------------------------
# HR — schedule interview
# ---------------------------------------------------------

@router.post(
    "/hr/interviews",
    name="hr_schedule_interview",
)
def hr_schedule_interview(
    request: Request,
    candidate_id: int = Form(...),
    interviewer_usernames: list[str] = Form(
        alias="interviewer_username[]"
    ),
    scheduled_at: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr")),
):
    candidate = db.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(404, "Candidate not found")

    if not pipeline.is_eligible_for_interview(candidate):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Candidate is not eligible for interview scheduling "
                f"(status={candidate.status!r})"
            ),
        )

    try:
        created = interview_core.schedule_interviews(
            db=db,
            candidate=candidate,
            interviewer_usernames=interviewer_usernames,
            scheduled_at=scheduled_at,
            created_by=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    update_candidate_status(db, candidate, "interview_scheduled", stage=6)

    log_progress(
        db,
        candidate.id,
        6,
        f"interview_scheduled ({', '.join(created)})",
        f"{scheduled_at} with {', '.join(created)}",
        user.id,
    )

    db.commit()

    return RedirectResponse(
        request.url_for("hr_interviews"),
        status_code=303,
    )


# ---------------------------------------------------------
# Senior — interviews list
# ---------------------------------------------------------
from collections import OrderedDict

@router.get(
    "/senior/interviews",
    name="senior_interviews",
    response_class=HTMLResponse,
)
def senior_interviews(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("senior_dev", "admin")),
):
 
    if user.role == "admin":
        rows = db.execute(
            select(Interview, User.full_name)
            .join(User, Interview.interviewer_id == User.id)
            .where(Interview.status.in_(["completed", "scheduled"]))
            .order_by(Interview.scheduled_at.desc())
        ).all()
 
        grouped = OrderedDict()
        for interview, interviewer_name in rows:
            key = (interview.candidate_id, interview.scheduled_at)
            if key not in grouped:
                grouped[key] = {
                    "interview": interview,       # representative row (candidate, scheduled_at, id, etc.)
                    "interviewer_names": [],
                    "statuses": set(),
                }
            grouped[key]["interviewer_names"].append(interviewer_name)
            grouped[key]["statuses"].add(interview.status)
 
        interviews = []
        for g in grouped.values():
            statuses = g["statuses"]
            # Only "completed" once EVERY interviewer for this candidate/slot is done.
            # If any interviewer is still "scheduled", the whole row stays "scheduled".
            merged_status = "scheduled" if "scheduled" in statuses else "completed"
 
            interviews.append({
                "interview": g["interview"],
                "interviewer_name": ", ".join(g["interviewer_names"]),
                "status": merged_status,
            })
 
    else:
        interviews = list(
            db.scalars(
                select(Interview)
                .where(Interview.interviewer_id == user.id)
                .order_by(Interview.scheduled_at)
            )
        )
 
    return templates.TemplateResponse(
        request,
        "senior_interviews.html",
        {
            "request": request,
            "user": user,
            "interviews": interviews,
        },
    )
# ---------------------------------------------------------
# Senior — interview form
# ---------------------------------------------------------

@router.get(
    "/senior/interview/{interview_id}",
    name="senior_interview_form",
    response_class=HTMLResponse,
)
def senior_interview_form(
    interview_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("senior_dev")),
):
    interview = db.get(Interview, interview_id)

    if not interview or interview.interviewer_id != user.id:
        raise HTTPException(status_code=404, detail="Interview not found")

    rubric_name = get_rubric_name_for_candidate(interview.candidate)

    return templates.TemplateResponse(
        request,
        "senior_interview_form.html",
        {
            "user": user,
            "interview": interview,
            "interview_datetime": interview.scheduled_at,
            "rubric_name": rubric_name,
            "root_path": request.scope.get("root_path", ""),
        },
    )


# ---------------------------------------------------------
# Senior — submit interview score
# ---------------------------------------------------------

@router.post("/submit/{interview_id}", name="submit_interview")
async def submit_interview(
    request: Request,
    interview_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("senior_dev")),
):
    interview = db.get(Interview, interview_id)

    if not interview or interview.interviewer_id != user.id:
        raise HTTPException(status_code=404, detail="Interview not found")

    candidate = db.get(Candidate, interview.candidate_id)

    rubric_name = get_rubric_name_for_candidate(candidate)
    if not rubric_name:
        raise HTTPException(status_code=400, detail="No rubric defined for this candidate department.")

    form = await request.form()
    input_data = {
        "interview_id": interview_id,
        "interviewer_id": user.id,
    }
    reserved_keys = {"notes", "role_assessed", "recommendation", "score"}

    for key, value in form.items():
        if key in reserved_keys:
            continue
        if value is None:
            continue
        raw_value = value if not isinstance(value, str) else value.strip()

        if raw_value == "":
            input_data[key] = raw_value
            continue

        try:
            input_data[key] = int(raw_value)
            continue
        except (TypeError, ValueError):
            pass

        try:
            input_data[key] = float(raw_value)
            continue
        except (TypeError, ValueError):
            pass

        input_data[key] = raw_value

    input_data["notes"] = form.get("notes", "") or ""
    input_data["role_assessed"] = form.get("role_assessed", "") or ""
    input_data["recommendation"] = form.get("recommendation", "") or ""

    result = interview_core.submit_score(
        db,
        candidate,
        input_data,
        score_fn=ai_interview_service.calculate_score,
        rubric_name=rubric_name,
        breakdown_fn=ai_interview_service.build_score_breakdown,
    )

    log_progress(
        db,
        candidate.id,
        6,
        "interview_score_submitted",
        f"{user.username} — Score: {result['score']}",
        user.id,
    )

    db.commit()

    if not result["all_scored"]:
        return RedirectResponse(
            request.url_for("senior_interviews"),
            status_code=303,
        )

    pipeline.advance(
        db,
        candidate,
        "interview",
        {"avg_score": result["avg_score"]},
    )

    return RedirectResponse(
        request.url_for("senior_interviews"),
        status_code=303,
    )


# ---------------------------------------------------------
# HR / Admin — suggest interviewers (JSON)
# ---------------------------------------------------------

@router.get("/hr/suggest-interviewers/{candidate_id}")
def suggest_interviewers_route(
    candidate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr")),
):
    candidate = db.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(404, "Candidate not found")

    matches = interview_core.suggest_interviewers(db, candidate.skills)
    return {"matches": matches}


# ---------------------------------------------------------
# HR / Admin — final results
# ---------------------------------------------------------

@router.get(
    "/final",
    response_class=HTMLResponse,
    name="final_candidate_list",
)
def final_results(
    request: Request,
    message: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr", "admin")),
):
    # Offer Center removed — redirect to HR candidates listing
    return RedirectResponse(request.url_for("hr_candidates"), status_code=303)


@router.post(
    "/final/{candidate_id}/offer",
    name="final_mark_offer",
)
def final_mark_offer(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    candidate = db.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(404, "Candidate not found")

    if candidate.status == "offer":
        return RedirectResponse(
            request.url_for("final_candidate_list").include_query_params(
                message="Candidate is already in the offer stage."
            ),
            status_code=303,
        )

    if candidate.status != "interview_passed":
        return RedirectResponse(
            request.url_for("final_candidate_list").include_query_params(
                error="Candidate must have passed interview before moving to Offer."
            ),
            status_code=303,
        )

    candidate.status = "offer"
    candidate.stage = 8

    log_progress(
        db,
        candidate.id,
        8,
        "offer_selected",
        "Moved candidate to Offer stage",
        user.id,
    )

    db.commit()

    return_to = request.query_params.get('return_to') or ''
    if return_to == 'detail':
        return RedirectResponse(
            request.url_for(
                "final_candidate_detail",
                candidate_id=candidate.id,
            ).include_query_params(
                message="Candidate moved to Offer stage successfully."
            ),
            status_code=303,
        )

    return RedirectResponse(
        request.url_for("final_candidate_list").include_query_params(
            message="Candidate moved to Offer stage successfully."
        ),
        status_code=303,
    )


@router.post(
    "/final/{candidate_id}/reject",
    name="final_mark_reject",
)
async def final_mark_reject(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    candidate = db.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(404, "Candidate not found")

    if candidate.status == "rejected":
        return RedirectResponse(
            request.url_for("final_candidate_list").include_query_params(
                message="Candidate is already rejected."
            ),
            status_code=303,
        )

    # Allow admin to reject at final stage to end the workflow
    candidate.status = "rejected"
    candidate.stage = 0

    log_progress(
        db,
        candidate.id,
        candidate.stage,
        "admin_rejected",
        "Rejected by admin at final stage",
        user.id,
    )

    db.commit()

    # respect optional return_to (form/query) to stay on detail page when invoked from there
    # prefer form value if present
    form = None
    try:
        form = await request.form()
    except Exception:
        form = None

    return_to = ''
    if form and 'return_to' in form:
        return_to = form.get('return_to')
    else:
        return_to = request.query_params.get('return_to', '')

    if return_to == 'detail':
        return RedirectResponse(
            request.url_for(
                "final_candidate_detail",
                candidate_id=candidate.id,
            ).include_query_params(
                message="Candidate rejected successfully."
            ),
            status_code=303,
        )

    return RedirectResponse(
        request.url_for("final_candidate_list").include_query_params(
            message="Candidate rejected successfully."
        ),
        status_code=303,
    )


@router.post(
    "/generate/{candidate_id}",
    name="generate_offer_letter_route",
)
async def generate_offer_letter_route(
    candidate_id: int,
    job_position: str = Form(""),
    reporting_to: str = Form(""),
    salary: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr", "admin")),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")

    letter_text = await offer_service.generate_offer_letter(
        db, candidate, job_position, reporting_to, salary,
    )
    email_template = offer_service.build_admin_email_template(
        candidate,
        letter_text,
        job_position,
        reporting_to,
        salary,
    )
    return {"letter": letter_text, "email_template": email_template}


# ---------------------------------------------------------
# HR / Admin — final candidate detail
# ---------------------------------------------------------

@router.get(
    "/final/{candidate_id}",
    response_class=HTMLResponse,
    name="final_candidate_detail",
)
def final_candidate_detail(
    candidate_id: int,
    request: Request,
    message: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr", "admin")),
):
    try:
        data = interview_core.get_candidate_detail_data(db, candidate_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return templates.TemplateResponse(
        request,
        "final_candidate_detail.html",
        {
            "user": user,
            "message": message,
            "error": error,
            **data,
        },
    )


# ---------------------------------------------------------
# Admin — edit interviewer
# ---------------------------------------------------------

@router.post(
    "/final/{candidate_id}/interview/{interview_id}/interviewer",
    name="final_edit_interviewer",
)
def final_edit_interviewer(
    candidate_id: int,
    interview_id: int,
    request: Request,
    interviewer_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    candidate = db.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(404, "Candidate not found")

    try:
        new_username = interview_core.edit_interviewer(
            db=db,
            candidate=candidate,
            interview_id=interview_id,
            new_interviewer_id=interviewer_id,
        )
    except ValueError as e:
        return RedirectResponse(
            request.url_for(
                "final_candidate_detail",
                candidate_id=candidate.id,
            ).include_query_params(error=str(e)),
            status_code=303,
        )

    db.commit()

    return RedirectResponse(
        request.url_for(
            "final_candidate_detail",
            candidate_id=candidate.id,
        ).include_query_params(
            message=f"Interviewer updated to {new_username}."
        ),
        status_code=303,
    )


# ---------------------------------------------------------
# Admin — add interviewer
# ---------------------------------------------------------

@router.post(
    "/final/{candidate_id}/interviewers",
    name="final_add_interviewer",
)
def final_add_interviewer(
    candidate_id: int,
    request: Request,
    interviewer_id: int = Form(...),
    scheduled_at: str = Form(...),
    return_to: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    candidate = db.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(404, "Candidate not found")

    try:
        new_username = interview_core.add_interviewer(
            db=db,
            candidate=candidate,
            interviewer_id=interviewer_id,
            scheduled_at=scheduled_at,
            created_by=user.id,
        )
    except ValueError as e:
        target_route = "final_candidate_summary" if return_to == "summary" else "final_candidate_detail"
        return RedirectResponse(
            request.url_for(
                target_route,
                candidate_id=candidate.id,
            ).include_query_params(error=str(e)),
            status_code=303,
        )

    log_progress(
        db,
        candidate.id,
        6,
        "interview_added_by_admin",
        f"{scheduled_at} with {new_username}",
        user.id,
    )

    db.commit()

    return RedirectResponse(
        request.url_for(
            "final_candidate_summary" if return_to == "summary" else "final_candidate_detail",
            candidate_id=candidate.id,
        ).include_query_params(
            message=f"Interviewer {new_username} added successfully."
        ),
        status_code=303,
    )
