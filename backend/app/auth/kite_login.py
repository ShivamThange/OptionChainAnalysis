"""Kite Connect access-token management with automated daily TOTP login.

Requires a *real* Kite Connect subscription (api_key + api_secret). This is not
a bypass — it drives Zerodha's standard login + 2FA to obtain a request_token,
then exchanges it via the official `generate_session`. The access token is valid
until ~06:00 next day and cached on disk so we log in at most once per day.

If credentials are missing, `ensure_access_token` raises — the caller keeps the
provider dormant and stays on NSE fallback.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pyotp

log = logging.getLogger("auth.kite")

_KITE_WEB = "https://kite.zerodha.com"


class KiteCredentialsMissing(RuntimeError):
    pass


def _load_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (ValueError, OSError):
        return None
    # tokens expire ~6am next day; treat anything dated today as valid.
    if data.get("date") == dt.date.today().isoformat() and data.get("access_token"):
        return data
    return None


def _save_cache(path: Path, access_token: str, public_token: str = "") -> None:
    path.write_text(json.dumps({
        "date": dt.date.today().isoformat(),
        "access_token": access_token,
        "public_token": public_token,
    }))


def _auto_request_token(api_key: str, user_id: str, password: str,
                        totp_secret: str) -> str:
    """Drive Zerodha web login + TOTP 2FA and capture the request_token."""
    with httpx.Client(timeout=15.0, follow_redirects=False) as c:
        # 1) password login -> request_id
        r = c.post(f"{_KITE_WEB}/api/login",
                   data={"user_id": user_id, "password": password})
        r.raise_for_status()
        request_id = r.json()["data"]["request_id"]

        # 2) TOTP 2FA
        otp = pyotp.TOTP(totp_secret).now()
        r = c.post(f"{_KITE_WEB}/api/twofa",
                   data={"user_id": user_id, "request_id": request_id,
                         "twofa_value": otp, "twofa_type": "totp"})
        r.raise_for_status()

        # 3) hit the Connect login endpoint; redirect carries request_token
        r = c.get("https://kite.trade/connect/login",
                  params={"api_key": api_key, "v": "3"})
        # follow the redirect chain manually to find request_token in a Location
        location = r.headers.get("location", "")
        for _ in range(5):
            qs = parse_qs(urlparse(location).query)
            if "request_token" in qs:
                return qs["request_token"][0]
            if not location:
                break
            r = c.get(location)
            location = r.headers.get("location", "")
    raise RuntimeError("Could not capture request_token from Kite login redirect")


def ensure_access_token(settings) -> str:
    """Return a valid Kite access token, logging in via TOTP if needed."""
    if not settings.kite_enabled:
        raise KiteCredentialsMissing("KITE_API_KEY / KITE_API_SECRET not set")

    cache_path = settings.token_cache_file
    cached = _load_cache(cache_path)
    if cached:
        log.info("Using cached Kite access token (%s)", cached["date"])
        return cached["access_token"]

    if not (settings.kite_user_id and settings.kite_password and settings.kite_totp_secret):
        raise KiteCredentialsMissing(
            "No cached token and KITE_USER_ID/PASSWORD/TOTP_SECRET not set for "
            "automated login. Provide them, or complete the manual login flow.")

    from kiteconnect import KiteConnect

    log.info("Performing automated Kite TOTP login for %s", settings.kite_user_id)
    request_token = _auto_request_token(
        settings.kite_api_key, settings.kite_user_id,
        settings.kite_password, settings.kite_totp_secret)

    kite = KiteConnect(api_key=settings.kite_api_key)
    session = kite.generate_session(request_token, api_secret=settings.kite_api_secret)
    access_token = session["access_token"]
    _save_cache(cache_path, access_token, session.get("public_token", ""))
    log.info("Kite login OK; token cached to %s", cache_path)
    return access_token
