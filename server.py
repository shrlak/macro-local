#!/usr/bin/env python3
"""Macro Local: a self-hosted workspace app (docs, tasks, chat, email, calendar, calls, CRM).

Standard library only (Python 3.9+). Run:  python3 server.py   (opens as a desktop-style app window)
"""
from datetime import date as dt_date, timedelta as dt_timedelta
import hashlib, json, os, re, shutil, socket, sqlite3, ssl, subprocess, sys, threading, time, uuid, webbrowser
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import caldav
import google
import ics
import mailer

FROZEN = getattr(sys, "frozen", False)
CODE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
STATIC = CODE_DIR / "static"
DATA_DIR = Path(os.environ.get("MACRO_HOME") or Path.home() / ".macro-local")
DATA_DIR.mkdir(parents=True, exist_ok=True)
REC_DIR = DATA_DIR / "recordings"
REC_DIR.mkdir(exist_ok=True)
DB_PATH = os.environ.get("MACRO_DB", str(DATA_DIR / "macro.db"))
HOST = os.environ.get("MACRO_HOST", "127.0.0.1")
PORT = int(os.environ.get("MACRO_PORT", "8787"))
TYPES = {"doc", "task", "contact", "company", "deal", "email", "event", "call"}
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
lock = threading.RLock()

db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS items(
  id TEXT PRIMARY KEY, type TEXT NOT NULL, title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '', data TEXT NOT NULL DEFAULT '{}', created REAL, updated REAL);
