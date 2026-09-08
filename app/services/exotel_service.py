import os
from urllib.parse import urljoin

import requests
from flask import current_app, has_request_context, request


def exotel_auth():
    return (
        current_app.config.get("EXOTEL_API_KEY"),
        current_app.config.get("EXOTEL_API_TOKEN"),
    )


def exotel_base():
    host = current_app.config.get("EXOTEL_SUBDOMAIN") or "api.in.exotel.com"
    sid = current_app.config.get("EXOTEL_SID")
    return f"https://{host}/v1/Accounts/{sid}"


def exotel_configured():
    cfg = current_app.config
    return bool(cfg.get("EXOTEL_API_KEY") and cfg.get("EXOTEL_API_TOKEN") and cfg.get("EXOTEL_SID"))


def resolve_public_base():
    """Prefer PUBLIC_BASE_URL; otherwise derive from the current inbound request (ngrok)."""
    configured = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if configured:
        return configured
    if has_request_context():
        # When Exotel/ngrok hits us, Host is already public
        host = request.headers.get("X-Forwarded-Host") or request.host
        proto = request.headers.get("X-Forwarded-Proto") or request.scheme or "https"
        if host and "127.0.0.1" not in host and "localhost" not in host:
            return f"{proto}://{host}".rstrip("/")
    return ""


def public_url(path):
    base = resolve_public_base()
    if not base:
        return path
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def download_recording(recording_url, dest_path):
    """Download Exotel recording using API key/token basic auth."""
    if not recording_url:
        return False

    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    resp = requests.get(
        recording_url,
        auth=exotel_auth(),
        timeout=60,
        stream=True,
    )
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return True


def verify_account():
    """Ping Exotel account API. Returns dict with ok/error/details."""
    if not exotel_configured():
        return {"ok": False, "error": "Exotel credentials incomplete"}
    try:
        r = requests.get(f"{exotel_base()}.json", auth=exotel_auth(), timeout=20)
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:200]}
        account = (r.json() or {}).get("Account") or {}
        return {
            "ok": True,
            "sid": account.get("Sid"),
            "status": account.get("Status"),
            "type": account.get("Type"),
            "kyc_status": account.get("KycStatus"),
            "friendly_name": account.get("FriendlyName"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def list_numbers():
    if not exotel_configured():
        return []
    try:
        r = requests.get(
            f"{exotel_base()}/IncomingPhoneNumbers.json",
            auth=exotel_auth(),
            timeout=20,
        )
        if r.status_code != 200:
            return []
        data = r.json() or {}
        item = data.get("IncomingPhoneNumber")
        if not item:
            return []
        if isinstance(item, list):
            return item
        return [item]
    except Exception:
        return []


def status_summary():
    cfg = current_app.config
    account = verify_account() if exotel_configured() else {"ok": False}
    numbers = list_numbers() if account.get("ok") else []
    phone_numbers = [n.get("PhoneNumber") for n in numbers if n.get("PhoneNumber")]
    return {
        "api_key_set": bool(cfg.get("EXOTEL_API_KEY")),
        "api_token_set": bool(cfg.get("EXOTEL_API_TOKEN")),
        "sid_set": bool(cfg.get("EXOTEL_SID")),
        "sid": cfg.get("EXOTEL_SID") or "",
        "subdomain": cfg.get("EXOTEL_SUBDOMAIN") or "api.in.exotel.com",
        "virtual_number": cfg.get("EXOTEL_VIRTUAL_NUMBER") or "",
        "exotel_numbers": phone_numbers,
        "public_base_url": cfg.get("PUBLIC_BASE_URL") or "",
        "resolved_public_base": resolve_public_base(),
        "account_ok": bool(account.get("ok")),
        "account_status": account.get("status"),
        "account_type": account.get("type"),
        "kyc_status": account.get("kyc_status"),
        "webhook_path": "/ivr/exotel/incoming",
        "ready_for_webhooks": bool(
            account.get("ok") and (cfg.get("PUBLIC_BASE_URL") or resolve_public_base())
        ),
        "kyc_warning": account.get("kyc_status") in ("rejected", "pending", None)
        and account.get("ok"),
    }
