from __future__ import annotations
import time
from io import BytesIO

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Request,
    UploadFile,
    HTTPException,
)
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import select
from app.core.auth import require_role
from app.core.db import get_db
from app.core.models import (
    User,
    Candidate,
    Interview,
    InterviewScore,
    Submission,
    AssessmentCategoryScore,
)
from app.integrations.mock_adapters import merge_excel_api
from app.core.config import templates, logger, PIPELINES
from app.services.excel import (
    build_screening_excel_bytes,
    build_candidates_export_excel_bytes,
    parse_hr_master_rows,
    sync_candidates_from_hr_rows,
)
from app.services.resume import process_resume_batch, save_uploaded_resumes
from app.services.candidates import search_candidates, compute_acceptance_deadline
from app.services.candidates import (
    get_pipeline_data,
    build_candidate_progress_card
)
from app.modules.interview import core as interview_core
from app.core.constants import DEPARTMENTS

router = APIRouter(
    tags=["HR"],
)
from app.services.timeline import build_timeline

AI_ML_DEPARTMENT = "AI / ML"
 
TRIAGE_STATUSES = ("new", "parsed")
 
FLOW_META = {
    "ai_hackathon_flow": {"label": "AI Hackathon", "class": "purple"},
    "ai_interview_flow": {"label": "AI Interview", "class": "blue"},
}
 
 
def _status_tab(status: str) -> str:
    """
    4 tabs now: new / parsed / routed / rejected. "new" and "parsed" are
    real distinct Candidate.status values (parsed = AI extraction done,
    match score + skills available; new = just uploaded, not parsed yet).
    Shortlisting still isn't a persisted state of its own — it's the
    accept+flow decision (process_hr_decision/hr_decision), so once that
    happens the candidate becomes "routed".
    """
    if status == "new":
        return "new"
    if status == "parsed":
        return "parsed"
    if status == "accepted":
        return "routed"
    if status == "rejected":
        return "rejected"
    return "new"
 
 
@router.get(
    "/hr/upload",
    response_class=HTMLResponse,
)
def hr_upload_page(
    request: Request,
    user: User = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Candidate)
        .order_by(Candidate.created_at.desc())
    ).all()
 
    candidates = []
    counts = {"all": 0, "new": 0, "parsed": 0, "routed": 0, "rejected": 0}
 
    for c in rows:
        tab = _status_tab(c.status)
        counts["all"] += 1
        counts[tab] += 1
 
        screening = getattr(c, "screening", None)
        flow_meta = FLOW_META.get(c.flow)
 
        candidates.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            # CONFIRM: where is the original resume filename stored?
            "filename": getattr(c, "resume_filename", None) or "resume.pdf",
            # CONFIRM: no parsed job-title field found yet — using
            # recommended_problem as a placeholder (likely wrong, it's
            # a hackathon problem name, not a role title).
            "role": screening.recommended_problem if screening else "—",
            "department": c.department,
            # CONFIRM: no experience_years field found anywhere yet.
            "experience_years": getattr(c, "experience_years", None),
            "match_score": round(screening.fit_score) if screening and screening.fit_score is not None else None,
            "status_tab": tab,
            "skills": [s.strip() for s in (c.skills or "").split(",") if s.strip()],
            "flow": c.flow,
            "flow_label": flow_meta["label"] if flow_meta else None,
            "flow_class": flow_meta["class"] if flow_meta else None,
        })
 
    return templates.TemplateResponse(
        request,
        "hr_upload.html",
        {
            "user": user,
            "merge_message": None,
            "merge_result": None,
            "candidates": candidates,
            "tab_counts": counts,
            "departments": DEPARTMENTS,
            "ai_ml_department": AI_ML_DEPARTMENT,
        },
    )
 
 