CREATE INDEX IF NOT EXISTS items_type ON items(type);
CREATE TABLE IF NOT EXISTS channels(id TEXT PRIMARY KEY, name TEXT UNIQUE, created REAL);
CREATE TABLE IF NOT EXISTS messages(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, channel TEXT, author TEXT,
  text TEXT, created REAL, task_id TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
""")
if not db.execute("SELECT 1 FROM channels").fetchone():
    for n in ("general", "random"):
        db.execute("INSERT INTO channels VALUES(?,?,?)", (uuid.uuid4().hex[:8], n, time.time()))
    db.commit()
try:
    os.chmod(DB_PATH, 0o600)  # the db holds mail credentials
except OSError:
    pass


def new_id():
    return uuid.uuid4().hex[:10]


def get_setting(key, default=None):
    r = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else default


def set_setting(key, value):
    db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, json.dumps(value)))
    db.commit()


def item_json(r):
    d = dict(r)
    d["data"] = json.loads(d["data"] or "{}")
    return d


def get_item(i):
    r = db.execute("SELECT * FROM items WHERE id=?", (i,)).fetchone()
    return item_json(r) if r else None


def create_item(type_, title="", body="", data=None, created=None):
    i, now = new_id(), time.time()
    db.execute("INSERT INTO items VALUES(?,?,?,?,?,?,?)",
               (i, type_, title, body, json.dumps(data or {}), created or now, now))
    db.commit()
    return get_item(i)


def resolve_links(body):
    out = []
    for name in LINK_RE.findall(body or ""):
        r = db.execute("SELECT id,type,title FROM items WHERE id=? OR lower(title)=lower(?) LIMIT 1",
                       (name.strip(), name.strip())).fetchone()
        out.append({"ref": name, "item": dict(r) if r else None})
    return out


def backlinks(it):
    q, args = "SELECT id,type,title FROM items WHERE id!=? AND (body LIKE ?", [it["id"], "%[[" + it["id"] + "]]%"]
    if it["title"]:
        q += " OR lower(body) LIKE lower(?)"
        args.append("%[[" + it["title"] + "]]%")
    return [dict(r) for r in db.execute(q + ")", args)]


def search(q):
    q = q.strip()
    if not q:
        return []
    pat = "%" + q.replace("%", "") + "%"
    res = [dict(r, kind="item") for r in db.execute(
        "SELECT id,type,title,substr(body,1,140) AS snippet FROM items "
        "WHERE title LIKE ? OR body LIKE ? OR data LIKE ? ORDER BY updated DESC LIMIT 40", (pat, pat, pat))]
    res += [dict(r, kind="message", type="chat") for r in db.execute(
        "SELECT id,channel,author,text AS title FROM messages WHERE text LIKE ? ORDER BY seq DESC LIMIT 20", (pat,))]
    return res


# ---------------------------------------------------------------- email
def mail_cfg():
    c = get_setting("email")
    return c if c and c.get("address") and c.get("password") else None


def google_cfg():
    """Google settings if the account is connected (OAuth done), else None."""
    with lock:
        g = get_setting("google", {})
    return g if g.get("tokens") and g.get("client_id") else None


def google_token(g):
    def save(tok):
        with lock:
            cur = get_setting("google", {})
            cur["tokens"] = tok
            set_setting("google", cur)
    return google.access_token(g, save)


sync_guard = threading.Lock()  # one Google sync at a time (post-sign-in sync vs. background sync)


def sync_gmail(g):
    with sync_guard:
        return _sync_gmail(g)


def _sync_gmail(g):
    """Pull recent INBOX/SENT messages through the Gmail API. Network I/O happens outside the db lock."""
    try:
        tok = google_token(g)
        inbox, sent = google.gmail_ids(tok, ["INBOX"]), google.gmail_ids(tok, ["SENT"])
        unread = set(google.gmail_ids(tok, ["INBOX", "UNREAD"]))
        with lock:
            known = {}
            for r in db.execute("SELECT id,data FROM items WHERE type='email'"):
                d = json.loads(r["data"])
                if d.get("gmail_id"):
                    known[d["gmail_id"]] = (r["id"], d)
        todo, seen = [], set()
        for folder, ids in (("inbox", inbox), ("sent", sent)):
            for mid in reversed(ids):  # oldest first
                if mid not in known and mid not in seen:
                    seen.add(mid)
                    todo.append((mid, folder))
        fetched = [(mid, folder, *google.gmail_get(tok, mid)) for mid, folder in todo]
    except Exception as e:
        return {"error": str(e), "new": 0}
    with lock:
        for mid, folder, raw, labels, thread in fetched:
            m = mailer.parse_message(raw)
            create_item("email", m["subject"], m["body"], {
                "from": m["from"], "to": m["to"], "cc": m["cc"], "date": m["date"], "folder": folder,
                "message_id": m["message_id"], "in_reply_to": m["in_reply_to"], "gmail_id": mid, "thread_id": thread,
                "attachments": ", ".join(m["attachments"]), "unread": "yes" if mid in unread and folder == "inbox" else "no"})
        for mid, (iid, d) in known.items():  # mirror read/unread changes made in Gmail
            want = "yes" if mid in unread else "no"
            if mid in inbox and d.get("folder") == "inbox" and d.get("unread") != want:
                db.execute("UPDATE items SET data=? WHERE id=?", (json.dumps({**d, "unread": want}), iid))
        db.commit()
        set_setting("email_state", {"address": g.get("email", ""), "synced": time.time()})
    return {"new": len(fetched)}


def sync_email():
    """Fetch new INBOX messages into email items. Network I/O happens outside the db lock."""
    g = google_cfg()
    if g and g.get("mail", True):
        return sync_gmail(g)
    with lock:
        cfg, state = mail_cfg(), get_setting("email_state", {})
    if not cfg:
        return {"error": "Email account not configured", "new": 0}
    last = state.get("last_uid", 0) if state.get("address") == cfg["address"] else 0
    try:
        msgs, newest = mailer.fetch_new(cfg, last)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "new": 0}
    n = 0
    with lock:
        for uid, m in msgs:
            if m["message_id"] and db.execute("SELECT 1 FROM items WHERE type='email' AND data LIKE ?",
                                              ("%" + json.dumps({"message_id": m["message_id"]})[1:-1] + "%",)).fetchone():
                continue
            create_item("email", m["subject"], m["body"], {
                "from": m["from"], "to": m["to"], "cc": m["cc"], "date": m["date"], "folder": "inbox",
                "message_id": m["message_id"], "in_reply_to": m["in_reply_to"],
                "attachments": ", ".join(m["attachments"]), "unread": "yes"})
            n += 1
        set_setting("email_state", {"address": cfg["address"], "last_uid": newest, "synced": time.time()})
    return {"new": n}


def send_email_google(g, b):
    try:
        with lock:
            ref = db.execute("SELECT data FROM items WHERE type='email' AND data LIKE ?",
                             ("%" + json.dumps({"message_id": b.get("in_reply_to", "")})[1:-1] + "%",)).fetchone() \
                if b.get("in_reply_to") else None
        thread = json.loads(ref["data"]).get("thread_id", "") if ref else ""
        cfg = {"address": g["email"], "name": g.get("name", "")}
        m = mailer.build_message(cfg, b["to"], b.get("subject", ""), b.get("body", ""), b.get("cc", ""), b.get("in_reply_to", ""))
        res = google.gmail_send(google_token(g), m.as_bytes(), thread)
    except Exception as e:
        return {"error": str(e)}, 502
    with lock:
        it = create_item("email", b.get("subject") or "(no subject)", b.get("body", ""), {
            "from": g["email"], "to": b["to"], "cc": b.get("cc", ""), "folder": "sent", "gmail_id": res.get("id", ""),
            "thread_id": res.get("threadId", ""), "date": time.strftime("%Y-%m-%dT%H:%M"),
            "message_id": m["Message-ID"], "unread": "no"})
    return it, 200


def send_email(b):
    g = google_cfg()
    if g and g.get("mail", True):
        return send_email_google(g, b) if b.get("to") else ({"error": "Recipient required"}, 400)
    with lock:
        cfg = mail_cfg()
    if not cfg:
        return {"error": "Email account not configured"}, 400
    if not b.get("to"):
        return {"error": "Recipient required"}, 400
    try:
        m = mailer.send(cfg, b["to"], b.get("subject", ""), b.get("body", ""), b.get("cc", ""), b.get("in_reply_to", ""))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}, 502
    with lock:
        it = create_item("email", b.get("subject") or "(no subject)", b.get("body", ""), {
            "from": cfg["address"], "to": b["to"], "cc": b.get("cc", ""), "folder": "sent",
            "date": time.strftime("%Y-%m-%dT%H:%M"), "message_id": m["Message-ID"], "unread": "no"})
    return it, 200


# ---------------------------------------------------------------- calendar
def sync_feeds():
    with lock:
        feeds = get_setting("feeds", [])
    total, errors = 0, []
    for f in feeds:
        url = re.sub(r"^webcal", "https", f["url"].strip())
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MacroLocal"}), timeout=30) as r:
                events = ics.parse_ics(r.read().decode("utf-8", "replace"))
        except Exception as e:
            errors.append(f"{f.get('name') or url}: {e}")
            continue
        total += import_events(events, feed=hashlib.md5(url.encode()).hexdigest()[:8], prune=True)
    return {"events": total, "errors": errors}


def import_events(events, feed="", prune=False):
    """Upsert parsed ICS events as event items (keyed by uid)."""
    with lock:
        seen = set()
        for e in events:
            uid = e["uid"]
            seen.add(uid)
            data = {k: e[k] for k in ("start", "end", "allday", "location", "rrule")}
            data.update(uid=uid, feed=feed)
            if e.get("gid"):
                data["gid"] = e["gid"]
            data.update(e.get("extra", {}))
            row = db.execute("SELECT id,data FROM items WHERE type='event' AND data LIKE ?",
                             ("%" + json.dumps({"uid": uid})[1:-1] + "%",)).fetchone()
            if row:
                db.execute("UPDATE items SET title=?,body=?,data=?,updated=? WHERE id=?",
                           (e["title"], e["body"], json.dumps({**json.loads(row["data"]), **data}), time.time(), row["id"]))
            else:
                create_item("event", e["title"], e["body"], data)
        if prune and feed:
            for r in db.execute("SELECT id,data FROM items WHERE type='event'").fetchall():
                d = json.loads(r["data"])
                if d.get("feed") == feed and d.get("uid") not in seen:
                    db.execute("DELETE FROM items WHERE id=?", (r["id"],))
        db.commit()
    return len(events)


def sync_google_calendar(g=None):
    with sync_guard:
        return _sync_google_calendar(g)


def _sync_google_calendar(g=None):
    """Pull the primary Google calendar (last 60 days onward) into event items."""
    g = g or google_cfg()
    if not g:
        return {"error": "Google not connected", "events": 0}
    tmin = (dt_date.today() - dt_timedelta(days=60)).isoformat()
    try:
        raw = google.calendar_events(google_token(g), tmin)
    except Exception as e:
        return {"error": str(e), "events": 0}
    evs = [x for x in (google.event_from_google(e, g.get("timezone", "")) for e in raw) if x]
    n = import_events(evs)
    present = {e["id"] for e in raw}
    with lock:  # events deleted in Google disappear here (recurring masters are kept)
        for r in db.execute("SELECT id,data FROM items WHERE type='event'").fetchall():
            d = json.loads(r["data"])
            if d.get("gid") and d["gid"] not in present and not d.get("rrule") and d.get("start", "")[:10] >= tmin:
                db.execute("DELETE FROM items WHERE id=?", (r["id"],))
        db.commit()
    return {"events": n}


push_lock, push_pending = threading.Lock(), {}


def queue_push(key, kind, payload):
    """Coalesce outbound Google writes (latest per key wins); the worker flushes them every second."""
    with push_lock:
        push_pending[key] = (kind, payload)


def caldav_cfg():
    with lock:
        c = get_setting("caldav", {})
    return c if c.get("url") and c.get("password") and c.get("calendars") else None


def caldav_client(c):
    return caldav.Client(c["url"], c["username"], c["password"])


def push_caldav(c, it, tz):
    """Create/update one event on the CalDAV server, preserving the server's other properties (alarms, attendees...)."""
    d = it["data"]
    cal = d.get("caldav_cal") or c.get("default")
    uid = d.get("uid") or uuid.uuid4().hex + "@macro-local"
    ev = {"id": it["id"], "title": it["title"], "body": it["body"], "data": {**d, "uid": uid}}
    raw = d.get("caldav_raw")
    text = ics.patch_ics(raw, ev, tz) if raw else ics.export_ics([ev], tz=tz)
    existing = d.get("caldav_href")
    href = existing or urllib.parse.urljoin(cal, urllib.parse.quote(uid, safe="@") + ".ics")
    etag = caldav_client(c).put(href, text, (d.get("caldav_etag") or "*") if existing else None)
    with lock:
        cur = get_item(it["id"])
        if cur:
            db.execute("UPDATE items SET data=? WHERE id=?", (json.dumps({
                **cur["data"], "uid": uid, "caldav_href": href, "caldav_etag": etag, "caldav_cal": cal,
                "caldav_raw": text[:60000]}), it["id"]))
            db.commit()


def event_provider(d, g, c):
    """Which account an event belongs to. New local events follow the 'new events go to' setting."""
    if d.get("gid"):
        return "google" if g and g.get("calendar", True) else None
    if d.get("caldav_href"):
        return "caldav" if c else None
    if d.get("feed") or d.get("uid"):
        return None  # imported from an .ics file/feed: not ours to write
    with lock:
        target = get_setting("calendar_target", "auto")
    gok = bool(g and g.get("calendar", True))
    if target == "google" or (target == "auto" and gok):
        return "google" if gok else None
    if target in ("caldav", "auto"):
        return "caldav" if c and c.get("default") else None
    return None


def process_pushes():
    with push_lock:
        jobs = list(push_pending.values())
        push_pending.clear()
    g, c = google_cfg(), caldav_cfg()
    tz = (g or {}).get("timezone") or (c or {}).get("timezone", "")
    for kind, payload in jobs:
        err_key = "caldav_error" if kind.startswith("caldav") else "google_error"
        try:
            if kind == "event_upsert":
                with lock:
                    it = get_item(payload)
                if not it:
                    continue
                prov = event_provider(it["data"], g, c)
                if prov == "google" and g:
                    res = google.calendar_upsert(google_token(g), it, g.get("timezone", ""))
                    with lock:
                        cur = get_item(payload)
                        if cur:
                            db.execute("UPDATE items SET data=? WHERE id=?",
                                       (json.dumps({**cur["data"], "gid": res["id"], "uid": "g:" + res["id"]}), payload))
                            db.commit()
                elif prov == "caldav" and c:
                    err_key = "caldav_error"
                    push_caldav(c, it, tz)
            elif kind == "event_delete" and g and g.get("calendar", True):
                google.calendar_delete(google_token(g), payload)
            elif kind == "caldav_delete" and c:
                caldav_client(c).delete(payload["href"], payload.get("etag") or None)
            elif kind == "mail_read" and g and g.get("mail", True):
                google.gmail_mark_read(google_token(g), payload)
        except Exception as e:
            with lock:
                set_setting(err_key, {"error": str(e), "at": time.time()})


def sync_caldav(c=None):
    with sync_guard:
        return _sync_caldav(c)


def _sync_caldav(c=None):
    """Pull every selected CalDAV calendar (last 60 days onward) into event items."""
    c = c or caldav_cfg()
    if not c:
        return {"error": "CalDAV calendar not connected", "events": 0}
    sel = [x for x in c["calendars"] if x.get("selected")]
    tmin = (dt_date.today() - dt_timedelta(days=60)).isoformat()
    cl, evs, present = caldav_client(c), [], set()
    try:
        for cal in sel:
            for r in cl.fetch(cal["href"], tmin):
                present.add(r["href"])
                for e in ics.parse_ics(r["ics"]):
                    e["extra"] = {"caldav_href": r["href"], "caldav_etag": r["etag"], "caldav_cal": cal["href"],
                                  "caldav_raw": r["ics"][:60000]}
                    evs.append(e)
    except Exception as e:
        with lock:
            set_setting("caldav_error", {"error": str(e), "at": time.time()})
        return {"error": str(e), "events": 0}
    n = import_events(evs)
    cals = {x["href"] for x in sel}
    with lock:  # events deleted on the server disappear here (recurring ones are kept)
        for r in db.execute("SELECT id,data FROM items WHERE type='event'").fetchall():
            d = json.loads(r["data"])
            if d.get("caldav_cal") in cals and d.get("caldav_href") not in present and not d.get("rrule") \
                    and d.get("start", "")[:10] >= tmin:
                db.execute("DELETE FROM items WHERE id=?", (r["id"],))
        db.commit()
        set_setting("caldav_error", {})
    return {"events": n}


def push_worker():
    while True:
        time.sleep(1)
        try:
            process_pushes()
        except Exception:
            pass


oauth_pending = {}


def calendar_window(a, b):
    out = []
    for r in db.execute("SELECT * FROM items WHERE type='event'"):
        it = item_json(r)
        d = it["data"]
        if not d.get("start"):
            continue
        try:
            for s, e in ics.occurrences(d["start"], d.get("end"), d.get("rrule"), a, b):
                out.append({"id": it["id"], "title": it["title"] or "(untitled)", "start": s, "end": e,
                            "allday": d.get("allday") == "yes", "location": d.get("location", "")})
        except Exception:
            continue
    return sorted(out, key=lambda x: x["start"])


# ---------------------------------------------------------------- calls (WebRTC signaling)
rooms, rooms_lock = {}, threading.Lock()


def room_state(room):
    r = rooms.setdefault(room, {"peers": {}, "inbox": {}})
    now = time.time()
    for pid in [p for p, v in r["peers"].items() if now - v["seen"] > 15]:
        r["peers"].pop(pid, None)
        r["inbox"].pop(pid, None)
    return r


def background():
    n = 0
    while True:
        time.sleep(60)
        n += 1
        try:
            g = google_cfg()
            if n % 5 == 0 and (mail_cfg() or (g and g.get("mail", True))):
                sync_email()
            if n % 10 == 0 and g and g.get("calendar", True):
                sync_google_calendar(g)
            if n % 10 == 5 and caldav_cfg():
                sync_caldav()
            if n % 30 == 0 and get_setting("feeds"):
                sync_feeds()
        except Exception:
            pass


MIME = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
        ".png": "image/png", ".webmanifest": "application/manifest+json", ".webm": "audio/webm"}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send(self, obj, code=200):
        self.raw(json.dumps(obj).encode(), "application/json", code)

    def raw(self, data, ctype, code=200, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def body(self, raw=False):
        n = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(n) if n else b""
        return data if raw else (json.loads(data) if data else {})

    def parts(self):
        u = urlparse(self.path)
        return [unquote(x) for x in u.path.strip("/").split("/")], parse_qs(u.query)

    def do_GET(self):
        p, q = self.parts()
        if p == ["oauth", "google", "callback"]:
            return self.google_callback(q)
        if p == ["api", "ping"]:  # the page pings this so a browser-mode server can quit after its tab closes
            globals()["last_ping"] = time.time()
            return self.send({"ok": True})
        if p[0] == "recordings" and len(p) == 2:
            return self.recording(p[1])
        if p[0] != "api":
            return self.static(self.path.split("?")[0])
        if p[1:] == ["calendar", "export.ics"]:
            with lock:
                evs = [item_json(r) for r in db.execute("SELECT * FROM items WHERE type='event'")]
            return self.raw(ics.export_ics(evs).encode(), "text/calendar",
                            extra={"Content-Disposition": 'attachment; filename="macro-local.ics"'})
        if p[1] == "rooms" and len(p) == 4 and p[3] == "poll":
            with rooms_lock:
                r = room_state(p[2])
                pid = q.get("id", [""])[0]
                if pid in r["peers"]:
                    r["peers"][pid]["seen"] = time.time()
                msgs = r["inbox"].get(pid, [])
                if pid in r["inbox"]:
                    r["inbox"][pid] = []
                peers = [{"id": k, "name": v["name"]} for k, v in r["peers"].items()]
            return self.send({"msgs": msgs, "peers": peers})
        with lock:
            if p[1:] == ["items"]:
                t = q.get("type", [None])[0]
                rows = db.execute("SELECT * FROM items WHERE type=? ORDER BY updated DESC", (t,)) \
                    if t else db.execute("SELECT * FROM items ORDER BY updated DESC")
                return self.send([item_json(r) for r in rows])
            if p[1] == "items" and len(p) == 3:
                it = get_item(p[2])
                if not it:
                    return self.send({"error": "not found"}, 404)
                it["links"], it["backlinks"] = resolve_links(it["body"]), backlinks(it)
                return self.send(it)
            if p[1:] == ["search"]:
                return self.send(search(q.get("q", [""])[0]))
            if p[1:] == ["channels"]:
                return self.send([dict(r) for r in db.execute("SELECT * FROM channels ORDER BY name")])
            if p[1] == "channels" and len(p) == 4 and p[3] == "messages":
                since = int(q.get("since", ["0"])[0])
                return self.send([dict(r) for r in db.execute(
                    "SELECT * FROM messages WHERE channel=? AND seq>? ORDER BY seq", (p[2], since))])
            if p[1:] == ["calendar"]:
                return self.send(calendar_window(q["start"][0], q["end"][0]))
            if p[1:] == ["settings"]:
                email = dict(get_setting("email", {}))
                email["has_password"] = bool(email.pop("password", ""))
                g = get_setting("google", {})
                cd = get_setting("caldav", {})
                return self.send({"email": email, "feeds": get_setting("feeds", []),
                                  "email_state": get_setting("email_state", {}),
                                  "calendar_target": get_setting("calendar_target", "auto"),
                                  "caldav": {"connected": bool(cd.get("password")), "url": cd.get("url", ""),
                                             "username": cd.get("username", ""), "calendars": cd.get("calendars", []),
                                             "default": cd.get("default", ""),
                                             "error": get_setting("caldav_error", {}).get("error", "")},
                                  "google": {"client_id": g.get("client_id", ""), "has_secret": bool(g.get("client_secret")),
                                             "connected": bool(g.get("tokens")), "email": g.get("email", ""),
                                             "mail": g.get("mail", True), "calendar": g.get("calendar", True),
                                             "error": get_setting("google_error", {}).get("error", "")}})
        self.send({"error": "not found"}, 404)

    def do_POST(self):
        p, q = self.parts()
        if p[1] == "calls" and len(p) == 4 and p[3] == "recording":  # raw audio upload
            data = self.body(raw=True)
            name = re.sub(r"\W", "", p[2]) + ".webm"
            (REC_DIR / name).write_bytes(data)
            with lock:
                it = get_item(p[2])
                if it:
                    d = {**it["data"], "recording": name}
                    db.execute("UPDATE items SET data=?,updated=? WHERE id=?", (json.dumps(d), time.time(), p[2]))
                    db.commit()
            return self.send({"ok": True, "file": name})
        try:
            b = self.body()
        except Exception:
            return self.send({"error": "bad json"}, 400)
        # network-bound actions run outside the db lock
        if p[1:] == ["email", "sync"]:
            return self.send(sync_email())
        if p[1:] == ["email", "send"]:
            obj, code = send_email(b)
            return self.send(obj, code)
        if p[1:] == ["calendar", "sync"]:
            return self.send(sync_feeds())
        if p[0] == "api" and p[1] == "google":
            return self.send(*self.google_api(p[2], b))
        if p[0] == "api" and p[1] == "caldav":
            return self.send(*self.caldav_api(p[2], b))
        if p[1] == "rooms":
            with rooms_lock:
                r = room_state(p[2])
                if p[3] == "join":
                    pid = new_id()
                    others = [{"id": k, "name": v["name"]} for k, v in r["peers"].items()]
                    r["peers"][pid] = {"name": (b.get("name") or "guest")[:40], "seen": time.time()}
                    r["inbox"][pid] = []
                    return self.send({"id": pid, "peers": others})
                if p[3] == "leave":
                    r["peers"].pop(b.get("id"), None)
                    r["inbox"].pop(b.get("id"), None)
                    return self.send({"ok": True})
                if p[3] == "signal":
                    if b.get("to") in r["inbox"]:
                        r["inbox"][b["to"]].append({"from": b.get("from"), "type": b.get("type"), "data": b.get("data")})
                    return self.send({"ok": True})
        with lock:
            if p[1:] == ["items"]:
                if b.get("type") not in TYPES:
                    return self.send({"error": "bad type"}, 400)
                return self.send(create_item(b["type"], b.get("title", ""), b.get("body", ""), b.get("data")))
            if p[1:] == ["settings"]:
                if "email" in b:
                    e = dict(b["email"])
                    old = get_setting("email", {})
                    if not e.get("password"):
                        e["password"] = old.get("password", "")
                    e.pop("has_password", None)
                    set_setting("email", e)
                if "feeds" in b:
                    set_setting("feeds", [f for f in b["feeds"] if f.get("url")])
                return self.send({"ok": True})
            if p[1:] == ["calendar", "import"]:
                evs = ics.parse_ics(b.get("ics", ""))
            else:
                evs = None
            if p[1:] == ["channels"]:
                name = re.sub(r"[^a-z0-9-]", "-", b.get("name", "").lower()).strip("-")
                if not name:
                    return self.send({"error": "bad name"}, 400)
                db.execute("INSERT OR IGNORE INTO channels VALUES(?,?,?)", (new_id(), name, time.time()))
                db.commit()
                return self.send({"ok": True})
            if p[1] == "channels" and len(p) == 4:
                text = (b.get("text") or "").strip()
                if not text:
                    return self.send({"error": "empty"}, 400)
                db.execute("INSERT INTO messages(id,channel,author,text,created) VALUES(?,?,?,?,?)",
                           (new_id(), p[2], b.get("author") or "me", text, time.time()))
                db.commit()
                return self.send({"ok": True})
            if p[1] == "messages" and len(p) == 4 and p[3] == "to-task":
                m = db.execute("SELECT * FROM messages WHERE id=?", (p[2],)).fetchone()
                if not m:
                    return self.send({"error": "not found"}, 404)
                t = create_item("task", m["text"][:80], f"From chat #{m['channel']} by {m['author']}:\n\n{m['text']}",
                                {"status": "todo"})
                db.execute("UPDATE messages SET task_id=? WHERE id=?", (t["id"], p[2]))
                db.commit()
                return self.send(t)
            if p[1] == "items" and len(p) == 4 and p[3] in ("to-contact", "to-task"):
                e = get_item(p[2])
                if not e or e["type"] != "email":
                    return self.send({"error": "not an email"}, 400)
                if p[3] == "to-task":
                    return self.send(create_item("task", e["title"], f"From email [[{e['id']}]]", {"status": "todo"}))
                addr = e["data"].get("from", "")
                m = re.search(r"([\w.+-]+@([\w-]+\.[\w.-]+))", addr)
                name = re.sub(r"<.*?>", "", addr).strip().strip('"') or (m.group(1) if m else "Unknown")
                return self.send(create_item("contact", name, f"Created from email [[{e['id']}]]",
                                             {"email": m.group(1) if m else "", "company": m.group(2) if m else ""}))
        if evs is not None:
            return self.send({"imported": import_events(evs)})
        self.send({"error": "not found"}, 404)

    def do_PUT(self):
        p, _ = self.parts()
        b = self.body()
        with lock:
            it = get_item(p[2]) if len(p) == 3 and p[1] == "items" else None
            if not it:
                return self.send({"error": "not found"}, 404)
            data = {**it["data"], **b.get("data", {})}
            db.execute("UPDATE items SET title=?,body=?,data=?,updated=? WHERE id=?",
                       (b.get("title", it["title"]), b.get("body", it["body"]), json.dumps(data), time.time(), it["id"]))
            db.commit()
            new = get_item(it["id"])
        if new["type"] == "event":
            queue_push(new["id"], "event_upsert", new["id"])
        if new["type"] == "email" and new["data"].get("gmail_id") and it["data"].get("unread") == "yes" and new["data"].get("unread") == "no":
            queue_push("r" + new["data"]["gmail_id"], "mail_read", new["data"]["gmail_id"])
        return self.send(new)

    def do_DELETE(self):
        p, _ = self.parts()
        with lock:
            if len(p) == 3 and p[1] == "items":
                old = get_item(p[2])
                db.execute("DELETE FROM items WHERE id=?", (p[2],))
                db.commit()
                if old and old["type"] == "event" and old["data"].get("gid"):
                    queue_push("d" + old["data"]["gid"], "event_delete", old["data"]["gid"])
                if old and old["type"] == "event" and old["data"].get("caldav_href"):
                    queue_push("d" + old["data"]["caldav_href"], "caldav_delete",
                               {"href": old["data"]["caldav_href"], "etag": old["data"].get("caldav_etag", "")})
                return self.send({"ok": True})
        self.send({"error": "not found"}, 404)

    def caldav_api(self, action, b):
        if action == "connect":
            with lock:
                old = get_setting("caldav", {})
            url, user = (b.get("url") or "").strip(), (b.get("username") or "").strip()
            pw = b.get("password") or old.get("password", "")
            if not (url and user and pw):
                return {"error": "Enter the server URL, username and password"}, 400
            try:
                cals = caldav.Client(url, user, pw).discover()
            except Exception as e:
                return {"error": str(e)}, 400
            prev = {x["href"]: x for x in old.get("calendars", [])} if old.get("url") == url else {}
            cals = [{**x, "selected": prev.get(x["href"], {}).get("selected", True)} for x in cals]
            with lock:
                set_setting("caldav", {"url": url, "username": user, "password": pw, "calendars": cals,
                                       "default": old.get("default") if old.get("default") in [x["href"] for x in cals] else cals[0]["href"],
                                       "timezone": b.get("timezone") or old.get("timezone", "")})
            return {"calendars": cals}, 200
        if action == "calendars":
            with lock:
                c = get_setting("caldav", {})
                sel = set(b.get("selected", []))
                for x in c.get("calendars", []):
                    x["selected"] = x["href"] in sel
                c["default"] = b.get("default") if b.get("default") in sel else next(iter(sel), "")
                set_setting("caldav", c)
                for r in db.execute("SELECT id,data FROM items WHERE type='event'").fetchall():  # drop events of deselected calendars
                    d = json.loads(r["data"])
                    if d.get("caldav_cal") and d["caldav_cal"] not in sel:
                        db.execute("DELETE FROM items WHERE id=?", (r["id"],))
                db.commit()
            return {"ok": True}, 200
        if action == "sync":
            return sync_caldav(), 200
        if action == "disconnect":
            with lock:
                set_setting("caldav", {})
                set_setting("caldav_error", {})
            return {"ok": True}, 200
        if action == "target":
            with lock:
                set_setting("calendar_target", b.get("target") if b.get("target") in ("auto", "google", "caldav", "local") else "auto")
            return {"ok": True}, 200
        return {"error": "not found"}, 404

    def google_api(self, action, b):
        if action == "config":
            with lock:
                g = get_setting("google", {})
                cid = (b.get("client_id") or "").strip()
                if cid and cid != g.get("client_id"):
                    g.pop("tokens", None)  # a different OAuth client invalidates old tokens
                    g.pop("email", None)
                g.update(client_id=cid or g.get("client_id", ""))
                if b.get("client_secret"):
                    g["client_secret"] = b["client_secret"].strip()
                for k in ("mail", "calendar"):
                    if k in b:
                        g[k] = bool(b[k])
                if b.get("timezone"):
                    g["timezone"] = b["timezone"]
                set_setting("google", g)
            return {"ok": True}, 200
        if action == "connect":
            with lock:
                g = get_setting("google", {})
                if b.get("timezone"):
                    g["timezone"] = b["timezone"]
                    set_setting("google", g)
            if not g.get("client_id") or not g.get("client_secret"):
                return {"error": "Enter your Google OAuth client ID and secret first"}, 400
            verifier, challenge = google.new_pkce()
            state = uuid.uuid4().hex
            scheme = "https" if isinstance(self.connection, ssl.SSLSocket) else "http"
            redirect = f"{scheme}://{self.headers.get('Host', f'localhost:{PORT}')}/oauth/google/callback"
            for k in [k for k, v in oauth_pending.items() if time.time() - v["t"] > 900]:
                oauth_pending.pop(k)
            oauth_pending[state] = {"verifier": verifier, "redirect": redirect, "t": time.time()}
            return {"url": google.auth_url(g["client_id"], redirect, state, challenge), "redirect": redirect}, 200
        if action == "disconnect":
            with lock:
                g = get_setting("google", {})
                tok = (g.pop("tokens", None) or {})
                g.pop("email", None)
                set_setting("google", g)
                set_setting("google_error", {})
            if tok.get("refresh_token"):
                google.revoke(tok["refresh_token"])
            return {"ok": True}, 200
        if action == "sync":
            m, c = sync_email(), sync_google_calendar()
            return {"mail": m, "calendar": c, "error": m.get("error") or c.get("error", "")}, 200
        return {"error": "not found"}, 404

    def google_callback(self, q):
        def page(title, msg, ok):
            html = (f"<!doctype html><meta charset=utf-8><title>{title}</title><body style='font:16px system-ui;max-width:480px;margin:15vh auto;padding:0 20px'>"
                    f"<h2>{'✅' if ok else '⚠️'} {title}</h2><p>{msg}</p></body>")
            self.raw(html.encode(), "text/html; charset=utf-8")
        from html import escape
        state, code, err = (q.get(k, [""])[0] for k in ("state", "code", "error"))
        pend = oauth_pending.pop(state, None)
        if err or not code or not pend:
            return page("Google sign-in failed", escape(err or "This sign-in link is invalid or expired. Start again from Settings."), False)
        with lock:
            g = get_setting("google", {})
        try:
            tokens = google.exchange_code(g, code, pend["verifier"], pend["redirect"])
            addr = google.gmail_profile(tokens["access_token"])["emailAddress"]
        except Exception as e:
            return page("Google sign-in failed", escape(str(e)), False)
        with lock:
            g = get_setting("google", {})
            g.update(tokens=tokens, email=addr)
            g.setdefault("mail", True)
            g.setdefault("calendar", True)
            set_setting("google", g)
            set_setting("google_error", {})
        threading.Thread(target=lambda: (sync_email(), sync_google_calendar()), daemon=True).start()
        page("Connected", f"Signed in as <b>{escape(addr)}</b>. Mail and calendar are syncing. You can close this tab and return to Macro Local.", True)

    def recording(self, name):
        f = (REC_DIR / re.sub(r"[^\w.]", "", name))
        if not f.is_file():
            return self.send({"error": "not found"}, 404)
        data, size = f.read_bytes(), f.stat().st_size
        rng = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if rng and (rng.group(1) or rng.group(2)):
            a = int(rng.group(1) or 0)
            z = int(rng.group(2)) if rng.group(2) else size - 1
            return self.raw(data[a:z + 1], "audio/webm", 206, {"Content-Range": f"bytes {a}-{z}/{size}", "Accept-Ranges": "bytes"})
        self.raw(data, "audio/webm", extra={"Accept-Ranges": "bytes"})

    def static(self, path):
        f = (STATIC / (path.lstrip("/") or "index.html")).resolve()
        if (STATIC.resolve() not in f.parents) or not f.is_file():
            f = STATIC / "index.html"
        self.raw(f.read_bytes(), MIME.get(f.suffix, "application/octet-stream") + ("; charset=utf-8" if f.suffix in (".html", ".js", ".css") else ""))


# ---------------------------------------------------------------- app window
def find_chromium():
    names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge", "brave-browser"]
    for n in names:
        if shutil.which(n):
            return shutil.which(n)
    cands = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            cands += [f"{base}/Google/Chrome/Application/chrome.exe", f"{base}/Microsoft/Edge/Application/msedge.exe",
                      f"{base}/BraveSoftware/Brave-Browser/Application/brave.exe"]
    return next((c for c in cands if Path(c).exists()), None)


def port_open(host, port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def open_window(url):
    """Open the UI as a standalone app window. Returns the browser Popen, or None."""
    exe = find_chromium()
    if exe:
        try:
            return subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={DATA_DIR / 'window-profile'}",
                                     "--no-first-run", "--window-size=1280,820"])
        except OSError:
            pass
    webbrowser.open(url)
    return None


