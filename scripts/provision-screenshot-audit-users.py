#!/usr/bin/env python3
"""Provision dedicated production screenshot-audit users and set the GitHub secret.

This script is intentionally local-only. It prompts for an existing Accounting owner/admin
credential, generates random audit passwords in memory, creates or refreshes one audit user
per active human role, and streams the resulting credential matrix directly to GitHub CLI.
Passwords are never printed or written to disk.
"""

from __future__ import annotations

import argparse
import getpass
import json
import re
import secrets
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_BASE_URL = "https://hiddenoasis.app"
DEFAULT_REPO = "moraledacaryl-dev/accounting-program-online"
SECRET_NAME = "ACCOUNTING_SCREENSHOT_AUDIT_USERS_JSON"
SERVICE_ROLE_RE = re.compile(r"(?:^|_)(?:integration|service)(?:_|$)")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ScreenshotAudit/1.0"


class PreserveMethodRedirectHandler(HTTPRedirectHandler):
    """Follow redirects without silently turning authenticated mutations into GETs."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if code in {301, 302, 303, 307, 308} and req.get_method() not in {"GET", "HEAD"}:
            forwarded = dict(req.header_items())
            return Request(newurl, data=req.data, headers=forwarded, method=req.get_method())
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = build_opener(PreserveMethodRedirectHandler())


def open_request(request: Request):
    request.add_header("User-Agent", USER_AGENT)
    return OPENER.open(request, timeout=30)


def resolve_canonical_base_url(base_url: str) -> str:
    configured = base_url.rstrip("/")
    request = Request(f"{configured}/api/healthz", headers={"Accept": "application/json"}, method="GET")
    try:
        with open_request(request) as response:
            final = urlsplit(response.geturl())
            if not final.scheme or not final.netloc:
                raise RuntimeError("Health check resolved to an invalid URL.")
            if response.status >= 400:
                raise RuntimeError(f"Health check failed with HTTP {response.status}")
            return f"{final.scheme}://{final.netloc}"
    except HTTPError as exc:
        raise RuntimeError(f"Cannot resolve canonical Accounting host: health check returned HTTP {exc.code}") from None
    except URLError as exc:
        raise RuntimeError(f"Cannot reach {configured}: {exc.reason}") from None


def api_json(base_url: str, path: str, *, method: str = "GET", token: str | None = None, payload=None):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{base_url.rstrip('/')}{path}", data=body, headers=headers, method=method)
    try:
        with open_request(request) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except HTTPError as exc:
        detail = ""
        allow = exc.headers.get("Allow", "") if exc.headers else ""
        server = exc.headers.get("Server", "") if exc.headers else ""
        try:
            parsed = json.loads(exc.read().decode("utf-8"))
            detail = parsed.get("detail", "") if isinstance(parsed, dict) else ""
        except Exception:
            pass
        extras = []
        if detail:
            extras.append(str(detail))
        if allow:
            extras.append(f"Allow={allow}")
        if server:
            extras.append(f"Server={server}")
        suffix = f": {'; '.join(extras)}" if extras else ""
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}{suffix}") from None
    except URLError as exc:
        raise RuntimeError(f"Cannot reach {base_url}: {exc.reason}") from None


def canonical_username(role_code: str) -> str:
    safe = re.sub(r"[^a-z0-9_]+", "_", role_code.strip().lower()).strip("_")
    if not safe:
        raise RuntimeError(f"Role code cannot be converted to an audit username: {role_code!r}")
    return f"audit_{safe}"


def active_human_roles(base_url: str, token: str) -> list[dict]:
    roles = api_json(base_url, "/api/roles-permissions/roles?active_only=true", token=token)
    if not isinstance(roles, list) or not roles:
        raise RuntimeError("Active role endpoint returned no roles.")
    human = []
    for role in roles:
        code = str(role.get("code") or "").strip()
        if not code:
            raise RuntimeError("Active role endpoint returned a role without a canonical code.")
        if not SERVICE_ROLE_RE.search(code):
            human.append(role)
    if not human:
        raise RuntimeError("No active human roles were discovered.")
    return human


def provision(base_url: str, token: str, roles: list[dict]) -> tuple[dict, list[str]]:
    existing = api_json(base_url, "/api/auth/users", token=token)
    if not isinstance(existing, list):
        raise RuntimeError("User endpoint returned an invalid response.")
    by_username = {str(row.get("username")): row for row in existing if row.get("username")}

    usernames = [canonical_username(str(role["code"])) for role in roles]
    if len(usernames) != len(set(usernames)):
        raise RuntimeError("Two active role codes map to the same audit username; refusing to provision.")

    matrix: dict[str, dict[str, str]] = {}
    touched: list[str] = []
    for role in roles:
        code = str(role["code"]).strip()
        role_id = int(role["id"])
        username = canonical_username(code)
        password = secrets.token_urlsafe(32)
        payload = {
            "full_name": f"Screenshot Audit — {role.get('name') or code}",
            "role": code,
            "role_ids": [role_id],
            "is_active": True,
            "password": password,
        }
        current = by_username.get(username)
        if current:
            api_json(base_url, f"/api/auth/users/{int(current['id'])}", method="PUT", token=token, payload=payload)
            action = "refreshed"
        else:
            api_json(base_url, "/api/auth/users", method="POST", token=token, payload={"username": username, **payload})
            action = "created"
        matrix[code] = {"username": username, "password": password}
        touched.append(f"{code}: {username} ({action})")
    return matrix, touched


def set_github_secret(repo: str, matrix: dict) -> None:
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI `gh` is not installed or not on PATH.")
    secret = json.dumps(matrix, separators=(",", ":"))
    result = subprocess.run(
        ["gh", "secret", "set", SECRET_NAME, "-R", repo],
        input=secret,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to set GitHub secret: {result.stderr.strip() or 'gh returned an error'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    args = parser.parse_args()

    print("This will create/refresh dedicated audit users in Accounting and rotate their audit-only passwords.")
    print("Passwords remain in memory and are sent directly to the GitHub Actions secret; they are never displayed.")
    base_url = resolve_canonical_base_url(args.base_url)
    print(f"Accounting API origin: {base_url}")
    username = input("Existing Accounting owner/admin username: ").strip()
    password = getpass.getpass("Existing Accounting owner/admin password: ")
    if not username or not password:
        raise RuntimeError("Username and password are required.")

    login = api_json(base_url, "/api/auth/login", method="POST", payload={"username": username, "password": password})
    token = str((login or {}).get("access_token") or "")
    if not token:
        raise RuntimeError("Login succeeded without returning an access token.")

    me = api_json(base_url, "/api/auth/me", token=token)
    permissions = set((me or {}).get("permissions") or [])
    role = str((me or {}).get("role") or "")
    if role not in {"owner", "admin"} and "users.manage" not in permissions:
        raise RuntimeError("The supplied account does not have users.manage permission.")

    roles = active_human_roles(base_url, token)
    print("Active human roles: " + ", ".join(str(role["code"]) for role in roles))
    matrix, touched = provision(base_url, token, roles)
    set_github_secret(args.repo, matrix)

    print(f"\n{SECRET_NAME} was set successfully for {args.repo}.")
    print("Audit accounts:")
    for line in touched:
        print(f"  - {line}")
    print("No audit password was printed or written to disk.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
