from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field


class Contact(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    portfolio: str = ""


class ExperienceSection(BaseModel):
    name: str = ""
    bullets: List[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    dates: str = ""
    bullets: List[str] = Field(default_factory=list)
    sections: List[ExperienceSection] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str = ""
    subtitle: str = ""
    bullets: List[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    school: str = ""
    degree: str = ""
    location: str = ""
    dates: str = ""
    details: str = ""


class ActivityItem(BaseModel):
    name: str = ""
    dates: str = ""


class TailoredResume(BaseModel):
    contact: Contact = Field(default_factory=Contact)
    target_title: str = ""
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    activities: List[ActivityItem] = Field(default_factory=list)
    # Optional flexible sections — included only when present in the candidate's resume
    achievements: List[str] = Field(default_factory=list)   # Awards, honors, scholarships
    languages: List[str] = Field(default_factory=list)      # Language proficiency
    publications: List[str] = Field(default_factory=list)   # Papers, patents, articles
    ats_keywords_used: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class JobPosting(BaseModel):
    url: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    text: str = ""
    keywords: List[str] = Field(default_factory=list)


class ProfileOverrides(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    portfolio: str = ""
    summary_override: str = ""
    target_roles: List[str] = Field(default_factory=list)
    extra_keywords: List[str] = Field(default_factory=list)
