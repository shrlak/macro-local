"""Google OAuth (loopback + PKCE), Gmail API and Calendar API using only the standard library.

The user supplies their own OAuth client (Desktop app type) so no shared secret ships with the app.
"""
import base64
import datetime as dt
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

import ics

# module-level so tests can point them at a fake server
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com"
SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/calendar"]


class GoogleError(Exception):
    def __init__(self, status, message):
        super().__init__(f"Google {status}: {message}")
        self.status, self.message = status, message


def _http(method, url, token=None, body=None, form=None):
    data, headers = None, {"Accept": "application/json"}
    if form is not None:
        data, headers["Content-Type"] = urllib.parse.urlencode(form).encode(), "application/x-www-form-urlencoded"
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers), timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read())
            if isinstance(err.get("error"), str):  # OAuth style: {"error": "invalid_grant", "error_description": "..."}
                msg = err["error"] + (": " + err["error_description"] if err.get("error_description") else "")
            else:
                msg = err["error"]["message"]
        except Exception:
            msg = e.reason
        raise GoogleError(e.code, msg)


# ------------------------------------------------------------------ OAuth
def new_pkce():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def auth_url(client_id, redirect, state, challenge):
    return AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": " ".join(SCOPES),
        "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256"})


def exchange_code(cfg, code, verifier, redirect):
    t = _http("POST", TOKEN_URL, form={
        "client_id": cfg["client_id"], "client_secret": cfg["client_secret"], "code": code,
        "code_verifier": verifier, "redirect_uri": redirect, "grant_type": "authorization_code"})
    if not t.get("refresh_token"):
        raise GoogleError(400, "No refresh token returned. Remove Macro Local at myaccount.google.com/permissions and connect again.")
    return {"refresh_token": t["refresh_token"], "access_token": t["access_token"], "expires_at": time.time() + t.get("expires_in", 3600)}


def access_token(cfg, save):
    """Return a valid access token, refreshing (and persisting via save(tokens)) when needed."""
    tok = cfg.get("tokens") or {}
    if not tok.get("refresh_token"):
        raise GoogleError(401, "Not connected to Google")
    if tok.get("access_token") and tok.get("expires_at", 0) - 60 > time.time():
        return tok["access_token"]
    try:
        t = _http("POST", TOKEN_URL, form={"client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
                                           "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"})
    except GoogleError as e:
        if "invalid_grant" in e.message:
            raise GoogleError(401, "Google access expired or was revoked (apps in 'Testing' mode expire after 7 days). Reconnect in Settings.")
        raise
    tok = {**tok, "access_token": t["access_token"], "expires_at": time.time() + t.get("expires_in", 3600)}
    save(tok)
    return tok["access_token"]


def revoke(token):
    try:
        _http("POST", REVOKE_URL, form={"token": token})
    except Exception:
        pass


# ------------------------------------------------------------------ Gmail
def gmail_profile(tok):
    return _http("GET", f"{API}/gmail/v1/users/me/profile", tok)


def gmail_ids(tok, labels, limit=50):
    q = urllib.parse.urlencode({"labelIds": labels, "maxResults": limit}, doseq=True)
    return [m["id"] for m in _http("GET", f"{API}/gmail/v1/users/me/messages?{q}", tok).get("messages", [])]


def gmail_get(tok, mid):
    """-> (raw RFC822 bytes, labelIds, threadId)"""
    m = _http("GET", f"{API}/gmail/v1/users/me/messages/{mid}?format=raw", tok)
    raw = m["raw"] + "=" * (-len(m["raw"]) % 4)
    return base64.urlsafe_b64decode(raw), m.get("labelIds", []), m.get("threadId", "")


def gmail_send(tok, raw, thread_id=""):
    body = {"raw": base64.urlsafe_b64encode(raw).decode()}
    if thread_id:
        body["threadId"] = thread_id
    return _http("POST", f"{API}/gmail/v1/users/me/messages/send", tok, body)


