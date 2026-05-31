"""Wire models for auth/admin/referrals (camelCase to match the frontend)."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class LoginInput(BaseModel):
    username: str
    password: str


class RegisterInput(BaseModel):
    ref: str              # referral code (a user's referral_code or an org's reg_code)
    username: str
    password: str
    email: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str
    orgId: Optional[str] = None   # Clerk organization id (string)
    referredBy: Optional[int] = None
    referralCode: str
    blocked: bool = False
    createdAt: str


class SetRoleInput(BaseModel):
    role: str  # "admin" | "user" (never "superuser")


class OrgAnalytics(BaseModel):
    scope: str                 # "org" | "platform"
    orgName: Optional[str] = None
    users: int
    blockedUsers: int
    totalSubmissions: int
    accepted: int
    invalid: int
    inReview: int
    duplicate: int = 0
    totalPoints: int


class UserStat(BaseModel):
    userId: int
    username: str
    total: int
    accepted: int
    invalid: int
    inReview: int
    duplicate: int
    points: int


class TokenResponse(BaseModel):
    token: str
    user: UserOut


class OrgOut(BaseModel):
    id: str                              # Clerk organization id
    name: str
    createdAt: Optional[str] = None
    emailSent: Optional[bool] = None      # whether Clerk dispatched the admin invite


class CreateOrgInput(BaseModel):
    name: str
    adminEmail: Optional[str] = None


class RefInfo(BaseModel):
    """What the register page shows for a referral/registration code."""
    valid: bool
    role: Optional[str] = None
    orgName: Optional[str] = None
    inviter: Optional[str] = None


class ReviewItem(BaseModel):
    id: int
    userId: str
    imageUrl: str
    platform: Optional[str] = None
    fileName: Optional[str] = None
    status: str
    createdAt: str
    # decoded from analysis_json for the reviewer:
    verified: Optional[bool] = None
    confidence: Optional[float] = None
    needsReview: Optional[bool] = None
    profile: Optional[Any] = None
    reasoning: Optional[str] = None


class ReviewQueue(BaseModel):
    items: List[ReviewItem]
    total: int
    page: int
    limit: int
