from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path

import httpx


PROBLEMS = [
    "Build an API orchestration platform",
    "Create AI-assisted code reviewer",
    "Develop a hiring analytics engine",
    "Implement scalable queue processing service",
]

RESUME_API_BASE = os.getenv("RESUME_API_BASE", "https://mcptools1.unysite.com/resume-api").rstrip("/")
RESUME_API_LLM_SERVICE = os.getenv("RESUME_API_LLM_SERVICE", "OPENAI")


def _seed_from_filename(filename: str) -> int:
    digest = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:8]
    return int(digest, 16)


def parse_resume(file_path: str, filename: str) -> dict[str, str]:
    seed = _seed_from_filename(filename)
    rng = random.Random(seed)
    base_name = Path(filename).stem.replace("_", " ").replace("-", " ").title()
    phone = f"9{rng.randint(100000000, 999999999)}"
    email = f"{Path(filename).stem.lower()}@example.com"
    skills = ", ".join(rng.sample(["python", "backend", "ml", "sql", "fastapi", "docker"], 3))
    return {"name": base_name or "Unknown Candidate", "email": email, "phone": phone, "skills": skills}


def screen_candidate(skills: str) -> dict[str, str | float]:
    lowered = skills.lower()
    score = 65.0
    if "python" in lowered:
        score += 10
    if "fastapi" in lowered or "backend" in lowered:
        score += 8
    if "ml" in lowered:
        score += 7
    score = min(score, 95.0)
    tag = "Strong Fit" if score >= 80 else "Moderate Fit"
    problem = PROBLEMS[int(score) % len(PROBLEMS)]
    return {"fit_tag": tag, "fit_score": score, "recommended_problem": problem}


def _first_non_empty(*values: object, default: str = "") -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


async def screen_resume_api(file_path: str, filename: str) -> dict[str, object]:
    """Call external resume screening API and return normalized fields."""
    with open(file_path, "rb") as fh:
        files = {"file": (filename, fh, "application/pdf")}
        params = {"llm_service": RESUME_API_LLM_SERVICE}
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(f"{RESUME_API_BASE}/screen-resume", files=files, params=params)
            response.raise_for_status()
            payload = response.json() if response.content else {}
            print("SCREEN API RESPONSE:", payload)

    details = payload.get("candidate_details") or payload.get("candidate") or payload.get("details") or payload
    scores = payload.get("scores") or payload.get("category_scores") or {}
    total_score = payload.get("total_score") or payload.get("score") or payload.get("final_score")
    fit_score = _coerce_float(total_score, default=0.0)
    if fit_score <= 0 and isinstance(scores, dict):
        fit_score = _coerce_float(sum(_coerce_float(v) for v in scores.values()), default=0.0)
    fit_tag = "Strong Fit" if fit_score >= 70 else "Moderate Fit"
    recommendation = _first_non_empty(
        payload.get("recommendation"),
        payload.get("result"),
        payload.get("verdict"),
        default=fit_tag,
    )
    name = _first_non_empty(
        payload.get("candidate_name"),
        details.get("name") if isinstance(details, dict) else None,
        default="",
    )
    email = _first_non_empty(details.get("email") if isinstance(details, dict) else None, default="")
    phone = _first_non_empty(details.get("phone") if isinstance(details, dict) else None, default="")

    raw_skills = payload.get("skills") or (details.get("skills") if isinstance(details, dict) else None)
    if isinstance(raw_skills, list):
        skills = ", ".join(raw_skills)
    elif isinstance(raw_skills, str):
        skills = raw_skills
    else:
        skills = "" 
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": skills,
        "fit_tag": recommendation,
        "fit_score": fit_score,
        "summary": _first_non_empty(payload.get("summary"), payload.get("notes"), default=""),
    }


async def assign_project_api(file_path: str, filename: str) -> str:
    """Call external project assignment API and return assigned project text."""
    with open(file_path, "rb") as fh:
        files = {"file": (filename, fh, "application/pdf")}
        params = {"llm_service": RESUME_API_LLM_SERVICE}
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(f"{RESUME_API_BASE}/assign-project", files=files, params=params)
            response.raise_for_status()
            payload = response.json() if response.content else {}
    assigned = payload.get("assigned_project")
    if isinstance(assigned, dict):
        return _first_non_empty(
            assigned.get("project_name"),
            assigned.get("project_type"),
            assigned.get("reason"),
            default="",
        )
    return _first_non_empty(
        assigned,
        payload.get("project"),
        payload.get("project_type"),
        payload.get("description"),
        default="",
    )


async def merge_excel_api(
    hr_file_bytes: bytes,
    hr_filename: str,
    screening_file_bytes: bytes,
    screening_filename: str,
) -> dict[str, object]:
    """Call external merge-excel API and return its JSON response."""
    hr_name = (hr_filename or "hr_input.xlsx").strip()
    if "." not in hr_name:
        hr_name = f"{hr_name}.xlsx"
    hr_ext = Path(hr_name).suffix.lower()
    hr_content_type = (
        "application/vnd.ms-excel"
        if hr_ext == ".xls"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    screening_name = (screening_filename or "screening_results_generated.xlsx").strip()
    if "." not in screening_name:
        screening_name = f"{screening_name}.xlsx"

    files = {
        "hr_file": (
            hr_name,
            hr_file_bytes,
            hr_content_type,
        ),
        "screening_file": (
            screening_name,
            screening_file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(f"{RESUME_API_BASE}/merge-excel", files=files)
        response.raise_for_status()
        if not response.content:
            return {"message": "Merge completed"}

        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            return response.json()

        # Some merge APIs return a binary Excel file directly; avoid decoding bytes as UTF-8 JSON.
        try:
            return response.json()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return {
                "message": "Merge completed and returned a file response.",
                "content_type": content_type or "application/octet-stream",
                "size_bytes": len(response.content),
            }
