from __future__ import annotations

import asyncio
import time
import tempfile
import zipfile
import shutil
from pathlib import Path
from app.core.config import logger
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from fastapi import UploadFile
from app.core.db import engine
from app.integrations.mock_adapters import assign_project_api, screen_resume_api
from app.core.models import (
    Candidate,
    CandidateScreening,
    ResumeUpload,
    User,
)
from app.pipeline.utils import log_progress
from app.core.config import UPLOAD_DIR


# ---------------------------------------------------------
# Filename helper
# ---------------------------------------------------------

def extract_hr_id_from_filename(filename: str) -> int | None:
    """
    Return the 6-digit HR ID embedded as the first segment
    of the filename, e.g. '122778-Name.pdf' → 122778.
    """
    stem = Path(filename).stem
    prefix = stem.split("-")[0]
    if prefix.isdigit() and len(prefix) == 6:
        return int(prefix)
    return None


# ---------------------------------------------------------
# Single file processor
# ---------------------------------------------------------

async def process_resume_file(
    file_path: Path,
    filename: str,
    user: User,
    db: Session,
) -> None:

    start_time = time.perf_counter()
    logger.info(
        "resume.process.start filename=%s path=%s",
        filename, file_path,
    )

    screened            = await screen_resume_api(str(file_path), filename)
    recommended_problem = await assign_project_api(str(file_path), filename)

    phone_raw        = str(screened.get("phone") or "").strip() or None
    candidate_name   = str(screened.get("name")  or "").strip() or "Unknown"
    candidate_skills = str(screened.get("skills") or "").strip()
    fit_tag          = str(screened.get("fit_tag") or "").strip() or "Needs Further Evaluation"
    fit_score        = float(screened.get("fit_score") or 0.0)

    hr_id = extract_hr_id_from_filename(filename)

    for attempt in range(3):
        try:
            if hr_id is not None:
                candidate = db.get(Candidate, hr_id)

                if candidate is not None:
                    candidate.name   = candidate_name
                    candidate.phone  = phone_raw
                    candidate.email  = screened.get("email") or None
                    candidate.skills = candidate_skills
                    candidate.status = "parsed"

                    if candidate.screening:
                        candidate.screening.fit_tag              = fit_tag
                        candidate.screening.fit_score            = fit_score
                        candidate.screening.recommended_problem  = recommended_problem
                    else:
                        db.add(CandidateScreening(
                            candidate_id        = candidate.id,
                            fit_tag             = fit_tag,
                            fit_score           = fit_score,
                            recommended_problem = recommended_problem,
                        ))
                else:
                    candidate = Candidate(
                        id     = hr_id,
                        name   = candidate_name,
                        email  = screened.get("email") or None,
                        phone  = phone_raw,
                        skills = candidate_skills,
                        stage  = 1,
                        status = "parsed",
                    )
                    db.add(candidate)
                    db.flush()
                    db.add(CandidateScreening(
                        candidate_id        = candidate.id,
                        fit_tag             = fit_tag,
                        fit_score           = fit_score,
                        recommended_problem = recommended_problem,
                    ))
            else:
                candidate = Candidate(
                    name   = candidate_name,
                    email  = screened.get("email") or None,
                    phone  = phone_raw,
                    skills = candidate_skills,
                    stage  = 1,
                    status = "parsed",
                )
                db.add(candidate)
                db.flush()
                db.add(CandidateScreening(
                    candidate_id        = candidate.id,
                    fit_tag             = fit_tag,
                    fit_score           = fit_score,
                    recommended_problem = recommended_problem,
                ))

            db.add(ResumeUpload(
                candidate_id = candidate.id,
                file_name    = filename,
                file_path    = str(file_path),
                uploaded_by  = user.id,
            ))

            log_progress(
                db, candidate.id, 1,
                "resume_processed",
                "Resume parsed and screened via ResumeAPI",
                user.id,
            )

            db.commit()

            elapsed = time.perf_counter() - start_time
            logger.info(
                "resume.process.success filename=%s candidate_id=%s "
                "fit_score=%s elapsed_sec=%.2f",
                filename, candidate.id, fit_score, elapsed,
            )
            return

        except OperationalError:
            db.rollback()
            logger.warning(
                "resume.process.db_locked filename=%s attempt=%s",
                filename, attempt + 1,
            )
            if attempt == 2:
                logger.error(
                    "resume.process.failed filename=%s "
                    "reason=db_locked_retries_exhausted",
                    filename,
                )
                return
            await asyncio.sleep(0.4 * (attempt + 1))


# ---------------------------------------------------------
# Batch processor (background task)
# ---------------------------------------------------------

async def process_resume_batch(
    file_jobs: list[tuple[str, str]],
    user_id: int,
) -> None:
    """Process uploaded resume files outside the request/response cycle."""

    with Session(engine) as db:
        user = db.get(User, user_id)

        if not user:
            logger.error(
                "resume.batch.failed reason=user_not_found user_id=%s",
                user_id,
            )
            return

        for file_path, filename in file_jobs:
            try:
                await process_resume_file(
                    Path(file_path), filename, user, db,
                )
            except Exception as exc:
                logger.exception(
                    "resume.batch.file_failed filename=%s path=%s error=%s",
                    filename, file_path, exc,
                )

async def save_uploaded_resumes(
    resumes: list[UploadFile],
) -> list[tuple[str, str]]:
    """
    Persist uploaded resume files to UPLOAD_DIR.
 
    Accepts individual .pdf files and .zip archives of .pdf files.
    Zips are extracted to a temp dir, every .pdf found inside is
    copied into UPLOAD_DIR, and the temp dir is cleaned up.
 
    Returns a list of (saved_path, original_filename) tuples ready
    to be queued for background processing.
    """
    queued_jobs: list[tuple[str, str]] = []
 
    for resume in resumes:
 
        if not resume.filename:
            continue
 
        lower_name = resume.filename.lower()
 
        if lower_name.endswith(".pdf"):
            destination = UPLOAD_DIR / resume.filename
            destination.write_bytes(await resume.read())
            queued_jobs.append((str(destination), resume.filename))
            continue
 
        if lower_name.endswith(".zip"):
            zip_start = time.perf_counter()
 
            zip_destination = UPLOAD_DIR / resume.filename
            zip_destination.write_bytes(await resume.read())
 
            temp_dir = tempfile.mkdtemp(prefix="hr_zip_")
 
            try:
                with zipfile.ZipFile(zip_destination, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
 
                extracted_pdf_count = 0
 
                for extracted in Path(temp_dir).rglob("*"):
                    if (
                        extracted.is_file()
                        and extracted.name.lower().endswith(".pdf")
                    ):
                        destination = UPLOAD_DIR / extracted.name
                        destination.write_bytes(extracted.read_bytes())
                        queued_jobs.append((str(destination), extracted.name))
                        extracted_pdf_count += 1
 
                logger.info(
                    "bulk_upload.zip_processed "
                    "zip=%s pdf_count=%s elapsed_sec=%.2f",
                    resume.filename,
                    extracted_pdf_count,
                    time.perf_counter() - zip_start,
                )
 
            except zipfile.BadZipFile:
                logger.warning(
                    "bulk_upload.bad_zip zip=%s",
                    resume.filename,
                )
                continue
 
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
 
        else:
            logger.info(
                "bulk_upload.unsupported_file name=%s",
                resume.filename,
            )
 
    return queued_jobs