@router.post("/hr/upload")
async def hr_upload(
    request: Request,
    resumes: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    user: User = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    batch_start = time.perf_counter()
 
    logger.info(
        "bulk_upload.start user=%s files=%s",
        user.username,
        len(resumes),
    )
 
    queued_jobs = await save_uploaded_resumes(resumes)
 
    if queued_jobs:
        background_tasks.add_task(
            process_resume_batch,
            queued_jobs,
            user.id,
        )
 
    logger.info(
        "bulk_upload.queued "
        "user=%s queued_files=%s elapsed_sec=%.2f",
        user.username,
        len(queued_jobs),
        time.perf_counter() - batch_start,
    )
 
    return RedirectResponse(
        request.url_for("hr_candidates"),
        status_code=303,
    )
 
# =============================================================
# HR — Merge Excel
# =============================================================

@router.get("/hr/merge-excel")
def hr_merge_excel_page(
    request: Request,
    user: User = Depends(require_role("hr")),
):
    return RedirectResponse(
        request.url_for("hr_upload_page"),
        status_code=303,
    )


@router.post("/hr/merge-excel")
async def hr_merge_excel(
    request: Request,
    hr_file: UploadFile = File(...),
    user: User = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    hr_name = hr_file.filename or ""

    if not hr_name.lower().endswith(".xlsx"):
        return templates.TemplateResponse(
            request,
            "hr_upload.html",
            {
                "user": user,
                "merge_message": (
                    "Please upload a valid "
                    "HR Excel file in .xlsx format."
                ),
                "merge_result": None,
            },
            status_code=400,
        )

    try:
        hr_file_bytes = await hr_file.read()

        screening_bytes = build_screening_excel_bytes(db)

        result = await merge_excel_api(
            hr_file_bytes,
            hr_name,
            screening_bytes,
            "screening_results_generated.xlsx",
        )

        hr_rows, skipped_invalid = parse_hr_master_rows(hr_file_bytes)

        created_count, updated_count, skipped_sync = (
            sync_candidates_from_hr_rows(db, hr_rows)
        )

        return templates.TemplateResponse(
            request,
            "hr_upload.html",
            {
                "user": user,
                "merge_message": (
                    "Merge completed successfully. "
                    f"Candidate sync: "
                    f"created={created_count}, "
                    f"updated={updated_count}, "
                    f"skipped={skipped_invalid + skipped_sync}."
                ),
                "merge_result": result,
            },
        )

    except Exception as exc:
        db.rollback()

        return templates.TemplateResponse(
            request,
            "hr_upload.html",
            {
                "user": user,
                "merge_message": f"Merge failed: {exc}",
                "merge_result": None,
            },
            status_code=502,
        )


@router.get(
    "/hr/candidates",
    name="hr_candidates",
    response_class=HTMLResponse,
)
def hr_candidates(
    request: Request,
    q: str = "",
    fit: str = "",
    status: str = "",
    department: str ="",
    flow: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr", "admin")),
):
    # Filtering + pagination math now lives in the candidates service.
    candidates, total_pages, has_next = search_candidates(
        db,
        q=q,
        fit=fit,
        status=status,
        flow=flow,
        page=page,
        per_page=10,
    )

    return templates.TemplateResponse(
        request,
        "hr_candidates.html",
        {
            "user": user,
            "candidates": candidates,
            "q": q,
            "fit": fit,
            "department": department,
            "status": status,
            "flow": flow,
            "page": page,
            "total_pages": total_pages,
            "has_next": has_next,
        },
    )


@router.get(
    "/hr/candidate/{candidate_id}",
    name="hr_candidate_detail",
    response_class=HTMLResponse,
)
def hr_candidate_detail(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr", "admin")),
):
    candidate = db.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(404, "Candidate not found")

    detail_data = interview_core.get_candidate_detail_data(db, candidate_id)

    # "accepted -> +7 days" rule now lives in the candidates service.
    deadline = compute_acceptance_deadline(candidate)

    return templates.TemplateResponse(
        request,
        "hr_candidate_detail.html",
        {
            "user": user,
            "candidate": detail_data["candidate"],
            "progress_entries": detail_data["progress_entries"],
            "interviews": detail_data["interviews"],
            "seniors": detail_data["seniors"],
            "timeline_rows": build_timeline(db, candidate), 
            "deadline": deadline,
        },
    )

@router.get(
    "/export-candidates-excel",
    name="export_candidates_excel",
)
def export_candidates_excel(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "hr")),
):
    # Workbook construction (querying progress/interviews/scores and
    # formatting rows) now lives in the excel service.
    excel_bytes = build_candidates_export_excel_bytes(db)

    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=final_candidates.xlsx",
        },
    )

@router.get(
    "/hr/talent-pipeline",
    name="talent_pipeline",
)
def talent_pipeline(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr", "admin")),
):
    department = request.query_params.get("department", "AI / ML")
    search = request.query_params.get("search", "").strip()
    seniors = db.scalars(
    select(User).where(User.role == "senior_dev").order_by(User.full_name)
).all()
 
    pipeline_data = get_pipeline_data(db, department)

    if search:
        needle = search.lower()
        for column in pipeline_data:
            column["candidates"] = [
                c for c in column["candidates"] if needle in c["name"].lower()
            ]

    return templates.TemplateResponse(
        request,
        "talent_pipeline.html",
        {
            "user": user,
            "departments": DEPARTMENTS,
            "selected_department": department,
            "search": search,
            "pipeline_data": pipeline_data,
            "seniors": seniors,
        },
    )

