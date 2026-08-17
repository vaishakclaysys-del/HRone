from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_role, hash_password
from app.core.db import get_db
from app.core.models import User
from app.core.config import templates
from app.core.constants import SENIOR_DEV_SKILLS

router = APIRouter(tags=["Admin"])

@router.get(
    "/admin/users",
    name="admin_users",
    response_class=HTMLResponse,
)
def admin_users(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    users = list(
        db.scalars(
            select(User).order_by(User.id)
        )
    )

    return templates.TemplateResponse(
        request,
        "admin_users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "skill_options": SENIOR_DEV_SKILLS,
        },
    )


@router.post(
    "/admin/users",
    name="admin_users_add",
)
def admin_users_add(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    skills: list[str] = Form([]),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    existing = db.scalar(
        select(User).where(User.username == username)
    )

    users = list(
        db.scalars(
            select(User).order_by(User.id)
        )
    )

    if existing:
        return templates.TemplateResponse(
            request,
            "admin_users.html",
            {
                "request": request,
                "user": user,
                "users": users,
                "skill_options": SENIOR_DEV_SKILLS,
                "error": f"Username '{username}' already exists.",
            },
        )

    db.add(
        User(
            username=username,
            full_name=full_name,
            role=role,
            password_hash=hash_password(password),
            skills=", ".join(skills) if role == "senior_dev" else "",
        )
    )

    db.commit()

    users = list(
        db.scalars(
            select(User).order_by(User.id)
        )
    )

    return templates.TemplateResponse(
        request,
        "admin_users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "skill_options": SENIOR_DEV_SKILLS,
            "success": f"User '{username}' added successfully!",
        },
    )

