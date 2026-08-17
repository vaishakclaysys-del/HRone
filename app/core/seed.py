from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import hash_password
from app.core.models import User


def seed_users(db: Session) -> None:
    if db.execute(select(User.id)).first():
        return
    users = [
        User(username="hr1",        full_name="HR One",         role="hr",         password_hash=hash_password("password")),
        User(username="admin1",     full_name="Admin One",      role="admin",       password_hash=hash_password("password")),
        User(username="senior1",    full_name="Senior Dev One", role="senior_dev",  password_hash=hash_password("password")),
        User(username="senior2",    full_name="Senior Dev Two", role="senior_dev",  password_hash=hash_password("password")),
        User(username="candidate1", full_name="Candidate One",  role="candidate",   password_hash=hash_password("password")),
    ]
    db.add_all(users)
    db.commit()