@router.get(
    "/hr/department-pipeline",
    name="department_pipeline",
)
def department_pipeline(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr", "admin")),
):
    department = request.query_params.get("department", "AI / ML")
    if department not in PIPELINES:
        department = "AI / ML"

    department_label = next(
        (d["label"] for d in DEPARTMENTS if d["id"] == department),
        department,
    )

    candidates_query = (
        select(Candidate)
        .where(
            Candidate.department == department,
            Candidate.status != "rejected",
        )
        .options(
            selectinload(Candidate.submission).selectinload(Submission.reviews),
            selectinload(Candidate.interviews).selectinload(Interview.scores),
            selectinload(Candidate.screening),
        )
        .order_by(Candidate.updated_at.desc())
    )

    candidates = [
        build_candidate_progress_card(c) for c in db.scalars(candidates_query).all()
    ]

    return templates.TemplateResponse(
        request,
        "department_pipeline.html",
        {
            "user": user,
            "departments": DEPARTMENTS,
            "selected_department": department,
            "selected_department_label": department_label,
            "candidates": candidates,
        },
    )
@router.get(
    "/hr/candidates/{candidate_id}",
    name="final_candidate_summary",
)
def final_candidate_detail(
    request: Request,
    candidate_id: int,
    message: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr", "admin")),
):
    candidate = db.scalar(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(
            # matches the relationship names used in department_pipeline() above:
            # Candidate.submission -> Submission, Submission.reviews -> hackathon reviewer scores
            selectinload(Candidate.submission).selectinload(Submission.reviews),
            selectinload(Candidate.interviews).selectinload(Interview.scores).selectinload(InterviewScore.interviewer),
        )
    )

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    seniors = list(
        db.scalars(
            select(User)
            .where(User.role == "senior_dev")
            .order_by(User.full_name.asc())
        )
    )

    raw_reviews = (candidate.submission.reviews if candidate.submission else []) or []
    raw_reviews = sorted(raw_reviews, key=lambda r: r.created_at)

    score_ids = [
        score.id
        for interview in candidate.interviews or []
        for score in interview.scores or []
        if getattr(score, "id", None) is not None
    ]
    category_map: dict[int, list[AssessmentCategoryScore]] = {}
    if score_ids:
        category_rows = db.scalars(
            select(AssessmentCategoryScore).where(
                AssessmentCategoryScore.interview_score_id.in_(score_ids)
            )
        ).all()
        for category in category_rows:
            category_map.setdefault(category.interview_score_id, []).append(category)

    hackathon_reviews = []
    for r in raw_reviews:
        hackathon_reviews.append({
            "reviewer_id": r.reviewer_id,
            "creativity": r.creativity,
            "technical": r.technical_execution,
            "feasibility": r.feasibility,
            "problem_fit": r.problem_fit_demo,
            "weighted_total": r.weighted_total,
            "comments": r.comments,
        })

    # GitHub URL: try several likely field names on Submission until one is non-empty
    submission = candidate.submission
    github_url = None
    github_submitted_at = None
    if submission:
        for field in ("github_url", "repo_url", "repository_url", "github_link", "github_repo"):
            value = getattr(submission, field, None)
            if value:
                github_url = value
                break
        for field in ("submitted_at", "created_at", "uploaded_at"):
            value = getattr(submission, field, None)
            if value:
                github_submitted_at = value
                break

    interview_scores = []
    for interview in sorted(candidate.interviews or [], key=lambda i: getattr(i, "id", 0)):
        for score in (interview.scores or []):
            interviewer = getattr(score, "interviewer", None)
            interview_scores.append({
                "interview_id": interview.id,
                "interviewer_name": getattr(interviewer, "full_name", None) or "Unknown",
                "interviewer_username": getattr(interviewer, "username", None) or "",
                "score": getattr(score, "score", None),
                "role_assessed": getattr(score, "role_assessed", None),
                "recommendation": getattr(score, "recommendation", None),
                "comments": getattr(score, "comments", None) or getattr(score, "feedback", None) or getattr(score, "notes", None),
                "categories": [
                    {
                        "category_title": category.category_title,
                        "raw_score": category.raw_score,
                        "max_score": category.max_score,
                        "percentage": category.percentage,
                    }
                    for category in category_map.get(score.id, [])
                ],
            })

    # weighted-total average across hackathon reviewers, shown as a summary stat
    weighted_totals = [
        r["weighted_total"] for r in hackathon_reviews if r["weighted_total"] is not None
    ]
    avg_weighted_total = (
        round(sum(weighted_totals) / len(weighted_totals), 1) if weighted_totals else None
    )

    return templates.TemplateResponse(
        request,
        "final_candidate_summary.html",
        {
            "user": user,
            "candidate": candidate,
            "message": message,
            "error": error,
            "seniors": seniors,
            "github_url": github_url,
            "github_submitted_at": github_submitted_at,
            "hackathon_reviews": hackathon_reviews,
            "interview_scores": interview_scores,
            "avg_weighted_total": avg_weighted_total,
        },
    )