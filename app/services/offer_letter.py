from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.models import Candidate
from app.integrations.llm_adapter import generate_text
from app.modules.hackathon import core as hackathon_core
from app.modules.interview import core as interview_core

OFFER_SUMMARY_SYSTEM_PROMPT = (
    "You are an HR assistant drafting the candidate-assessment section of a "
    "formal job offer letter. Base your summary ONLY on the interview/hackathon "
    "notes and scores provided below — do not invent strengths, weaknesses, or "
    "details that aren't supported by that material. This works across "
    "departments (AI/ML, QA, or any other) — do not assume a specific domain "
    "unless the provided notes indicate one. Note: individual question-level "
    "interview scores are not yet available in this system — only the overall "
    "interview score and free-text notes are provided. Do not claim to know "
    "granular breakdowns that weren't given to you. If the provided notes are "
    "thin, keep the summary brief rather than filling in gaps."
)


def _fmt(value: str | None, placeholder: str = "TBD") -> str:
    value = (value or "").strip()
    return value if value else placeholder


def build_admin_email_template(
    candidate: Candidate,
    offer_letter_text: str,
    job_position: str,
    reporting_to: str,
    salary: str,
) -> str:
    subject = f"Offer Letter Draft for {candidate.name}"
    body_lines = [
        f"Hi {candidate.name},",
        "",
        f"Please find the offer letter draft for the {job_position or 'requested role'} role below.",
        "",
        offer_letter_text,
        "",
        f"Reporting To: {_fmt(reporting_to)}",
        f"Salary: {_fmt(salary)}",
        "",
        "Best regards,",
        "HR Team",
    ]
    return "\n".join([f"Subject: {subject}", *body_lines])


def _build_prompt(
    db: Session,
    candidate: Candidate,
    job_position: str,
    reporting_to: str,
    salary: str,
) -> str:
    sections = [
        f"Candidate name: {candidate.name}",
        f"Candidate email: {candidate.email}",
        f"Department: {candidate.department or 'not specified'}",
        f"Skills: {candidate.skills or 'not specified'}",
        f"Job position: {job_position}",
        f"Reporting to: {_fmt(reporting_to)}",
        f"Salary: {_fmt(salary)}",
    ]

    # Flow-structure decision (does this candidate's flow even have a
    # hackathon stage) — lives here, not duplicated inside every module.
    if candidate.flow == "ai_hackathon_flow":
        hackathon_notes = hackathon_core.describe_reviews_for_offer_letter(db, candidate)
        sections.append(f"\nHackathon stage notes:\n{hackathon_notes}")

    interview_notes = interview_core.describe_scores_for_offer_letter(db, candidate)
    sections.append(f"\nInterview stage notes:\n{interview_notes}")

    sections.append(
        "\nUsing the above, write the offer letter in this exact format. If "
        "'Reporting to' or 'Salary' are 'TBD', keep them as 'TBD' in the "
        "output — do not guess a value. Replace every placeholder with the "
        "provided candidate or offer value.\n\n"
        "After conducting the hackathon and interview process for <candidate name>, "
        "following is the summary of the candidate.\n\n"
        "Strengths & Weaknesses:\n<2-4 sentences>\n\n"
        "Key Insights from Interview:\n<2-4 sentences>\n\n"
        "Overall Summary:\n<2-4 sentences>\n\n"
        "Then provide these details at the end. Keep the labels exactly as shown "
        "and do not add any other content after Salary:\n"
        "Candidate name: <name>\n"
        "Candidate email: <email>\n"
        "Job Position info:\n"
        "Job position: <position>\n"
        "Reporting To: <reporting to>\n"
        "Salary: <salary>\n\n"
        "Do not include a separate 'Summary:' heading."
    )
    return "\n".join(sections)


async def generate_offer_letter(
    db: Session,
    candidate: Candidate,
    job_position: str,
    reporting_to: str = "",
    salary: str = "",
) -> str:
    prompt = _build_prompt(db, candidate, job_position, reporting_to, salary)
    print(f"[offer-letter] prompt:\n{prompt}", flush=True)
    response = await generate_text(prompt, system=OFFER_SUMMARY_SYSTEM_PROMPT, debug=True)
    print(f"[offer-letter] response:\n{response}", flush=True)
    return response