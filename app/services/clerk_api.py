"""Minimal Clerk Backend API client (https://api.clerk.com/v1), stdlib only.

Used for the superuser-only org-creation flow and referral auto-join, since the
frontend's Clerk components can't create orgs when user-creation is disabled.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from app.core.config import settings

_BASE = "https://api.clerk.com/v1"


def _request(method: str, path: str, body: Optional[dict] = None) -> dict:
    if not settings.clerk_secret_key:
        raise RuntimeError("CLERK_SECRET_KEY not configured")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {settings.clerk_secret_key}",
            "Content-Type": "application/json",
            # Clerk's API is behind Cloudflare, which 403s urllib's default UA (error 1010).
            "User-Agent": "mech_turk/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"Clerk API {method} {path} -> {e.code}: {detail}")


def create_organization(name: str, created_by_clerk_id: str) -> dict:
    return _request("POST", "/organizations", {"name": name, "created_by": created_by_clerk_id})


def create_organization_invitation(org_id: str, email: str, role: str = "org:admin",
                                   inviter_user_id: Optional[str] = None,
                                   redirect_url: Optional[str] = None) -> dict:
    body = {"email_address": email, "role": role}
    if inviter_user_id:
        body["inviter_user_id"] = inviter_user_id
    if redirect_url:
        # Send invitees to OUR app's sign-up (which accepts the ticket) instead of
        # Clerk's hosted Account Portal.
        body["redirect_url"] = redirect_url
    return _request("POST", f"/organizations/{org_id}/invitations", body)


def create_application_invitation(email: str, redirect_url: Optional[str] = None) -> dict:
    """Application-level invitation (not org) — used for inviting platform turk admins."""
    body: dict = {"email_address": email, "notify": True, "ignore_existing": True}
    if redirect_url:
        body["redirect_url"] = redirect_url
    return _request("POST", "/invitations", body)


def add_member(org_id: str, clerk_user_id: str, role: str = "org:member") -> dict:
    return _request("POST", f"/organizations/{org_id}/memberships",
                    {"user_id": clerk_user_id, "role": role})


def update_member_role(org_id: str, clerk_user_id: str, role: str) -> dict:
    return _request("PATCH", f"/organizations/{org_id}/memberships/{clerk_user_id}",
                    {"role": role})


def list_members(org_id: str, limit: int = 100) -> list[dict]:
    res = _request("GET", f"/organizations/{org_id}/memberships?limit={limit}")
    # Clerk returns {data: [...], total_count} or a bare list depending on version.
    return res.get("data", res) if isinstance(res, dict) else res