def gmail_mark_read(tok, mid):
    _http("POST", f"{API}/gmail/v1/users/me/messages/{mid}/modify", tok, {"removeLabelIds": ["UNREAD"]})


# ------------------------------------------------------------------ Calendar
def _utc(s):
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        return d.strftime("%Y-%m-%dT%H:%M")
    return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M") + "Z"


def _local_floating(s, tz):
    """UTC/offset time -> naive wall-clock time in tz, so recurring events keep their local hour across DST."""
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        return d.strftime("%Y-%m-%dT%H:%M")
    if ics.ZoneInfo and tz:
        try:
            return d.astimezone(ics.ZoneInfo(tz)).strftime("%Y-%m-%dT%H:%M")
        except Exception:
            pass
    return _utc(s)


def calendar_events(tok, time_min):
    """List primary-calendar events (recurring events as masters). time_min: 'YYYY-MM-DD'."""
    out, page = [], None
    while True:
        q = {"maxResults": 250, "singleEvents": "false", "timeMin": time_min + "T00:00:00Z"}
        if page:
            q["pageToken"] = page
        r = _http("GET", f"{API}/calendar/v3/calendars/primary/events?{urllib.parse.urlencode(q)}", tok)
        out += r.get("items", [])
        page = r.get("nextPageToken")
        if not page:
            return out


def event_from_google(ev, tz=""):
    """Google event -> dict for server.import_events, or None to skip (cancelled / single-instance overrides)."""
    if ev.get("status") == "cancelled" or ev.get("recurringEventId"):
        return None
    s, e = ev.get("start", {}), ev.get("end", {})
    rrule = next((r[6:] for r in ev.get("recurrence", []) if r.upper().startswith("RRULE:")), "")
    if "date" in s:
        start = s["date"]
        end = (dt.datetime.strptime(e.get("date", start), "%Y-%m-%d") - dt.timedelta(days=1)).strftime("%Y-%m-%d")
        end, allday = max(end, start), "yes"
    elif "dateTime" in s:
        conv = (lambda x: _local_floating(x, tz)) if rrule else _utc
        start, end, allday = conv(s["dateTime"]), conv(e.get("dateTime", s["dateTime"])), "no"
    else:
        return None
    return {"uid": "g:" + ev["id"], "gid": ev["id"], "title": ev.get("summary", "") or "(no title)",
            "body": ev.get("description", ""), "location": ev.get("location", ""),
            "start": start, "end": end, "allday": allday, "rrule": rrule}


def event_to_google(it, tz):
    """Event item -> Google event resource body."""
    d = it["data"]
    ev = {"summary": it["title"], "description": it.get("body", ""), "location": d.get("location", "")}
    if d.get("allday") == "yes":
        end = dt.datetime.strptime((d.get("end") or d["start"])[:10], "%Y-%m-%d") + dt.timedelta(days=1)
        ev["start"], ev["end"] = {"date": d["start"][:10]}, {"date": end.strftime("%Y-%m-%d")}
    else:
        def point(s):
            s = s if len(s) > 10 else s + "T09:00"
            return {"dateTime": s[:16] + ":00Z"} if s.endswith("Z") else {"dateTime": s[:16] + ":00", "timeZone": tz or "UTC"}
        ev["start"], ev["end"] = point(d["start"]), point(d.get("end") or d["start"])
    ev["recurrence"] = ["RRULE:" + d["rrule"]] if d.get("rrule") else []
    return ev


def calendar_upsert(tok, it, tz):
    body = event_to_google(it, tz)
    gid = it["data"].get("gid")
    if gid:
        return _http("PATCH", f"{API}/calendar/v3/calendars/primary/events/{urllib.parse.quote(gid)}", tok, body)
    return _http("POST", f"{API}/calendar/v3/calendars/primary/events", tok, body)


def calendar_delete(tok, gid):
    try:
        _http("DELETE", f"{API}/calendar/v3/calendars/primary/events/{urllib.parse.quote(gid)}", tok)
    except GoogleError as e:
        if e.status not in (404, 410):
            raise
