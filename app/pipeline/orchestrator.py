from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.models import Candidate

from app.pipeline.utils import (
    log_progress,
    update_candidate_status,
)
from app.core.config import (
    HACKATHON_THRESHOLD,
    INTERVIEW_THRESHOLD,
)
# ---------------------------------------------------------
# Pipeline configuration — owned by pipeline, not workflow
# ---------------------------------------------------------

FLOWS = {
    "ai_hackathon_flow": ["hackathon", "interview"],
    "ai_interview_flow": ["interview"],
}

THRESHOLDS = {
    "hackathon": HACKATHON_THRESHOLD,
    "interview": INTERVIEW_THRESHOLD,
}

# ---------------------------------------------------------
# Module registry — add new modules here
# ---------------------------------------------------------

def _get_module_map():

    from app.modules.hackathon import (
        core as hackathon_core,
    )

    from app.modules.hackathon import (
        ai_hackathon_service,
    )
    from app.modules.interview import (
        core as interview_core,
    )

    from app.modules.interview import (
        ai_interview_service,
    )

    # Interview uses calculate_final_score: by the time advance() is
    # called, all individual scores are saved and averaged by core.
    # We wrap it so the orchestrator sees the same calculate_score name.
    interview_score_calculator = type(
        "InterviewScoreCalculator",
        (),
        {"calculate_score": staticmethod(ai_interview_service.calculate_final_score)},
    )()

    return {
        "hackathon": (
            ai_hackathon_service,
            hackathon_core,
        ),
        "interview": (
            interview_score_calculator,
            interview_core,
        ),
    }

def _get_module(module_name: str):
    module_map = _get_module_map()
    if module_name not in module_map:
        raise ValueError(f"Unknown module: {module_name!r}")
    return module_map[module_name]


# ---------------------------------------------------------
# advance() — called by routes
# ---------------------------------------------------------

def advance(
    db: Session,
    candidate: Candidate,
    module_name: str,
    input_data: dict,
) -> dict:

    if not candidate.flow:
        raise ValueError("Candidate has no flow assigned")

    flow_modules = FLOWS.get(candidate.flow, [])
    if module_name not in flow_modules:
        raise ValueError(f"Module {module_name!r} not in flow {candidate.flow!r}")

    service_mod, workflow_mod = _get_module(module_name)

    # ── Step 1: save (skip if already saved by route) ──
    skip_save = input_data.pop("skip_save", False)
    if not skip_save:
        workflow_mod.save(db, candidate, input_data)

    # ── Step 2: score (use override if route pre-calculated avg) ──
    score = input_data.pop("score_override", None)
    if score is None:
        score = service_mod.calculate_score(**input_data)

    if score is None:
        db.commit()
        return {
            "candidate_id": candidate.id,
            "module":        module_name,
            "score":         None,
            "passed":        None,
            "status":        candidate.status,
            "stage":         candidate.stage,
        }

    # ── Step 3: pass/fail ──
    passed        = score >= _cutoff_for(module_name)
    current_index = flow_modules.index(module_name)
    next_index    = current_index + 1
    has_next      = next_index < len(flow_modules)

    actor = input_data.get("interviewer_id") or input_data.get("reviewer_id")

    # ── Step 4: failed ──
    if not passed:
        failed_status = "failed_stage4" if module_name == "hackathon" else "interview_failed"
        failed_stage  = _stage_for(module_name)
        update_candidate_status(db, candidate, failed_status, failed_stage)
        log_progress(
            db, candidate.id,
            failed_stage,
            f"{module_name}_failed",
            f"Score: {score} below cutoff {_cutoff_for(module_name)}",
            actor,
        )

    # ── Step 5: passed, next module exists ──
    elif has_next:
        next_module = flow_modules[next_index]
        next_status = _entry_status_for(next_module, candidate.flow)
        next_stage  = _stage_for(next_module)

        # hackathon → interview: stage 5 is the "passed stage4" landing point
        if module_name == "hackathon":
            update_candidate_status(db, candidate, "passed_stage4", stage=5)
            log_progress(
                db, candidate.id, 5,
                "hackathon_passed",
                f"Avg score: {score} — advancing to {next_module}",
                actor,
            )
        else:
            update_candidate_status(db, candidate, next_status, next_stage)
            log_progress(
                db, candidate.id, next_stage,
                f"{module_name}_passed",
                f"Score: {score} → advancing to {next_module}",
                actor,
            )

    # ── Step 6: last module passed — flow complete ──
    else:
        update_candidate_status(db, candidate, "interview_passed", stage=7)
        log_progress(
            db, candidate.id, 7,
            f"{module_name}_passed",
            f"Score: {score} — completed {candidate.flow}",
            actor,
        )

    db.commit()

    return {
        "candidate_id": candidate.id,
        "module":        module_name,
        "score":         score,
        "passed":        passed,
        "status":        candidate.status,
        "stage":         candidate.stage,
    }
# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _cutoff_for(module_name: str) -> float:
    if module_name not in THRESHOLDS:
        raise ValueError(f"No threshold defined for module: {module_name!r}")
    return THRESHOLDS[module_name]


def _stage_for(
    module_name: str,
) -> int:

    return {

        "hackathon": 4,

        "interview": 5,

    }.get(module_name, 0)


def _entry_status_for(
    module_name: str,
    flow: str,
) -> str:

    if module_name == "hackathon":

        return "accepted"

    if module_name == "interview":

        if flow == "ai_interview_flow":

            return "accepted"

        return "passed_stage4"

    return "accepted"


def is_eligible_for_interview(
    candidate: Candidate,
) -> bool:

    if candidate.flow == "ai_interview_flow":

        return candidate.status in (

            "accepted",

            "interview_scheduled",
        )

    return (
        candidate.status
        == "passed_stage4"
    )


def should_skip_reviews(
    candidate: Candidate,
) -> bool:

    return (
        candidate.flow
        == "ai_interview_flow"
    )

def on_hackathon_submitted(
    db: Session,
    candidate: Candidate,
    input_data: dict,
) -> None:

    candidate.stage  = 4
    candidate.status = "submitted"

    log_progress(
        db,
        candidate.id,
        4,
        "hackathon_submitted",
        f"Github: {input_data.get('github_link', '')}",
        None,
    )
    
def on_candidate_accepted(
    db: Session,
    candidate: Candidate,
) -> None:

    if (
        not candidate.flow
        or candidate.flow not in FLOWS
    ):
        return

    log_progress(
        db,
        candidate.id,
        3,
        "flow_assigned",
        f"Flow selected: {candidate.flow}",
        None,
    )
    