def main():
    args = sys.argv[1:]
    arg = lambda n: args[args.index(n) + 1] if n in args else None
    scheme = "https" if arg("--cert") else "http"
    url = f"{scheme}://localhost:{PORT}"
    if port_open("127.0.0.1", PORT):  # already running: just open another window
        print("Macro Local is already running; opening a window.")
        open_window(url)
        return
    srv = ThreadingHTTPServer((HOST, PORT), H)
    srv.daemon_threads = True
    if arg("--cert"):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(arg("--cert"), arg("--key"))
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=background, daemon=True).start()
    threading.Thread(target=push_worker, daemon=True).start()
    if sys.stdout:
        print(f"Macro Local at {url}  (data: {DATA_DIR})  Ctrl+C to stop")
    if "--no-window" not in args:
        threading.Timer(0.5, lambda: globals().__setitem__("_proc", open_window(url))).start()
    if "--no-window" not in args and find_chromium():
        # app mode: quit the server when the window closes
        def watch():
            time.sleep(2.5)
            p = globals().get("_proc")
            if p:
                p.wait()
                srv.shutdown()
        threading.Thread(target=watch, daemon=True).start()
    elif "--no-window" not in args and "--keep-running" not in args and HOST == "127.0.0.1":
        # opened in the default browser: there is no window to watch, so quit once the tab has been closed for a while
        idle = float(os.environ.get("MACRO_IDLE_SECONDS", 150))  # background tabs throttle timers, so be generous

        def idle_exit():
            t0 = time.time()
            while True:
                time.sleep(min(10, idle / 3))
                seen = globals().get("last_ping", 0)
                if (seen and time.time() - seen > idle) or (not seen and time.time() - t0 > idle + 30):
                    srv.shutdown()
                    return
        threading.Thread(target=idle_exit, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
