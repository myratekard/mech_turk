"""Referrals: a user's downline + minting their own user-invite link."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.api.routes.auth import to_user_out
from app.schemas.auth_models import UserOut
from app.services import auth_db

router = APIRouter(prefix="/me", tags=["referrals"])


@router.get("/referrals", response_model=list[UserOut])
def my_referrals(user: dict = Depends(get_current_user)):
    # A user's invite link is /register?ref=<their referral_code> (built client-side).
    return [to_user_out(u) for u in auth_db.list_referrals(user["id"])]
