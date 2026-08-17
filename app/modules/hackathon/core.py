from __future__ import annotations

from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.models import (
    Candidate, Submission, SubmissionReview,
)
from app.modules.hackathon.ai_hackathon_service import compute_weighted_total
from app.services.candidates import compute_acceptance_deadline
from app.core.config import MIN_REVIEWS_REQUIRED
from app.core.models import User

# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------

def validate_submission(
    candidate: Candidate,
) -> dict:

    if not candidate:
        return {
            "ok": False,
            "reason": "No candidate found for this phone.",
            "deadline_passed": False,
        }

    if candidate.status != "accepted":
        return {
            "ok": False,
            "reason": f"Submission not open (status: {candidate.status})",
            "deadline_passed": False,
        }

    deadline = compute_acceptance_deadline(candidate)

    if deadline and datetime.utcnow() > deadline:
        return {
            "ok": False,
            "reason": None,
            "deadline_passed": True,
        }

    return {
        "ok": True,
        "deadline_passed": False,
    }


# ---------------------------------------------------------
# Pipeline entrypoint — called by orchestrator.advance()
# ---------------------------------------------------------

def save(
    db: Session,
    candidate: Candidate,
    input_data: dict,
) -> None:
    """
    Saves one reviewer's scores, then appends review_count and average
    to input_data so orchestrator.advance() can pass them to
    calculate_score().
    """
    save_review(db, candidate, input_data)

    review_count, average = get_review_average(db, candidate)

    input_data["review_count"] = review_count
    input_data["average"] = average


# ---------------------------------------------------------
# Submission persistence
# ---------------------------------------------------------

def save_submission(
    db: Session,
    candidate: Candidate,
    input_data: dict,
) -> None:

    existing = db.scalar(
        select(Submission).where(
            Submission.candidate_id == candidate.id
        )
    )

    if existing:
        existing.github_link = input_data["github_link"]
        existing.video_link = input_data["video_link"]
        existing.notes = input_data["notes"]

    else:
        db.add(
            Submission(
                candidate_id=candidate.id,
                github_link=input_data["github_link"],
                video_link=input_data["video_link"],
                notes=input_data["notes"],
            )
        )

    db.flush()


# ---------------------------------------------------------
# Review persistence
# ---------------------------------------------------------

def save_review(
    db: Session,
    candidate: Candidate,
    input_data: dict,
    weighted_total_fn=compute_weighted_total,
) -> None:
    """
    Saves one reviewer's score for a submission.

    weighted_total_fn: injected so any module reusing this core
    can supply its own rubric weighting. Defaults to
    ai_hackathon_service.compute_weighted_total.
    """
    submission = db.scalar(
        select(Submission).where(
            Submission.candidate_id == candidate.id
        )
    )

    if not submission:
        raise ValueError(
            f"No submission found for candidate {candidate.id}"
        )

    weighted_total = weighted_total_fn(
        creativity=input_data["creativity"],
        technical_execution=input_data["technical_execution"],
        feasibility=input_data["feasibility"],
        problem_fit_demo=input_data["problem_fit_demo"],
    )

    existing = db.scalar(
        select(SubmissionReview).where(
            SubmissionReview.submission_id == submission.id,
            SubmissionReview.reviewer_id == input_data["reviewer_id"],
        )
    )

    if existing:
        existing.creativity = input_data["creativity"]
        existing.technical_execution = input_data["technical_execution"]
        existing.feasibility = input_data["feasibility"]
        existing.problem_fit_demo = input_data["problem_fit_demo"]
        existing.weighted_total = weighted_total
        existing.comments = input_data["comments"]

    else:
        db.add(
            SubmissionReview(
                submission_id=submission.id,
                reviewer_id=input_data["reviewer_id"],
                creativity=input_data["creativity"],
                technical_execution=input_data["technical_execution"],
                feasibility=input_data["feasibility"],
                problem_fit_demo=input_data["problem_fit_demo"],
                weighted_total=weighted_total,
                comments=input_data["comments"],
            )
        )

    db.flush()


