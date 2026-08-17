from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    skills: Mapped[str] = mapped_column(Text, default="") 
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(150), nullable=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=True, index=True)
    skills: Mapped[str] = mapped_column(Text, default="")
    flow: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)  # ai_hackathon_flow | ai_interview_flow
    stage: Mapped[int] = mapped_column(Integer, default=1, index=True)
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    department: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    screening: Mapped[CandidateScreening | None] = relationship(back_populates="candidate", uselist=False)
    decision: Mapped[CandidateDecision | None] = relationship(back_populates="candidate", uselist=False)
    submission: Mapped[Submission | None] = relationship(back_populates="candidate", uselist=False)
    interviews: Mapped[list[Interview]] = relationship(back_populates="candidate")


class ResumeUpload(Base):
    __tablename__ = "resume_uploads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CandidateScreening(Base):
    __tablename__ = "candidate_screening"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), unique=True, nullable=False)
    fit_tag: Mapped[str] = mapped_column(String(100), nullable=False)
    fit_score: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_problem: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    candidate: Mapped[Candidate] = relationship(back_populates="screening")


class CandidateDecision(Base):
    __tablename__ = "candidate_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), unique=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # accept/reject
    notes: Mapped[str] = mapped_column(Text, default="")
    acted_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    acted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    candidate: Mapped[Candidate] = relationship(back_populates="decision")


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), unique=True, nullable=False)
    github_link: Mapped[str] = mapped_column(String(255), nullable=False)
    video_link: Mapped[str] = mapped_column(String(255), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    candidate: Mapped[Candidate] = relationship(back_populates="submission")
    reviews: Mapped[list[SubmissionReview]] = relationship(back_populates="submission")


class SubmissionReview(Base):
    __tablename__ = "submission_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    creativity: Mapped[int] = mapped_column(Integer, nullable=False)
    technical_execution: Mapped[int] = mapped_column(Integer, nullable=False)
    feasibility: Mapped[int] = mapped_column(Integer, nullable=False)
    problem_fit_demo: Mapped[int] = mapped_column(Integer, nullable=False)
    weighted_total: Mapped[float] = mapped_column(Float, nullable=False)
    comments: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("submission_id", "reviewer_id", name="uq_submission_reviewer"),)
    submission: Mapped[Submission] = relationship(back_populates="reviews")


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    interviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    scheduled_at: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="scheduled")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    candidate: Mapped[Candidate] = relationship(back_populates="interviews")
    scores: Mapped[list[InterviewScore]] = relationship(back_populates="interview")


# Parent interview score record. Category and field breakdowns are stored in child
# tables and link back here by InterviewScore.id via interview_score_id.
class InterviewScore(Base):
    __tablename__ = "interview_scores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), nullable=False)
    interviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    role_assessed: Mapped[str]    # stores Q4 "Role Candidate is Assessed for"
    recommendation: Mapped[str]   # stores Q37 "Overall Recommendation"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("interview_id", "interviewer_id", name="uq_interview_reviewer"),)
    interview: Mapped[Interview] = relationship(back_populates="scores")
    interviewer: Mapped[User] = relationship()


class AssessmentCategoryScore(Base):
    __tablename__ = "assessment_category_scores"
    # Link to InterviewScore.id; child rows belong to a single interview score record.
    interview_score_id: Mapped[int] = mapped_column(
        ForeignKey("interview_scores.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    category_title: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)


class AssessmentFieldScore(Base):
    __tablename__ = "assessment_field_scores"
    # Link to InterviewScore.id; child rows belong to a single interview score record.
    interview_score_id: Mapped[int] = mapped_column(
        ForeignKey("interview_scores.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[str] = mapped_column(String(50), nullable=False, primary_key=True)
    field_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    field_label: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    max_value: Mapped[float] = mapped_column(Float, nullable=False)


class CandidateProgress(Base):
    __tablename__ = "candidate_progress"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="")
    acted_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)