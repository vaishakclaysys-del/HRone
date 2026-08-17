# HR Hackathon MVP

Web app for an end-to-end hiring hackathon workflow: resume intake, HR screening, candidate submission, senior rubric reviews, interview scheduling, interview scoring, and a final timeline view. Built with **FastAPI**, **SQLite**, **SQLAlchemy**, and **Jinja2** templates.

## Features

- **Stage 1–2:** Bulk PDF/ZIP resume upload, parsing and screening (external resume API with local fallback), searchable candidate list, accept/reject with notes.
- **Stage 3:** Candidates submit GitHub/video links **without logging in**; matching uses phone number (flexible formatting: spaces, `+91`, dashes, etc.).
- **Stage 4:** Two **different** senior developers must submit rubric reviews; average weighted score must be ≥ **48** to pass (see `app/services/workflow.py`).
- **Stage 5:** HR sees **eligible**, **pending**, and **rejected** lists from review data; opens per-candidate score summary; schedules interviews only for cutoff-passed candidates.
- **Stage 6–7:** Seniors score interviews; HR/Admin view final pipeline and per-candidate progress timeline.

## Stack

| Layer | Technology |
| --- | --- |
| API / server | FastAPI, Uvicorn |
| Database | SQLite (`./hr_mvp.db`), SQLAlchemy 2.x |
| UI | Jinja2, static CSS |
| Auth | Session cookies (`starlette.middleware.sessions`), Passlib (PBKDF2) |

Roles: `hr`, `senior_dev`, `admin`, `candidate` (seeded `candidate1` is optional; real candidates use the public submit form).

## Requirements

- Python 3.10+ recommended  
- Dependencies: see [`requirements.txt`](requirements.txt)

## Local setup (Python venv)

From the project root:

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate             # Windows (cmd)
# .venv\Scripts\Activate.ps1         # Windows (PowerShell)
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. (Optional) Load sample candidates if the DB is empty:

```bash
python3 seed_data.py
```

Default HR/senior/admin users are created automatically on first app startup if no users exist yet.

## Run locally

With the venv **activated**:

```bash
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) (redirects to dashboard; unauthenticated users hitting protected routes are sent to login).

### Environment variables (resume API)

Defaults point at the bundled integration; override if needed:

```bash
export RESUME_API_BASE="https://mcptools1.unysite.com/resume-api"
export RESUME_API_LLM_SERVICE="OPENAI"
```

## Seeded accounts

| Username | Password | Role |
| --- | --- | --- |
| `hr1` | `password` | HR |
| `admin1` | `password` | Admin |
| `senior1` | `password` | Senior dev |
| `senior2` | `password` | Senior dev |
| `candidate1` | `password` | Test candidate (optional) |

Change these before any real deployment; session secret is also a dev default in `app/main.py`.

## Main routes

| Path | Who | Purpose |
| --- | --- | --- |
| `/login` | Public | Staff login; link to public submission |
| `/dashboard` | Logged-in | Hub |
| `/hr/upload` | HR | PDF/ZIP upload, optional Excel merge |
| `/hr/candidates` | HR, Admin | List, filter, open candidate, accept/reject |
| `/hr/candidate/{id}` | HR, Admin | Detail + decision |
| `/candidate/submit` | **Public** | Submit phone + repo/video (requires HR **accepted** status) |
| `/senior/reviews` | Senior | Queue of `submitted` candidates |
| `/senior/review/{id}` | Senior | Rubric form |
| `/hr/interviews` | HR | Interview lists + schedule form |
| `/hr/review-summary/{id}` | HR | Review scores + average + eligibility |
| `/senior/interviews` | Senior | Assigned interviews |
| `/senior/interview/{id}` | Senior | Interview score form |
| `/final` | HR, Admin | Candidates from stage ≥ 6 |
| `/final/{id}` | HR, Admin | Full timeline |

## Workflow notes

1. **Duplicate reviews:** Each senior can only store **one** review per submission (unique `submission_id` + `reviewer_id`). Two totals require **two different** senior accounts.
2. **Interview eligibility:** Scheduling requires `passed_stage4` (set when two reviews exist and average ≥ cutoff). Opening `/hr/interviews` or posting a schedule runs a safe sync so status matches review data.
3. **Phone matching:** Submission uses normalized digit matching so `9123456789` and `+91 91234 56789` align when they refer to the same local number.

## Project layout

```
app/
  main.py           # Routes and orchestration
  models.py         # SQLAlchemy models
  db.py             # Engine and session
  auth.py           # Passwords, session user, optional user
  phone_utils.py    # Phone normalization for submission
  services/workflow.py  # Rubric math, stage-4/6 finalization
  integrations/     # Resume API + mocks
templates/          # Jinja pages
static/             # CSS
data/resumes/       # Uploaded files (created at runtime)
tests/              # Pytest
```

## Tests

```bash
pytest -q
```

## License / hackathon use

This repository is structured as a hackathon MVP; harden auth, secrets, and validation before production use.

..