# ---------------------------------------------------------
# Review statistics
# ---------------------------------------------------------

def get_review_average(
    db: Session,
    candidate: Candidate,
) -> tuple[int, float]:

    submission = db.scalar(
        select(Submission).where(
            Submission.candidate_id == candidate.id
        )
    )

    if not submission:
        return 0, 0.0

    reviews = db.scalars(
        select(SubmissionReview).where(
            SubmissionReview.submission_id == submission.id
        )
    ).all()

    count = len(reviews)

    if count == 0:
        return 0, 0.0

    average = round(
        sum(r.weighted_total for r in reviews) / count,
        2,
    )

    return count, average


# ---------------------------------------------------------
# Senior reviews dashboard
# ---------------------------------------------------------

def get_pending_submissions_for_review(
    db: Session,
    reviewer_id: int,
) -> list[dict]:

    candidates = list(
        db.scalars(
            select(Candidate)
            .where(Candidate.status.in_(["submitted", "passed_stage4"]))
            .order_by(Candidate.created_at.desc())
        )
    )

    data = []

    for candidate in candidates:

        if candidate.submission:

            review_count = (
                db.execute(
                    select(func.count(SubmissionReview.id)).where(
                        SubmissionReview.submission_id
                        == candidate.submission.id
                    )
                ).scalar()
                or 0
            )

            already_reviewed = (
                db.scalar(
                    select(SubmissionReview.id).where(
                        SubmissionReview.submission_id
                        == candidate.submission.id,
                        SubmissionReview.reviewer_id == reviewer_id,
                    )
                )
                is not None
            )

        else:
            review_count = 0
            already_reviewed = False

        data.append(
            {
                "candidate": candidate,
                "review_count": int(review_count),
                "already_reviewed": already_reviewed,
            }
        )

    return data


# ---------------------------------------------------------
# HR review summary
# ---------------------------------------------------------

def get_review_summary(
    db: Session,
    candidate: Candidate,
    review_cutoff: float,
) -> dict:

    if candidate.flow == "ai_interview_flow":
        return {
            "reviews": [],
            "review_count": 0,
            "average": 0,
            "review_cutoff": review_cutoff,
            "is_passed": True,
            "ai_interview_flow": True,
            "submission_missing": False,
        }

    if not candidate.submission:
        return {
            "reviews": [],
            "review_count": 0,
            "average": 0,
            "review_cutoff": review_cutoff,
            "is_passed": False,
            "ai_interview_flow": False,
            "submission_missing": True,
        }

    reviews = list(
        db.scalars(
            select(SubmissionReview)
            .where(
                SubmissionReview.submission_id
                == candidate.submission.id
            )
            .order_by(SubmissionReview.created_at.asc())
        )
    )

    review_count, average = get_review_average(db, candidate)

    is_passed = (
        review_count >= MIN_REVIEWS_REQUIRED
        and average >= review_cutoff
    )

    return {
        "reviews": reviews,
        "review_count": review_count,
        "average": average,
        "review_cutoff": review_cutoff,
        "is_passed": is_passed,
        "ai_interview_flow": False,
        "submission_missing": False,
    }

    
def describe_reviews_for_offer_letter(db: Session, candidate: Candidate) -> str:
    """
    Formats this candidate's hackathon submission + reviewer scores as
    plain text, for use as LLM context (e.g. offer letter generation).
    """
    if not candidate.submission or not candidate.submission.reviews:
        return "No hackathon reviews available."

    lines = [f"GitHub submission: {candidate.submission.github_link or 'not provided'}"]
    for r in candidate.submission.reviews:
        reviewer = db.get(User, r.reviewer_id)
        reviewer_name = reviewer.full_name if reviewer else f"user #{r.reviewer_id}"
        lines.append(
            f"- Reviewer {reviewer_name}: weighted total {r.weighted_total} "
            f"(creativity {r.creativity}, technical execution {r.technical_execution}, "
            f"feasibility {r.feasibility}, problem fit demo {r.problem_fit_demo}). "
            f"Comments: {r.comments or 'none'}"
        )
    return "\n".join(lines)