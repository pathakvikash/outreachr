from typing import List

from pydantic import BaseModel, Field

try:
    from pydantic import field_validator
except ImportError:
    from pydantic import validator as field_validator


class ProfileSummary(BaseModel):
    skills: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    bio: str = ""


class ApplicationKit(BaseModel):
    cold_dm: str
    cover_letter: str


class RecruiterCandidate(BaseModel):
    name: str
    title: str
    linkedin_url: str
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("linkedin_url")
    def linkedin_url_must_be_http(cls, value: str) -> str:
        value = str(value).strip()
        if not value.startswith(("https://", "http://")):
            raise ValueError("linkedin_url must be an absolute URL")
        return value


class ResearchCandidates(BaseModel):
    candidates: List[RecruiterCandidate] = Field(default_factory=list)


class RankedRecruiter(BaseModel):
    recruiter_name: str
    title: str = ""
    linkedin_url: str
    reason_for_ranking: str
    score: int = Field(ge=0, le=100)

    @field_validator("linkedin_url")
    def linkedin_url_must_be_http(cls, value: str) -> str:
        value = str(value).strip()
        if not value.startswith(("https://", "http://")):
            raise ValueError("linkedin_url must be an absolute URL")
        return value


class RankedRecruiters(BaseModel):
    recruiters: List[RankedRecruiter] = Field(default_factory=list)


class OutreachItem(BaseModel):
    recruiter_name: str
    linkedin_url: str
    reason_for_ranking: str
    draft_message: str

    @field_validator("linkedin_url")
    def linkedin_url_must_be_http(cls, value: str) -> str:
        value = str(value).strip()
        if not value.startswith(("https://", "http://")):
            raise ValueError("linkedin_url must be an absolute URL")
        return value

    @field_validator("draft_message")
    def message_under_75_words(cls, value: str) -> str:
        if len(value.split()) > 75:
            raise ValueError("draft_message must be 75 words or fewer")
        return value


class OutreachResult(BaseModel):
    recruiters: List[OutreachItem] = Field(default_factory=list)
