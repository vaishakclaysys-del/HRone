from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
)
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
 
from app.core.db import get_db
from app.core.auth import require_role
from app.core.models import User
 
from app.services.candidates import process_hr_decision

router = APIRouter(
    tags=["Pipeline"],
)
 
@router.post(
    "/hr/candidate/{candidate_id}/decision",
    name="hr_decision",
)
def hr_decision(
    request: Request,
    candidate_id: int,
    decision: str = Form(...),
    notes: str = Form(""),
    flow: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("hr")),
):
    process_hr_decision(
        db=db,
        candidate_id=candidate_id,
        decision=decision,
        notes=notes,
        flow=flow,
        user=user,
    )

    return RedirectResponse(
        request.url_for(
            "hr_candidate_detail",
            candidate_id=candidate_id,
        ),
        status_code=303,
    )