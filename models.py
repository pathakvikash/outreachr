import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class RecruiterOutreach(Base):
    __tablename__ = 'recruiter_outreach'

    id = Column(Integer, primary_key=True)
    company_name = Column(String, nullable=False)
    job_role = Column(String, nullable=False)
    recruiter_name = Column(String, nullable=False)
    linkedin_url = Column(String, nullable=False)
    reason_for_ranking = Column(Text, nullable=True) # JSON or text explanation
    draft_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "recruiter_name": self.recruiter_name,
            "linkedin_url": self.linkedin_url,
            "reason_for_ranking": self.reason_for_ranking,
            "draft_message": self.draft_message
        }

class UsageLog(Base):
    __tablename__ = 'usage_logs'

    id = Column(Integer, primary_key=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class UserProfile(Base):
    """
    Stores the user's resume content and AI-generated summary.
    We assume single-user mode for this MVP, so we might just fetch the first record.
    """
    __tablename__ = 'user_profiles'

    id = Column(Integer, primary_key=True)
    raw_text = Column(Text, nullable=True)     # Full text from PDF
    summary_json = Column(Text, nullable=True) # Structured summary (JSON string)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)



DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///recruiter_outreach.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
