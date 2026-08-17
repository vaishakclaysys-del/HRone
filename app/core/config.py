import logging
from pathlib import Path
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "resumes"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
logger = logging.getLogger("hr_mvp")

HACKATHON_THRESHOLD = float(
    os.environ.get("HACKATHON_THRESHOLD", "")
)

INTERVIEW_THRESHOLD = float(
    os.environ.get("INTERVIEW_THRESHOLD", "")
)

MIN_REVIEWS_REQUIRED = int(
    os.environ.get("MIN_REVIEWS_REQUIRED", "")
)

SESSION_SECRET_KEY = os.environ.get(
    "SESSION_SECRET_KEY",
    "dev-secret-key",
)

PIPELINES = {
    "AI / ML": [
        "Telephonic (HR)",
        "Hackathon Submitted",
        "Interview Scheduled",
        "Interview Completed",
        "Offer",
    ],
    "Developer": [
        "Telephonic (HR)",
        "Interview",
        "Offer",
    ],
    "QA / Tester": [
        "Telephonic (HR)",
        "Interview",
        "Offer",
    ],
    "Project Manager": [
        "Telephonic (HR)",
        "Interview",
        "Offer",
    ],
    "Finance": [
        "Telephonic (HR)",
        "Interview",
        "Offer",
    ],
}