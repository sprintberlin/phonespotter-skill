"""Data models for PhoneSpotter."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class ContactInput(BaseModel):
    first_name: Optional[str] = Field(None, description="First name of the contact")
    last_name: Optional[str] = Field(None, description="Last name of the contact")
    company: Optional[str] = Field(None, description="Company name")
    email: Optional[str] = Field(None, description="Business email address")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile or company URL")
    designation: Optional[str] = Field(None, description="Job title or function")
    country: Optional[str] = Field("DE", description="ISO country code (default: DE)")
    current_phone: Optional[str] = Field(None, description="Existing phone number if known")
    current_mobile: Optional[str] = Field(None, description="Existing mobile number if known")

    @property
    def full_name(self) -> str:
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts).strip()

class PhoneCandidate(BaseModel):
    raw_number: str
    e164_number: Optional[str] = None
    phone_type: Literal["direct", "mobile", "company_hq", "unknown"] = "unknown"
    source: str
    confidence: float = 0.0
    notes: Optional[str] = None

class EnrichmentResult(BaseModel):
    status: Literal["found", "partial", "not_found", "error"]
    direct_phone: Optional[str] = None
    mobile_phone: Optional[str] = None
    company_phone: Optional[str] = None
    best_phone: Optional[str] = None
    best_phone_type: Optional[str] = None
    confidence: float = 0.0
    providers_checked: List[str] = Field(default_factory=list)
    successful_provider: Optional[str] = None
    candidates: List[PhoneCandidate] = Field(default_factory=list)
    evaluation_summary: Optional[str] = None
    error: Optional[str] = None
