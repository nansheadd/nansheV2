from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, constr


SupportedLang = Literal['fr', 'en', 'nl']


class ReportContentIn(BaseModel):
    url: constr(strip_whitespace=True, min_length=3, max_length=500) = Field(..., description="Exact URL of the reported content")
    reason: constr(strip_whitespace=True, min_length=10, max_length=4000) = Field(..., description="Why the content is suspected to be illegal")
    name: Optional[constr(strip_whitespace=True, max_length=200)] = Field(None, description="Optional reporter name")
    email: EmailStr = Field(..., description="Reporter email for follow-up")
    good_faith: bool = Field(..., description="Whether the reporter confirms the good-faith declaration")
    lang: Optional[SupportedLang] = Field(None, description="UI locale to tailor the acknowledgement email")


class ReportContentOut(BaseModel):
    status: str = Field("accepted", description="Indicates the report has been recorded")
    message: str = Field(..., description="Localized acknowledgement message to surface in the UI")

