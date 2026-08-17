from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "sqlite:///./data/hr_mvp.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:  
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=30000;")
    cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
def _migrate_drop_phone_unique() -> None:
    """Drop the unique index on candidates.phone if it still exists (one-time migration for existing DBs)."""
    from sqlalchemy import text

    with engine.connect() as conn:
        indexes = conn.execute(text("PRAGMA index_list('candidates')")).fetchall()
        has_unique_phone = any(
            row[2] == 1 and row[1] in ("ix_candidates_phone", "uq_candidates_phone")
            for row in indexes
        )
        if not has_unique_phone:
            return

        columns = conn.execute(text("PRAGMA table_info('candidates')")).fetchall()
        source_has_flow = any(row[1] == "flow" for row in columns)
        flow_select = "flow" if source_has_flow else "NULL AS flow"

        conn.execute(text("""
            CREATE TABLE candidates_new (
                id INTEGER PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                email VARCHAR(150),
                phone VARCHAR(30),
                skills TEXT,
                stage INTEGER DEFAULT 1,
                status VARCHAR(30) DEFAULT 'new',
                flow VARCHAR(30),
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        conn.execute(text(
            f"INSERT INTO candidates_new "
            f"SELECT id, name, email, phone, skills, stage, status, {flow_select}, created_at, updated_at "
            f"FROM candidates"
        ))
        conn.execute(text("DROP TABLE candidates"))
        conn.execute(text("ALTER TABLE candidates_new RENAME TO candidates"))
        conn.execute(text("CREATE INDEX ix_candidates_name ON candidates (name)"))
        conn.execute(text("CREATE INDEX ix_candidates_phone ON candidates (phone)"))
        conn.execute(text("CREATE INDEX ix_candidates_stage ON candidates (stage)"))
        conn.execute(text("CREATE INDEX ix_candidates_status ON candidates (status)"))
        conn.commit()
        
def _migrate_add_flow_column() -> None:
    """Add candidates.flow if missing (one-time migration for existing DBs)."""
    from sqlalchemy import text
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info('candidates')")).fetchall()
        has_flow = any(row[1] == "flow" for row in columns)
        if has_flow:
            return
        conn.execute(text("ALTER TABLE candidates ADD COLUMN flow VARCHAR(30)"))
        conn.commit()
