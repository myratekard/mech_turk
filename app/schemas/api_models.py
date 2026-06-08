"""Pydantic models mirroring the frontend's OpenAPI contract (lib/api-spec/openapi.yaml).

Field names are intentionally camelCase to match the generated TypeScript client
exactly — these are the wire models, distinct from the engine's snake_case schemas.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel

SubmissionStatus = Literal[
    "in_review", "processed", "accepted", "invalid", "duplicate", "unsupported"
]


class HealthStatus(BaseModel):
    status: str


class Submission(BaseModel):
    id: int
    userId: str
    imageUrl: str
    objectPath: str
    fileName: Optional[str] = None
    platform: Optional[str] = None
    status: SubmissionStatus
    points: int
    disputed: bool = False
    dupKind: Optional[str] = None      # 'self' | 'regular' for duplicates
    settled: bool = False
    settledAt: Optional[str] = None
    settledVia: Optional[str] = None   # org name the settlement came through
    africanDescent: Optional[bool] = None  # derived bool (african->true, non_african->false)
    africanClass: Optional[str] = None     # african | non_african | generic | unclear
    acctHandle: Optional[str] = None       # social handle captured from the screenshot
    orgId: Optional[str] = None            # uploader's org at submission time
    orgName: Optional[str] = None
    username: Optional[str] = None         # uploader (populated in admin listing)
    createdAt: str
    updatedAt: str


class SubmissionInput(BaseModel):
    imageUrl: str
    objectPath: str
    fileName: Optional[str] = None
    platform: Optional[str] = None


class SubmissionList(BaseModel):
    submissions: List[Submission]
    total: int
    page: int
    limit: int


class PointsBreakdownEntry(BaseModel):
    key: str
    label: str
    count: int
    points: int


class DashboardSummary(BaseModel):
    totalPoints: int                 # gross lifetime points (breakdown reconciles to this)
    settledPoints: int = 0           # points already paid out via a settled invoice
    unsettledPoints: int = 0         # outstanding = totalPoints - settledPoints
    totalSubmissions: int
    accepted: int
    inReview: int
    processed: int
    invalid: int
    duplicate: int = 0
    unsupported: int = 0
    updatedToday: int
    pointsBreakdown: List[PointsBreakdownEntry] = []


class UploadUrlRequest(BaseModel):
    name: str
    size: int
    contentType: str


class UploadUrlResponse(BaseModel):
    uploadURL: str
    objectPath: str
    metadata: UploadUrlRequest


class ErrorEnvelope(BaseModel):
    error: str
