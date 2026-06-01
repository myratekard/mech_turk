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
    loginCount: int = 0
    justLoggedIn: bool = False   # transient: set by clerk_sync on a fresh session
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
    unsupported: int = 0
    totalPoints: int
    settledPoints: int = 0
    unsettledPoints: int = 0


class UserStat(BaseModel):
    userId: int
    userKey: str = ""   # raw submissions user_id — unique per row (userId may be 0 for non-numeric ids)
    username: str
    total: int
    accepted: int
    invalid: int
    inReview: int
    duplicate: int
    unsupported: int = 0
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


# ------------------------------------------------------------------- invoices
class InvoiceOut(BaseModel):
    id: int
    orgId: str
    orgName: Optional[str] = None
    status: str                  # pending | settled
    submissionCount: int
    totalPoints: int
    rate: float
    amount: float
    currency: str
    createdBy: Optional[str] = None
    createdAt: str
    settledBy: Optional[str] = None
    settledAt: Optional[str] = None
    receiptAmount: Optional[float] = None      # amount read from the payment receipt
    receiptImageUrl: Optional[str] = None      # the receipt screenshot, for the org admin to view


class InvoiceLineItem(BaseModel):
    id: int
    userId: str
    username: Optional[str] = None
    platform: Optional[str] = None
    handle: Optional[str] = None
    status: str
    points: int
    createdAt: str


class InvoicePayee(BaseModel):
    """Per-user payment breakdown within an invoice (who gets paid, how much)."""
    userId: str
    username: Optional[str] = None
    email: Optional[str] = None
    submissionCount: int
    points: int
    amount: float


class InvoiceDetail(InvoiceOut):
    items: List[InvoiceLineItem] = []
    payees: List[InvoicePayee] = []


class SettleInvoiceInput(BaseModel):
    objectPath: str   # uploaded bank-receipt screenshot, verified before settling


class OutstandingSummary(BaseModel):
    orgId: str
    count: int
    points: int
    rate: float
    amount: float
    currency: str


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
    africanDescent: Optional[bool] = None   # informational only


class ReviewQueue(BaseModel):
    items: List[ReviewItem]
    total: int
    page: int
    limit: int
